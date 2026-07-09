"""Add Sales Invoice.custom_nd_invoice_no for cross-batch dedupe.

Stores the ND System's own "Invoice Number" on the Sales Invoice created by
Import ND Invoice processing, so
bp.bp.doctype.import_nd_invoice.import_nd_invoice can refuse to create a
second Sales Invoice for the same ND invoice number even if the originating
row was deleted and re-imported.

Idempotent: create_custom_fields(update=True) is safe to re-run.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Sales Invoice": [
		{
			"fieldname": "custom_nd_invoice_no",
			"fieldtype": "Data",
			"label": "ND Invoice No",
			"insert_after": "bp_sales_person",
			"read_only": 1,
			"no_copy": 1,
			"description": (
				"Invoice Number from the ND System's invoice export. Set automatically by Import "
				"ND Invoice processing; used to prevent duplicate imports."
			),
		},
	]
}


def execute():
	frappe.reload_doctype("Sales Invoice")
	create_custom_fields(CUSTOM_FIELDS, update=True)
