"""Invoice Kembali (HT-42) against real submitted invoices of the site.

Plain unittest.TestCase, not IntegrationTestCase: the latter's setup makes
ERPNext test records in the site (dev lessons #67/#69). Every test rolls back,
so the invoices it marks and the IK counter are left as they were.
Run from a bench execute runner, not bench run-tests.
"""

import unittest

import frappe

from bp.bp.doctype.invoice_kembali.invoice_kembali import find_invoice, resolve_invoice


def _tracked_invoices(count):
	return frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "is_return": 0, "bp_invoice_kembali": 0, "custom_nd_invoice_no": ["is", "not set"]},
		fields=["name", "company"],
		order_by="posting_date desc",
		limit=count,
	)


def _new(invoices, company):
	return frappe.get_doc(
		{
			"doctype": "Invoice Kembali",
			"company": company,
			"invoices": [{"sales_invoice": name} for name in invoices],
		}
	)


class TestInvoiceKembali(unittest.TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.invoices = _tracked_invoices(2)
		if len(self.invoices) < 2:
			self.skipTest("needs two submitted Sales Invoices not yet returned")
		self.company = self.invoices[0].company

	def tearDown(self):
		frappe.db.rollback()

	def test_submit_marks_and_cancel_clears(self):
		names = [i.name for i in self.invoices]
		doc = _new(names, self.company).insert()
		self.assertTrue(doc.name.startswith("IK-"))
		self.assertEqual(doc.total_invoices, 2)
		self.assertTrue(doc.invoices[0].customer)

		doc.submit()
		for name in names:
			si = frappe.db.get_value(
				"Sales Invoice", name, ["bp_invoice_kembali", "bp_kembali_by", "bp_kembali_ref", "bp_kembali_at"], as_dict=True
			)
			self.assertEqual((si.bp_invoice_kembali, si.bp_kembali_by, si.bp_kembali_ref), (1, "Administrator", doc.name))
			self.assertTrue(si.bp_kembali_at)

		doc.cancel()
		for name in names:
			self.assertEqual(frappe.db.get_value("Sales Invoice", name, ["bp_invoice_kembali", "bp_kembali_ref"]), (0, None))

	def test_already_returned_invoice_is_rejected(self):
		name = self.invoices[0].name
		_new([name], self.company).insert().submit()
		self.assertIn("already returned", resolve_invoice(name)["error"])
		with self.assertRaises(frappe.ValidationError):
			_new([name], self.company).insert()

	def test_duplicate_row_is_rejected(self):
		name = self.invoices[0].name
		with self.assertRaises(frappe.ValidationError):
			_new([name, name], self.company).insert()

	def test_resolve_returns_row_values(self):
		name = self.invoices[0].name
		row = resolve_invoice(f"  {name.lower()} ")
		self.assertEqual(row["sales_invoice"], name)
		self.assertIn("customer_name", row)

	def test_resolve_rejects_untracked_invoices(self):
		self.assertIn("not found", resolve_invoice("NO-SUCH-INVOICE")["error"])
		ret = frappe.db.get_value("Sales Invoice", {"docstatus": 1, "is_return": 1}, "name")
		if ret:
			self.assertIn("return", resolve_invoice(ret)["error"])
		cancelled = frappe.db.get_value("Sales Invoice", {"docstatus": 2}, "name")
		if cancelled:
			self.assertIn("cancelled", resolve_invoice(cancelled)["error"])

	def test_find_by_legacy_number(self):
		row = frappe.db.get_value(
			"Sales Invoice",
			{"docstatus": 1, "custom_legacy_no": ["is", "set"]},
			["name", "custom_legacy_no"],
			as_dict=True,
		)
		if not row or frappe.db.exists("Sales Invoice", row.custom_legacy_no):
			self.skipTest("no legacy number that differs from every invoice name")
		self.assertEqual(find_invoice(row.custom_legacy_no), row.name)
