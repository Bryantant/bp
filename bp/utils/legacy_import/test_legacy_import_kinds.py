from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from bp.utils.legacy_import import (
	AP_PAYMENT,
	AR_RECEIPT,
	PURCHASE_INVOICE,
	SALES_INVOICE,
	SALES_RETURN,
	STOCK_MUTATION,
	STOCK_SET,
	LegacyImportError,
)
from bp.utils.legacy_import.ap_payment import build_ap_payment
from bp.utils.legacy_import.ar_receipt import build_ar_receipt
from bp.utils.legacy_import.context import PENDING, ImportContext, is_nd_invoice_no
from bp.utils.legacy_import.kinds import KINDS, ORDERED, selected_kinds
from bp.utils.legacy_import.runner import classify
from bp.utils.legacy_import.sales_return import build_sales_return
from bp.utils.legacy_import.sales_return import expected_amount as return_expected
from bp.utils.legacy_import.stock_mutation import build_stock_mutation, check_quantity
from bp.utils.legacy_import.stock_set import build_stock_set

BANK = "11158 - Bank BCA - PT - BP"
RETUR_ACCOUNT = "42200 - Retur Penjualan - BP"
RECEIVABLE = "11201 - Piutang IDR - BP"
PAYABLE = "21100 - Hutang IDR - BP"


class FakeContext:
	"""Everything the builders read, with no database or legacy connection."""

	company = "PT. Bestindo Persada"
	company_currency = "IDR"
	cost_center = "Main - BP"
	tolerance = 10
	check_lines = ImportContext.check_lines

	def __init__(self, warehouses=None, methods=None, invoices=None, returns=None):
		self.warehouses = warehouses or {"GD": "A - BP", "GS": "GS - BP", "TK": "D - BP"}
		self.methods = methods if methods is not None else {"Bank BCA - PT": BANK, "Retur Penjualan": RETUR_ACCOUNT}
		self.invoices = invoices or {}
		self.returns = returns or {}
		self.return_credits = {}

	def has_customer(self, code):
		return code == "C0001"

	def has_supplier(self, code):
		return code == "S0001"

	def warehouse(self, code):
		return self.warehouses.get((code or "").strip().upper())

	def sales_person(self, code):
		return "LEMON" if code == "LEM" else None

	def uom(self, unit):
		return (unit or "").strip() or None

	def item_name(self, code):
		return code

	def check_currency(self, currency, problems):
		if currency and currency != "IDR":
			problems.append(f"Currency {currency} is not supported")

	def method_account(self, method, currency):
		return self.methods.get(method)

	pending = set()

	def missing_valuation_rate(self, item_code, warehouse, posting_date):
		return None

	def stock_entry_type(self, purpose):
		# Renamed like this site's: looked up by purpose, never by name.
		return {
			"Material Receipt": "Barang Masuk",
			"Material Issue": "Barang Keluar",
			"Material Transfer": "Relokasi Barang",
			"Repack": "Rakit Set",
		}.get(purpose)

	def is_return_method(self, method, currency):
		return method == "Retur Penjualan"

	def invoice_for(self, doctype, legacy_no, kind):
		return self.invoices.get(legacy_no)

	def sales_return_for(self, legacy_no):
		return self.returns.get(legacy_no)

	def return_credit(self, name):
		return self.return_credits.get(name, ("C0001", 10**9))

	def party_account(self, doctype, name):
		return RECEIVABLE if doctype == "Sales Invoice" else PAYABLE


def doc(kind, header, lines, legacy_no="X1", status=2):
	return {
		"kind": kind,
		"legacy_no": legacy_no,
		"date": datetime(2026, 9, 5).date(),
		"party": header.get("CustCode") or header.get("SuppCode"),
		"status": status,
		"updated_at": datetime(2026, 9, 5, 17, 0),
		"created_by": "DIPIN",
		"amount": None,
		"header": header,
		"lines": lines,
	}


def stock_line(item="ITEM-1", qty=5, packing=1, price=0, trans=None, row=1):
	line = {"RowNumber": row, "ItemCode": item, "Quantity": qty, "UnitMeas": "PCS", "Packing": packing, "Price": price}
	if trans is not None:
		line["Trans"] = trans
	return line


def pay_line(invoice, amount, method="Bank BCA - PT", doc_no=None, seq=1, currency="IDR"):
	return {
		"SeqNo": seq,
		"InvoDNNo": invoice,
		"CurrInDN": currency,
		"InDNAmon": amount,
		"CurrPaid": currency,
		"AmonPaid": amount,
		"MethodBy": method,
		"DocNo": doc_no,
	}


