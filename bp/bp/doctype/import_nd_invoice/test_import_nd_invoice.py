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

	def test_create_sales_invoices_blocks_all_or_nothing_on_missing_salesman(self):
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

		warehouse = frappe.get_all("Warehouse", limit=1, pluck="name")[0]
		doc = frappe.get_doc(
			{
				"doctype": "Import ND Invoice",
				"rows": [
					{
						"nd_invoice_no": f"TEST-{nd_code}",
						"cust_code_nd": nd_code,
						"invoice_date": "2026-01-01",
						"amount": 1000,
						"warehouse": warehouse,
						# salesman deliberately omitted
					}
				],
			}
		)
		ImportNDInvoice.resolve_customers(doc)
		self.assertRaises(frappe.ValidationError, ImportNDInvoice.create_sales_invoices, doc)
		self.assertFalse(frappe.db.exists("Sales Invoice", {"custom_nd_invoice_no": f"TEST-{nd_code}"}))
