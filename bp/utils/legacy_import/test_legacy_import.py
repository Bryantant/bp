from datetime import datetime
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from bp.overrides.sales_invoice import check_active_invoice_limit
from bp.utils.cascading_discount import calculate_cascading_discount
from bp.utils.legacy_import import PURCHASE_INVOICE, SALES_INVOICE, LegacyImportError
from bp.utils.legacy_import import purchase_invoice as pm
from bp.utils.legacy_import import sales_invoice as sm
from bp.utils.legacy_import.runner import check_amount, classify


def sales_line(**kw):
	line = {
		"RowNumber": 1,
		"ItemCode": "ITEM-1",
		"DescTamb": None,
		"Quantity": 5,
		"UnitMeas": "PCS",
		"Packing": 1,
		"Price": 1000,
		"DiscPerc": 0,
		"DiscAmnt": 0,
		"DiscPerc2": 0,
		"DiscAmnt2": 0,
		"Discamnt3": 0,
		"BranchCode": "GD",
	}
	line.update(kw)
	return line


def legacy_doc(doctype=SALES_INVOICE, status=2, updated_at=datetime(2026, 6, 24, 17, 0), **kw):
	doc = {
		"doctype": doctype,
		"legacy_no": "F26060001",
		"date": datetime(2026, 6, 24).date(),
		"party": "C0001",
		"status": status,
		"updated_at": updated_at,
		"created_by": "LOUISE",
		"amount": None,
		"header": {},
		"lines": [],
	}
	doc.update(kw)
	return doc


class FakeContext:
	"""Just enough of ImportContext for the builders' validation path."""

	company_currency = "IDR"

	def __init__(self, customers=(), warehouses=None, sales_persons=None):
		self.customers = set(customers)
		self.warehouses = warehouses or {}
		self.sales_persons = sales_persons or {}

	def has_customer(self, code):
		return code in self.customers

	def warehouse(self, code):
		return self.warehouses.get(code)

	def sales_person(self, code):
		return self.sales_persons.get(code)

	def check_currency(self, currency, problems):
		if currency and currency != self.company_currency:
			problems.append(f"Currency {currency} is not supported")

	def check_lines(self, lines, problems):
		return [line for line in lines if line["Quantity"] > 0]


