# Copyright (c) 2026, Hicom System and contributors
# For license information, please see license.txt

from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase

from bp.bp.doctype.import_nd_invoice.import_nd_invoice import (
	ImportNDInvoice,
	parse_amount,
	parse_dates,
	parse_pasted,
)


class TestImportNDInvoice(FrappeTestCase):
	def test_duplicate_nd_invoice_no_within_batch_is_blocked(self):
		doc = frappe.get_doc(
			{
				"doctype": "Import ND Invoice",
				"rows": [
					{
						"nd_invoice_no": "DUP-1",
						"cust_code_nd": "X",
						"invoice_date": "2026-01-01",
						"amount": 1,
					},
					{
						"nd_invoice_no": "DUP-1",
						"cust_code_nd": "Y",
						"invoice_date": "2026-01-01",
						"amount": 2,
					},
				],
			}
		)
		self.assertRaises(frappe.ValidationError, ImportNDInvoice.check_duplicate_nd_invoice_numbers, doc)

	def test_distinct_nd_invoice_numbers_pass(self):
		doc = frappe.get_doc(
			{
				"doctype": "Import ND Invoice",
				"rows": [
					{"nd_invoice_no": "A-1", "cust_code_nd": "X", "invoice_date": "2026-01-01", "amount": 1},
					{"nd_invoice_no": "A-2", "cust_code_nd": "Y", "invoice_date": "2026-01-01", "amount": 2},
				],
			}
		)
		ImportNDInvoice.check_duplicate_nd_invoice_numbers(doc)  # should not raise

	def test_resolve_customers_never_throws_on_unmatched_code(self):
		doc = frappe.get_doc(
			{
				"doctype": "Import ND Invoice",
				"rows": [
					{
						"nd_invoice_no": "A-1",
						"cust_code_nd": "NO-SUCH-CODE-XYZ",
						"invoice_date": "2026-01-01",
						"amount": 1,
					}
				],
			}
		)
		ImportNDInvoice.resolve_customers(doc)  # must not raise
		self.assertFalse(doc.rows[0].resolved_customer)

	def test_resolve_customers_sets_match(self):
		nd_code = frappe.generate_hash(length=8)
		customer = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": f"Test Import ND Customer {nd_code}",
				"customer_group": "Individual",
				"territory": "Indonesia",
				"custom_nd_code": nd_code,
				"custom_cn_initial": "Z",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(
			lambda: frappe.delete_doc("Customer", customer.name, force=True, ignore_permissions=True)
		)

		doc = frappe.get_doc(
			{
				"doctype": "Import ND Invoice",
				"rows": [
					{
						"nd_invoice_no": "A-1",
						"cust_code_nd": nd_code,
						"invoice_date": "2026-01-01",
						"amount": 1,
					}
				],
			}
		)
		ImportNDInvoice.resolve_customers(doc)
		self.assertEqual(doc.rows[0].resolved_customer, customer.name)
		self.assertEqual(doc.rows[0].cust_code, customer.name)
		self.assertEqual(doc.rows[0].customer_name, customer.customer_name)

	def test_submit_passes_without_extra_fields(self):
		customer, nd_code = frappe.db.get_value(
			"Customer", {"custom_nd_code": ["is", "set"], "disabled": 0}, ["name", "custom_nd_code"]
		)
		row = {
			"nd_invoice_no": f"TEST-{frappe.generate_hash(length=8)}",
			"cust_code_nd": nd_code,
			"invoice_date": "2026-01-01",
			"amount": 1000,
			"resolved_customer": customer,
		}
		doc = frappe.get_doc({"doctype": "Import ND Invoice", "rows": [row]})
		ImportNDInvoice.before_submit(doc)  # must not raise


