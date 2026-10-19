"""Rename the "Sales Invoice" print format to "Invoice" (Bry 2026-10-17, HT-169).

frappe.rename_doc follows every Link to Print Format (BP Print Lock Format,
BP Warehouse Print). The default_print_format Property Setter stores the
name as plain Data, so it is moved by hand.

If create_do_invoice_print_formats already made "Invoice" from the
templates, the old one is merged into it, so links still move over.

Idempotent: does nothing once "Sales Invoice" is gone.
"""

import frappe

OLD = "Sales Invoice"
NEW = "Invoice"


def execute():
	if frappe.db.exists("Print Format", OLD):
		frappe.rename_doc("Print Format", OLD, NEW, force=True, merge=frappe.db.exists("Print Format", NEW))

	frappe.db.sql(
		"""update `tabProperty Setter` set value = %s
		where property = 'default_print_format' and doc_type = 'Sales Invoice' and value = %s""",
		(NEW, OLD),
	)
	frappe.clear_cache(doctype="Sales Invoice")