class IntegrationTestLegacyImport(IntegrationTestCase):
	# -- legacy totals ---------------------------------------------------------

	def test_sales_total_matches_legacy_cascading_formula(self):
		# 5 x 1000, 10% then 5% compounding: 5000 - 500 - 225 = 4275,
		# minus 25 manual line amount and 50 header amount = 4200.
		line = sales_line(DiscPerc=10, DiscAmnt=500, DiscPerc2=5, DiscAmnt2=225, Discamnt3=25)
		self.assertEqual(sm.legacy_sales_total({"ndisc1": 50}, [line]), 4200)

	def test_erp_cascading_rate_reproduces_legacy_line_net(self):
		line = sales_line(Quantity=5, Price=264000.70, DiscPerc=10, DiscAmnt=132000.35)
		erp = calculate_cascading_discount(price_list_rate=line["Price"], discount1_percentage=line["DiscPerc"])
		self.assertAlmostEqual(erp["rate"] * line["Quantity"], sm.legacy_line_net(line), delta=0.05)

	def test_expected_amount_prefers_legacy_invoice_amount(self):
		doc = legacy_doc(amount=999, header={"ndisc1": 0}, lines=[sales_line()])
		self.assertEqual(sm.expected_amount(doc), 999)
		doc["amount"] = None
		self.assertEqual(sm.expected_amount(doc), 5000)

	def test_purchase_line_net_uses_percentage_when_amount_missing(self):
		line = {"Quantity": 10, "Price": 100, "DiscPerc": 10, "DiscAmt": 0}
		self.assertEqual(pm.legacy_line_net(line), 900)
		line["DiscAmt"] = 50
		self.assertEqual(pm.legacy_line_net(line), 950)

	# -- classification ------------------------------------------------------

	def test_confirmed_not_in_erp_is_ready(self):
		self.assertEqual(classify(legacy_doc(), None)[0], "Ready")

	def test_invoiced_delivery_order_counts_as_confirmed(self):
		self.assertEqual(classify(legacy_doc(status=3), None)[0], "Ready")

	def test_draft_or_cancelled_not_in_erp_is_skipped(self):
		self.assertEqual(classify(legacy_doc(status=1), None)[0], "Skipped")
		self.assertEqual(classify(legacy_doc(status=9), None)[0], "Skipped")
		# Status 3 is DO-only: a receiving with 3 is not confirmed.
		self.assertEqual(classify(legacy_doc(PURCHASE_INVOICE, status=3), None)[0], "Skipped")

	def test_unchanged_is_already_imported(self):
		erp = {"name": "A26060001", "docstatus": 1, "custom_legacy_updated_at": datetime(2026, 6, 24, 17, 0)}
		self.assertEqual(classify(legacy_doc(), erp)[0], "Already Imported")

	def test_newer_legacy_update_is_flagged_not_fixed(self):
		erp = {"name": "A26060001", "docstatus": 1, "custom_legacy_updated_at": datetime(2026, 6, 24, 17, 0)}
		doc = legacy_doc(updated_at=datetime(2026, 8, 5, 18, 3))
		self.assertEqual(classify(doc, erp)[0], "Changed in Legacy")

	def test_reversed_or_cancelled_after_import_is_flagged(self):
		erp = {"name": "A26060001", "docstatus": 1, "custom_legacy_updated_at": datetime(2026, 6, 24, 17, 0)}
		self.assertEqual(classify(legacy_doc(status=1), erp)[0], "Cancelled in Legacy")
		self.assertEqual(classify(legacy_doc(status=9), erp)[0], "Cancelled in Legacy")

	# -- builders ------------------------------------------------------------

	def test_builder_reports_every_mapping_problem_at_once(self):
		doc = legacy_doc(
			header={"CustCode": "NOPE", "BranchCode": "TK", "SaleCode": "XX", "CurrCode": "USD"},
			lines=[sales_line()],
		)
		with self.assertRaises(LegacyImportError) as cm:
			sm.build_sales_invoice(doc, FakeContext())
		message = str(cm.exception)
		for fragment in ("customer NOPE", "branch TK", "code XX", "Currency USD"):
			self.assertIn(fragment, message)

	def test_amount_check_respects_tolerance(self):
		doc = frappe._dict(grand_total=1000.12)
		check_amount(doc, 1000, tolerance=1)
		with self.assertRaises(LegacyImportError):
			check_amount(doc, 990, tolerance=1)

	# -- credit limit bypass --------------------------------------------------

	def test_credit_limit_checked_unless_legacy_import_is_running(self):
		"""The old system already issued these invoices, so ERP's credit-limit
		block must not refuse them -- but only while an import is running."""
		from unittest.mock import patch as mock_patch

		from bp.overrides.sales_invoice import BPSalesInvoice

		doc = BPSalesInvoice({"doctype": "Sales Invoice"})
		with mock_patch(
			"erpnext.accounts.doctype.sales_invoice.sales_invoice.SalesInvoice.check_credit_limit"
		) as core_check:
			frappe.flags.bp_legacy_import = True
			try:
				doc.check_credit_limit()
			finally:
				frappe.flags.bp_legacy_import = False
			self.assertEqual(core_check.call_count, 0)

			doc.check_credit_limit()
			self.assertEqual(core_check.call_count, 1)

	# -- active invoice limit bypass -----------------------------------------

	def test_active_invoice_limit_skipped_only_during_legacy_import(self):
		doc = frappe._dict(is_return=0, customer="C0001", customer_name="C0001", name="new")
		with patch("bp.overrides.sales_invoice.frappe.get_all", return_value=["A1", "A2"]), patch(
			"bp.overrides.sales_invoice.frappe.db.get_value", return_value=1
		):
			with self.assertRaises(frappe.ValidationError):
				check_active_invoice_limit(doc)

			frappe.flags.bp_legacy_import = True
			try:
				check_active_invoice_limit(doc)
			finally:
				frappe.flags.bp_legacy_import = False
