# Copyright (c) 2026, Hicom System and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from bp.bp.doctype.import_nd_invoice.import_nd_invoice import ImportNDInvoice


class TestImportNDInvoice(FrappeTestCase):
	def test_duplicate_nd_invoice_no_within_batch_is_blocked(self):
		doc = frappe.get_doc(
			{
				"doctype": "Import ND Invoice",
				"rows": [
					{"nd_invoice_no": "DUP-1", "cust_code_nd": "X", "invoice_date": "2026-01-01", "amount": 1},
					{"nd_invoice_no": "DUP-1", "cust_code_nd": "Y", "invoice_date": "2026-01-01", "amount": 2},
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
		self.addCleanup(lambda: frappe.delete_doc("Customer", customer.name, force=True, ignore_permissions=True))

		doc = frappe.get_doc(
			{
				"doctype": "Import ND Invoice",
				"rows": [
					{"nd_invoice_no": "A-1", "cust_code_nd": nd_code, "invoice_date": "2026-01-01", "amount": 1}
				],
			}
		)
		ImportNDInvoice.resolve_customers(doc)
		self.assertEqual(doc.rows[0].resolved_customer, customer.name)
		self.assertEqual(doc.rows[0].cust_code, customer.name)
		self.assertEqual(doc.rows[0].customer_name, customer.customer_name)

	def test_missing_warehouse_blocks_submit_but_salesman_is_optional(self):
		customer, nd_code = frappe.db.get_value(
			"Customer", {"custom_nd_code": ["is", "set"], "disabled": 0}, ["name", "custom_nd_code"]
		)
		row = {
			"nd_invoice_no": f"TEST-{frappe.generate_hash(length=8)}",
			"cust_code_nd": nd_code,
			"invoice_date": "2026-01-01",
			"amount": 1000,
			"resolved_customer": customer,
			# salesman deliberately omitted: optional for ND invoices
		}
		doc = frappe.get_doc({"doctype": "Import ND Invoice", "rows": [row]})
		with self.assertRaisesRegex(frappe.ValidationError, "Warehouse is required"):
			ImportNDInvoice.before_submit(doc)

		doc.rows[0].warehouse = frappe.db.get_value("Warehouse", {"is_group": 0}, "name")
		ImportNDInvoice.before_submit(doc)  # no salesman, still passes


class TestImportNDInvoiceEndToEnd(FrappeTestCase):
	"""HT-4: submit creates a Draft Sales Invoice that can itself be submitted.

	Earlier this failed with "Source Warehouse is required" because the import
	never sets set_warehouse; follow_standard_sales_invoice_warehouse made it
	optional again. Run in a transaction that is rolled back afterwards.
	"""

	def test_submit_creates_draft_invoice_that_submits(self):
		customer, nd_code = frappe.db.get_value(
			"Customer", {"custom_nd_code": ["is", "set"], "disabled": 0}, ["name", "custom_nd_code"]
		)
		warehouse = frappe.db.get_value("Warehouse", {"is_group": 0, "company": "PT. Bestindo Persada"}, "name")
		batch = frappe.get_doc(
			{
				"doctype": "Import ND Invoice",
				"rows": [
					{
						"nd_invoice_no": "TEST-ND-E2E-1",
						"cust_code_nd": nd_code,
						"invoice_date": frappe.utils.today(),
						"amount": 125000,
						# no salesman: ND invoices carry none (Bry 2026-10-17)
						"warehouse": warehouse,
					}
				],
			}
		).insert(ignore_permissions=True)
		batch.submit()

		si = frappe.get_doc("Sales Invoice", batch.rows[0].sales_invoice)
		self.assertEqual(si.name, "TEST-ND-E2E-1")  # named after the ND Invoice Number
		self.assertEqual(si.docstatus, 0)
		self.assertEqual(si.customer, customer)
		self.assertEqual(si.custom_nd_invoice_no, "TEST-ND-E2E-1")
		self.assertEqual(si.items[0].warehouse, warehouse)
		self.assertEqual(si.grand_total, 125000)
		self.assertFalse(si.bp_sales_person)
		self.assertFalse(si.sales_team)

		si.submit()
		self.assertEqual(si.docstatus, 1)
		self.assertFalse(frappe.db.exists("Stock Ledger Entry", {"voucher_no": si.name}))

	def test_submit_blocked_when_nd_number_is_taken_as_invoice_name(self):
		taken = frappe.db.get_value(
			"Sales Invoice", {"custom_nd_invoice_no": ["is", "not set"]}, "name"
		)
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
						"salesman": frappe.db.get_value("Sales Person", {"is_group": 0}, "name"),
						"warehouse": frappe.db.get_value("Warehouse", {"is_group": 0}, "name"),
						"resolved_customer": customer,
					}
				],
			}
		)
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be used as the name"):
			ImportNDInvoice.before_submit(doc)