def no_db_accounts():
	"""payment.py reads account_type and the company's default party accounts."""

	def fake(doctype, name, field):
		if doctype == "Account":
			return ""
		if field == "default_receivable_account":
			return RECEIVABLE
		return PAYABLE

	return patch("bp.utils.legacy_import.payment.frappe.get_cached_value", side_effect=fake)


class IntegrationTestLegacyImportKinds(IntegrationTestCase):
	# -- registry -------------------------------------------------------------

	def test_processing_order_follows_dependencies(self):
		"""Goods in before goods out; invoices and returns before the receipts that settle them."""
		self.assertEqual(
			[k.key for k in ORDERED],
			[PURCHASE_INVOICE, STOCK_MUTATION, STOCK_SET, SALES_INVOICE, SALES_RETURN, AR_RECEIPT, AP_PAYMENT],
		)

	def test_revert_cancels_payments_before_the_invoices_they_settle(self):
		by_revert = [k.key for k in sorted(KINDS.values(), key=lambda k: k.revert_order)]
		self.assertLess(by_revert.index(AR_RECEIPT), by_revert.index(SALES_INVOICE))
		self.assertLess(by_revert.index(AR_RECEIPT), by_revert.index(SALES_RETURN))
		self.assertLess(by_revert.index(AP_PAYMENT), by_revert.index(PURCHASE_INVOICE))
		self.assertLess(by_revert.index(SALES_INVOICE), by_revert.index(PURCHASE_INVOICE))

	def test_every_kind_has_a_checkbox_on_legacy_import(self):
		meta = frappe.get_meta("Legacy Import")
		for kind in KINDS.values():
			self.assertTrue(meta.get_field(kind.batch_flag), kind.batch_flag)
		batch = frappe._dict({kind.batch_flag: 0 for kind in KINDS.values()})
		batch.import_ar_receipt = 1
		self.assertEqual([k.key for k in selected_kinds(batch)], [AR_RECEIPT])

	def test_receipts_have_no_confirm_step(self):
		"""A saved receipt is effective; only 9 means cancelled."""
		self.assertEqual(classify(doc(AR_RECEIPT, {}, [], status=1), None)[0], "Ready")
		self.assertEqual(classify(doc(AR_RECEIPT, {}, [], status=9), None)[0], "Skipped")
		self.assertEqual(classify(doc(STOCK_MUTATION, {}, [], status=1), None)[0], "Skipped")

	# -- sales return ---------------------------------------------------------

	def _return_header(self, **kw):
		header = {
			"CustCode": "C0001",
			"BranchCode": "GS",
			"SaleCode": "LEM",
			"CurrCode": "IDR",
			"SalRetDt": datetime(2026, 9, 5),
			"CreaDate": datetime(2026, 9, 5, 10, 0),
			"SalRetNt": None,
		}
		header.update(kw)
		return header

	def test_return_puts_goods_back_with_negative_quantity(self):
		line = {**stock_line(qty=3, price=100000), "DiscPerc": 10, "DiscAmnt": 30000}
		si = build_sales_return(doc(SALES_RETURN, self._return_header(), [line]), FakeContext())
		self.assertEqual(si.is_return, 1)
		self.assertEqual(si.update_stock, 1)
		self.assertEqual(si.set_warehouse, "GS - BP")
		self.assertEqual(si.custom_legacy_type, SALES_RETURN)
		item = si.items[0]
		self.assertEqual(item.qty, -3)
		self.assertEqual(item.custom_discount1_percentage, 10)
		self.assertEqual(item.custom_discount1_amount, 10000)  # per unit

	def test_return_expected_total_is_negative(self):
		line = {**stock_line(qty=3, price=100000), "DiscPerc": 10, "DiscAmnt": 30000}
		self.assertEqual(return_expected(doc(SALES_RETURN, {}, [line])), -270000)

	def test_return_to_an_unmapped_branch_is_refused(self):
		line = {**stock_line(), "DiscPerc": 0, "DiscAmnt": 0}
		with self.assertRaises(LegacyImportError) as cm:
			build_sales_return(doc(SALES_RETURN, self._return_header(BranchCode="BR"), [line]), FakeContext())
		self.assertIn("branch BR", str(cm.exception))

	def test_return_to_a_warehouse_without_history_uses_the_company_valuation(self):
		ctx = FakeContext()
		ctx.missing_valuation_rate = lambda item, warehouse, date: 12500
		line = {**stock_line(), "DiscPerc": 0, "DiscAmnt": 0}
		si = build_sales_return(doc(SALES_RETURN, self._return_header(), [line]), ctx)
		self.assertEqual(si.items[0].incoming_rate, 12500)

	def test_return_of_an_item_never_valued_in_erp_is_refused(self):
		ctx = FakeContext()
		ctx.missing_valuation_rate = lambda item, warehouse, date: 0
		line = {**stock_line(), "DiscPerc": 0, "DiscAmnt": 0}
		with self.assertRaises(LegacyImportError) as cm:
			build_sales_return(doc(SALES_RETURN, self._return_header(), [line]), ctx)
		self.assertIn("no stock valuation", str(cm.exception))

	# -- stock mutation --------------------------------------------------------

	def _mutation(self, trans, source="GD", dest=None, lines=None):
		header = {
			"Trans": trans,
			"BranchCode": source,
			"BranchCodeDest": dest,
			"MutDate": datetime(2026, 9, 5),
			"CreaDate": datetime(2026, 9, 5, 9, 0),
			"Alasan": "Koreksi",
			"MutNote": None,
		}
		return doc(STOCK_MUTATION, header, lines or [stock_line(qty=2, packing=12, price=240000)])

	def test_goods_in_is_valued_at_the_legacy_price_per_stock_unit(self):
		se = build_stock_mutation(self._mutation(1), FakeContext())
		self.assertEqual(se.purpose, "Material Receipt")
		row = se.items[0]
		self.assertEqual(row.t_warehouse, "A - BP")
		self.assertIsNone(row.s_warehouse)
		# 240,000 per CTN of 12 -> 20,000 per piece, the stock unit
		self.assertEqual(row.basic_rate, 20000)
		self.assertEqual(row.set_basic_rate_manually, 1)

	def test_goods_in_without_a_price_uses_the_fallback_valuation(self):
		ctx = FakeContext()
		ctx.missing_valuation_rate = lambda item, warehouse, date: 7500
		se = build_stock_mutation(self._mutation(1, lines=[stock_line(qty=2, price=0)]), ctx)
		self.assertEqual((se.items[0].basic_rate, se.items[0].set_basic_rate_manually), (7500, 1))

		ctx.missing_valuation_rate = lambda item, warehouse, date: None  # ERP can value it
		se = build_stock_mutation(self._mutation(1, lines=[stock_line(qty=2, price=0)]), ctx)
		self.assertFalse(se.items[0].set_basic_rate_manually)

		ctx.missing_valuation_rate = lambda item, warehouse, date: 0
		with self.assertRaises(LegacyImportError) as cm:
			build_stock_mutation(self._mutation(1, lines=[stock_line(qty=2, price=0)]), ctx)
		self.assertIn("no price and no stock valuation", str(cm.exception))

	def test_goods_out_and_transfers_are_valued_by_erp(self):
		issue = build_stock_mutation(self._mutation(2), FakeContext())
		self.assertEqual(issue.purpose, "Material Issue")
		self.assertEqual(issue.items[0].s_warehouse, "A - BP")
		self.assertFalse(issue.items[0].set_basic_rate_manually)

		transfer = build_stock_mutation(self._mutation(3, "TK", "GD"), FakeContext())
		self.assertEqual(transfer.purpose, "Material Transfer")
		self.assertEqual(transfer.stock_entry_type, "Relokasi Barang")
		self.assertEqual((transfer.items[0].s_warehouse, transfer.items[0].t_warehouse), ("D - BP", "A - BP"))

	def test_transfer_needs_a_mapped_different_destination(self):
		with self.assertRaises(LegacyImportError) as cm:
			build_stock_mutation(self._mutation(3, "GD", "KS"), FakeContext())
		self.assertIn("destination branch KS", str(cm.exception))
		with self.assertRaises(LegacyImportError):
			build_stock_mutation(self._mutation(3, "GD", "GD"), FakeContext())

	def test_quantity_check_compares_stock_units(self):
		# SimpleNamespace, not frappe._dict: a _dict's .items is dict.items().
		legacy = self._mutation(3, "TK", "GD", [stock_line(qty=2, packing=12)])
		check_quantity(SimpleNamespace(items=[SimpleNamespace(transfer_qty=24)]), legacy)
		with self.assertRaises(LegacyImportError):
			check_quantity(SimpleNamespace(items=[SimpleNamespace(transfer_qty=2)]), legacy)

	# -- stock set ------------------------------------------------------------

	def test_set_consumes_components_and_makes_finished_items_in_one_warehouse(self):
		header = {"BranchCode": "GD", "MutDate": datetime(2026, 9, 1), "CreaDate": None, "Alasan": None, "MutNote": None}
		lines = [stock_line("SET-1", 10, trans=1, row=1), stock_line("PART-1", 10, trans=2, row=2)]
		se = build_stock_set(doc(STOCK_SET, header, lines), FakeContext())
		self.assertEqual(se.purpose, "Repack")
		by_item = {row.item_code: row for row in se.items}
		self.assertEqual(by_item["PART-1"].s_warehouse, "A - BP")
		self.assertEqual(by_item["SET-1"].t_warehouse, "A - BP")
		self.assertEqual(by_item["SET-1"].is_finished_item, 1)

	def test_set_without_a_finished_line_is_refused(self):
		header = {"BranchCode": "GD", "MutDate": datetime(2026, 9, 1), "CreaDate": None, "Alasan": None, "MutNote": None}
		with self.assertRaises(LegacyImportError):
			build_stock_set(doc(STOCK_SET, header, [stock_line(trans=2)]), FakeContext())

	# -- AR receipt -----------------------------------------------------------

	def _receipt(self, lines):
		header = {"CustCode": "C0001", "RecNotDt": datetime(2026, 9, 5), "PaymNote": "Tagihan Sep"}
		return doc(AR_RECEIPT, header, lines, legacy_no="BI26090051")

	def test_money_line_settles_the_invoice_against_the_method_account(self):
		ctx = FakeContext(invoices={"IF26083151": "IF26083151"})
		with no_db_accounts():
			je = build_ar_receipt(self._receipt([pay_line("IF26083151", 940000)]), ctx)
		invoice_row = next(r for r in je.accounts if r.reference_name == "IF26083151")
		self.assertEqual((invoice_row.account, invoice_row.party, invoice_row.credit_in_account_currency), (RECEIVABLE, "C0001", 940000))
		bank_row = next(r for r in je.accounts if r.account == BANK)
		self.assertEqual(bank_row.debit_in_account_currency, 940000)
		self.assertEqual(je.cheque_no, "BI26090051")

	def test_return_line_applies_the_imported_return_instead_of_booking_42200(self):
		"""The imported return already reduced the receivable; booking 42200 too
		would reduce it twice."""
		ctx = FakeContext(invoices={"IF26083151": "IF26083151"}, returns={"26080314": "RA26090001"})
		lines = [pay_line("IF26083151", 940000, seq=1), pay_line("IF26083151", 60000, "Retur Penjualan", "26080314", seq=2)]
		with no_db_accounts():
			je = build_ar_receipt(self._receipt(lines), ctx)
		return_row = next(r for r in je.accounts if r.reference_name == "RA26090001")
		self.assertEqual((return_row.account, return_row.debit_in_account_currency), (RECEIVABLE, 60000))
		self.assertFalse([r for r in je.accounts if r.account == RETUR_ACCOUNT])

	def test_return_line_without_an_imported_return_falls_back_to_42200(self):
		ctx = FakeContext(invoices={"IF26083151": "IF26083151"})
		lines = [pay_line("IF26083151", 60000, "Retur Penjualan", "26010999")]
		with no_db_accounts():
			je = build_ar_receipt(self._receipt(lines), ctx)
		self.assertEqual(next(r for r in je.accounts if r.account == RETUR_ACCOUNT).debit_in_account_currency, 60000)

	def test_return_of_another_customer_falls_back_to_42200(self):
		"""DocNo is free text in the old system; a number that lands on another
		customer's return must not move that customer's credit."""
		ctx = FakeContext(invoices={"IF26083151": "IF26083151"}, returns={"26090089": "RB26090028"})
		ctx.return_credits = {"RB26090028": ("T0140", 92000)}
		lines = [pay_line("IF26083151", 60000, "Retur Penjualan", "26090089")]
		with no_db_accounts():
			je = build_ar_receipt(self._receipt(lines), ctx)
		self.assertFalse([r for r in je.accounts if r.reference_name == "RB26090028"])
		self.assertEqual(next(r for r in je.accounts if r.account == RETUR_ACCOUNT).debit_in_account_currency, 60000)

	def test_return_is_not_applied_beyond_its_remaining_credit(self):
		ctx = FakeContext(invoices={"IA": "IA", "IB": "IB"}, returns={"26090046": "RA26090007"})
		ctx.return_credits = {"RA26090007": ("C0001", 100000)}
		lines = [
			pay_line("IA", 80000, "Retur Penjualan", "26090046", seq=1),
			pay_line("IB", 50000, "Retur Penjualan", "26090046", seq=2),
		]
		with no_db_accounts():
			je = build_ar_receipt(self._receipt(lines), ctx)
		applied = [r for r in je.accounts if r.reference_name == "RA26090007"]
		self.assertEqual([r.debit_in_account_currency for r in applied], [80000])
		self.assertEqual(next(r for r in je.accounts if r.account == RETUR_ACCOUNT).debit_in_account_currency, 50000)

	def test_four_decimal_legacy_amounts_still_balance(self):
		ctx = FakeContext(invoices={"IA": "IA", "IB": "IB", "IC": "IC"})
		lines = [pay_line("IA", 13879999.9976, seq=1), pay_line("IB", 6879999.9984, seq=2), pay_line("IC", 16779999.9968, seq=3)]
		with no_db_accounts():
			je = build_ar_receipt(self._receipt(lines), ctx)
		debit = sum(r.debit_in_account_currency or 0 for r in je.accounts)
		credit = sum(r.credit_in_account_currency or 0 for r in je.accounts)
		self.assertEqual(round(debit - credit, 6), 0)

	def test_missing_nd_invoice_points_at_import_nd_invoice(self):
		with no_db_accounts(), self.assertRaises(LegacyImportError) as cm:
			build_ar_receipt(self._receipt([pay_line("I260900187", 1000)]), FakeContext())
		self.assertIn("Import ND Invoice", str(cm.exception))

	def test_nd_invoice_numbers_are_told_apart_from_delivery_order_invoices(self):
		self.assertTrue(is_nd_invoice_no("I260900187"))
		self.assertFalse(is_nd_invoice_no("IC26090149"))
		self.assertFalse(is_nd_invoice_no("I26090014"))

	def test_lines_paid_the_same_way_become_one_deposit_row(self):
		ctx = FakeContext(invoices={"IA": "IA", "IB": "IB"})
		lines = [pay_line("IA", 100, seq=1), pay_line("IB", 200, seq=2)]
		with no_db_accounts():
			je = build_ar_receipt(self._receipt(lines), ctx)
		bank_rows = [r for r in je.accounts if r.account == BANK]
		self.assertEqual(len(bank_rows), 1)
		self.assertEqual(bank_rows[0].debit_in_account_currency, 300)

	def test_receipt_reports_every_problem_at_once(self):
		ctx = FakeContext(invoices={}, methods={})
		lines = [pay_line("IF1", 100, "Bank Maybank 1.5M - IDR", seq=1), pay_line("IF2", 5, currency="SGD", seq=2)]
		with no_db_accounts(), self.assertRaises(LegacyImportError) as cm:
			build_ar_receipt(self._receipt(lines), ctx)
		message = str(cm.exception)
		for fragment in ("invoice IF1 is not in ERP", "Bank Maybank 1.5M - IDR", "currency SGD"):
			self.assertIn(fragment, message)

	def test_invoice_created_later_in_the_same_batch_is_not_an_error_in_preview(self):
		ctx = FakeContext(invoices={"IF26090001": PENDING})
		with no_db_accounts():
			je = build_ar_receipt(self._receipt([pay_line("IF26090001", 100)]), ctx)
		self.assertEqual(next(r for r in je.accounts if r.party).account, RECEIVABLE)

	# -- AP payment -----------------------------------------------------------

	def test_ap_payment_is_the_mirror_of_an_ar_receipt(self):
		header = {"SuppCode": "S0001", "PayNotDt": datetime(2026, 9, 5), "PaymNote": None}
		ctx = FakeContext(invoices={"I20030137": "I20030137"}, methods={"Bank BCA - PT": BANK})
		with no_db_accounts():
			je = build_ap_payment(doc(AP_PAYMENT, header, [pay_line("I20030137", 500)]), ctx)
		bill_row = next(r for r in je.accounts if r.reference_name == "I20030137")
		self.assertEqual((bill_row.account, bill_row.party_type, bill_row.debit_in_account_currency), (PAYABLE, "Supplier", 500))
		self.assertEqual(next(r for r in je.accounts if r.account == BANK).credit_in_account_currency, 500)

	def test_ap_has_no_return_offset_path(self):
		"""'Retur Pembelian' books to its own account; only AR offsets returns."""
		header = {"SuppCode": "S0001", "PayNotDt": datetime(2026, 9, 5), "PaymNote": None}
		ctx = FakeContext(
			invoices={"I1": "I1"},
			methods={"Retur Pembelian": "51700 - Retur Pembelian - BP"},
			returns={"R1": "RA26090001"},
		)
		with no_db_accounts():
			je = build_ap_payment(doc(AP_PAYMENT, header, [pay_line("I1", 50, "Retur Pembelian", "R1")]), ctx)
		self.assertTrue([r for r in je.accounts if r.account == "51700 - Retur Pembelian - BP"])
