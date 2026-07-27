"""Add Sales Invoice.custom_order_by for the Delivery Order / Sales Invoice print formats.

Free-text "Order By" line shown under the customer block on both new print
formats. Not backed by any existing logic (unlike bp_sales_person), hence the
custom_ prefix rather than bp_.

Idempotent: create_custom_fields(update=True) is safe to re-run.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Sales Invoice": [
		{
			"fieldname": "custom_order_by",
			"fieldtype": "Data",
			"label": "Order By",
			"insert_after": "po_no",
			"description": "Printed on the Sales Invoice and Delivery Order print formats.",
		},
	]
}


def execute():
	frappe.reload_doctype("Sales Invoice")
	create_custom_fields(CUSTOM_FIELDS, update=True)
