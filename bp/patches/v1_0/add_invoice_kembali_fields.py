"""Add the "Invoice Kembali" status fields to Sales Invoice (HT-42).

Set by the Invoice Kembali form on submit and cleared on cancel
(bp/bp/doctype/invoice_kembali), read by the report Invoice Belum Kembali.
All read only and no_copy: an amended or duplicated invoice starts as not
returned. Placed in a collapsible section of the More Info tab, right after
the Print Control section (ensure_print_control_fields, which runs first).

Idempotent: create_custom_fields(update=True) is safe to re-run.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

COMMON = {"read_only": 1, "no_copy": 1, "allow_on_submit": 1, "print_hide": 1}

CUSTOM_FIELDS = {
	"Sales Invoice": [
		{
			"fieldname": "bp_kembali_section",
			"fieldtype": "Section Break",
			"label": "Invoice Kembali",
			"insert_after": "bp_last_printed_at",
			"collapsible": 1,
		},
		{
			"fieldname": "bp_invoice_kembali",
			"fieldtype": "Check",
			"label": "Invoice Kembali",
			"insert_after": "bp_kembali_section",
			"in_standard_filter": 1,
			"search_index": 1,
			"description": "Set when the invoice is scanned back in on an Invoice Kembali form.",
			**COMMON,
		},
		{
			"fieldname": "bp_kembali_at",
			"fieldtype": "Datetime",
			"label": "Kembali At",
			"insert_after": "bp_invoice_kembali",
			**COMMON,
		},
		{
			"fieldname": "bp_kembali_column_break",
			"fieldtype": "Column Break",
			"insert_after": "bp_kembali_at",
		},
		{
			"fieldname": "bp_kembali_by",
			"fieldtype": "Link",
			"label": "Kembali By",
			"options": "User",
			"insert_after": "bp_kembali_column_break",
			**COMMON,
		},
		{
			"fieldname": "bp_kembali_ref",
			"fieldtype": "Link",
			"label": "Invoice Kembali Ref",
			"options": "Invoice Kembali",
			"insert_after": "bp_kembali_by",
			**COMMON,
		},
	]
}


def execute():
	frappe.reload_doctype("Sales Invoice")
	create_custom_fields(CUSTOM_FIELDS, update=True)
