"""Sales Invoice.bp_sales_person: not mandatory for ND System invoices.

Invoices created by Import ND Invoice carry no salesperson, as in the old
Access "Import Sales Invoice" tool (Bry 2026-10-17). The field stays
mandatory for every other invoice through mandatory_depends_on;
bp.overrides.sales_invoice.validate skips its own check for the same case.
"""

import frappe


def execute():
	name = "Sales Invoice-bp_sales_person"
	if not frappe.db.exists("Custom Field", name):
		return
	field = frappe.get_doc("Custom Field", name)
	field.reqd = 0
	field.mandatory_depends_on = "eval:!doc.custom_nd_invoice_no"
	field.save()