class TestImportNDInvoiceEndToEnd(FrappeTestCase):
	"""HT-4: submitting a batch creates Sales Invoices that are already submitted, with Update Stock off.

	Earlier this failed with "Source Warehouse is required" because the import
	never sets set_warehouse; follow_standard_sales_invoice_warehouse made it
	optional again. Run in a transaction that is rolled back afterwards.
	"""

	def test_submit_creates_submitted_invoice_without_stock(self):
		customer, nd_code = frappe.db.get_value(
			"Customer", {"custom_nd_code": ["is", "set"], "disabled": 0}, ["name", "custom_nd_code"]
		)
		batch = frappe.get_doc(
			{
				"doctype": "Import ND Invoice",
				"rows": [
					{
						"nd_invoice_no": "TEST-ND-E2E-1",
						"cust_code_nd": nd_code,
						"invoice_date": frappe.utils.today(),
						"amount": 125000,
						# no salesman (Bry 2026-10-17) and no warehouse (Bry 2026-10-19)
					}
				],
			}
		).insert(ignore_permissions=True)
		batch.submit()

		si = frappe.get_doc("Sales Invoice", batch.rows[0].sales_invoice)
		self.assertEqual(si.name, "TEST-ND-E2E-1")  # named after the ND Invoice Number
		self.assertEqual(si.docstatus, 1)
		self.assertEqual(si.update_stock, 0)
		self.assertEqual(si.customer, customer)
		self.assertEqual(si.custom_nd_invoice_no, "TEST-ND-E2E-1")
		self.assertEqual(si.grand_total, 125000)
		self.assertFalse(si.bp_sales_person)
		self.assertFalse(si.sales_team)
		self.assertFalse(frappe.db.exists("Stock Ledger Entry", {"voucher_no": si.name}))

		batch.cancel()
		self.assertEqual(frappe.db.get_value("Sales Invoice", si.name, "docstatus"), 2)

	def test_submit_blocked_when_nd_number_is_taken_as_invoice_name(self):
		taken = frappe.db.get_value("Sales Invoice", {"custom_nd_invoice_no": ["is", "not set"]}, "name")
		if not taken:
			self.skipTest("needs an existing Sales Invoice that did not come from an ND import")
		customer, nd_code = frappe.db.get_value(
			"Customer", {"custom_nd_code": ["is", "set"], "disabled": 0}, ["name", "custom_nd_code"]
		)
		doc = frappe.get_doc(
			{
				"doctype": "Import ND Invoice",
				"rows": [
					{
						"nd_invoice_no": taken,
						"cust_code_nd": nd_code,
						"invoice_date": frappe.utils.today(),
						"amount": 1,
						"resolved_customer": customer,
					}
				],
			}
		)
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be used as the name"):
			ImportNDInvoice.before_submit(doc)


class TestPasteFromExcel(FrappeTestCase):
	"""Rows pasted from Excel carry the PC's display format (Bry 2026-10-23)."""

	def setUp(self):
		frappe.set_user("Administrator")

	def test_amount_in_both_separator_styles(self):
		self.assertEqual(parse_amount("1,016,195.70"), 1016195.70)
		self.assertEqual(parse_amount("1.016.195,70"), 1016195.70)
		self.assertEqual(parse_amount("204,281.00"), 204281)
		self.assertEqual(parse_amount("204.281"), 204281)
		self.assertEqual(parse_amount("1016195,7"), 1016195.7)
		self.assertEqual(parse_amount("Rp 5.000"), 5000)
		self.assertEqual(parse_amount("(1.500)"), -1500)
		self.assertEqual(parse_amount(3752250), 3752250)
		self.assertIsNone(parse_amount(""))

	def test_day_first_when_first_part_above_twelve(self):
		dates, error = parse_dates([("I261000444", "17/10/2026"), ("I261000445", "05/10/2026")])
		self.assertIsNone(error)
		self.assertEqual(dates, [date(2026, 10, 17), date(2026, 10, 5)])

	def test_month_first_when_second_part_above_twelve(self):
		dates, _ = parse_dates([("I261000444", "10-17-26"), ("I261000445", "10-05-26")])
		self.assertEqual(dates, [date(2026, 10, 17), date(2026, 10, 5)])

	def test_nd_number_month_settles_ambiguous_dates(self):
		# 05/10/2026 alone could be 5 Oct or 10 May; the ND number says October
		dates, _ = parse_dates([("I261000444", "05/10/2026")])
		self.assertEqual(dates, [date(2026, 10, 5)])
		dates, _ = parse_dates([("I261000444", "10/05/2026")])
		self.assertEqual(dates, [date(2026, 10, 5)])

	def test_mixed_order_is_refused(self):
		dates, error = parse_dates([("A", "17/10/2026"), ("B", "10/17/2026")])
		self.assertTrue(error)

	def test_iso_and_month_name_dates(self):
		cells = [("A", "2026-10-17"), ("B", "17-Okt-26"), ("C", "17 Oct 2026"), ("D", "hari ini")]
		dates, _ = parse_dates(cells)
		self.assertEqual(dates, [date(2026, 10, 17), date(2026, 10, 17), date(2026, 10, 17), None])

	def test_paste_reads_header_in_any_order_and_skips_blank_lines(self):
		text = (
			"Invoice Number\tInvoice Date\tCustomerID\tNet Amount\tExtra\r\n"
			"I261000444\t17/10/2026\t17CDFN1003\t1.016.195,70\tx\r\n"
			"\t\t\t\t\r\n"
			"I261000435\t17/10/2026\t17CDDR1004\t204.281,00\tx\r\n"
		)
		result = parse_pasted(text)
		self.assertEqual(result["errors"], [])
		self.assertEqual(
			[(r["nd_invoice_no"], r["cust_code_nd"], r["invoice_date"], r["amount"]) for r in result["rows"]],
			[
				("I261000444", "17CDFN1003", "2026-10-17", 1016195.70),
				("I261000435", "17CDDR1004", "2026-10-17", 204281),
			],
		)

	def test_paste_without_header_uses_the_nd_column_order(self):
		result = parse_pasted(
			"I261000444\t17/10/2026\t17CDFN1003\t1000\nSubtotal (1)\t\t\t1000\n\t\t\t\nI261000435\t17/10/2026\t17CDDR1004\t5"
		)
		self.assertEqual(result["errors"], [])
		self.assertEqual(
			[(r["nd_invoice_no"], r["cust_code_nd"], r["invoice_date"], r["amount"]) for r in result["rows"]],
			[("I261000444", "17CDFN1003", "2026-10-17", 1000), ("I261000435", "17CDDR1004", "2026-10-17", 5)],
		)

	def test_paste_with_incomplete_header_is_refused(self):
		self.assertRaises(
			frappe.ValidationError, parse_pasted, "Invoice Number\tInvoice Date\n I1\t17/10/2026"
		)

	def test_paste_reports_unreadable_cells(self):
		text = (
			"Invoice Number\tCustomerID\tInvoice Date\tNet Amount\n"
			"I1\tC1\tbesok\t100\n"
			"I2\tC2\t2026-10-17\tabc"
		)
		result = parse_pasted(text)
		self.assertEqual(result["rows"], [])
		self.assertEqual(len(result["errors"]), 2)
		# line numbers count the blank lines too, so they match the copied rows
		result = parse_pasted("Invoice Number\tCustomerID\tInvoice Date\tNet Amount\n\nI1\tC1\tbesok\t100")
		self.assertIn("Line 3", result["errors"][0])

	def test_paste_skips_subtotal_and_report_total_lines(self):
		# layout of the ND report: groups closed by "Subtotal (n)", then "Report Total"
		text = (
			"Invoice Number\tInvoice Date\tCustomerID\tNet Amount\n"
			"I261000444\t17/10/2026\t17CDFN1003\t1016195.7\n"
			"\t\t\t\n"
			"I261000435\t17/10/2026\t17CDDR1004\t204281\n"
			"Subtotal (1)\t\t\t204281\n"
			"\t\t\t\n"
			"Report Total\t\t\t1220476.7\n"
		)
		result = parse_pasted(text)
		self.assertEqual(result["errors"], [])
		self.assertEqual([r["nd_invoice_no"] for r in result["rows"]], ["I261000444", "I261000435"])
