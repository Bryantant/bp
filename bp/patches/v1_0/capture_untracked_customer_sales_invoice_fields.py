"""Capture pre-existing-but-untracked custom fields this feature depends on.

Customer.custom_nd_code and Customer/Sales Invoice.bp_sales_person already
exist LIVE on bp.localhost but were never captured in a patch or fixture in
this app's source -- a fresh site (or a new staging/dev site built from this
repo) would NOT have them, silently breaking Import ND Invoice customer
matching and the bp_sales_person -> sales_team sync in
bp.overrides.sales_invoice.validate.

Field definitions below were read directly from the live `tabCustom Field`
table on bp.localhost so this patch reproduces the exact existing layout.

Idempotent: create_custom_fields(update=True) is safe to re-run, and running
it against bp.localhost (where these fields already exist with these exact
values) is a no-op save -- no data change, no field reordering.

Runs post_model_sync, and before this feature's own patches: customer
matching depends on custom_nd_code existing first.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Customer": [
		{
			"fieldname": "bp_sales_person",
			"fieldtype": "Link",
			"label": "Sales Person",
			"options": "Sales Person",
			"insert_after": "territory",
		},
		{
			"fieldname": "custom_section_break_3trm0",
			"fieldtype": "Section Break",
			"label": "",
			"insert_after": "prospect_name",
		},
		{
			"fieldname": "custom_nd_code",
			"fieldtype": "Data",
			"label": "Customer in ND",
			"insert_after": "custom_section_break_3trm0",
			"translatable": 1,
			"description": (
				"Customer code in the ND System. Used to match imported invoice rows "
				"(Import ND Invoice) to this Customer."
			),
		},
	],
	"Sales Invoice": [
		{
			"fieldname": "bp_sales_person",
			"fieldtype": "Link",
			"label": "Sales Person",
			"options": "Sales Person",
			"insert_after": "customer_name",
			"reqd": 1,
			"allow_on_submit": 1,
			"description": (
				"Required. Rebuilds Sales Team (100% allocation) on validate -- see "
				"bp.overrides.sales_invoice.validate."
			),
		},
	],
}


def execute():
	frappe.reload_doctype("Customer")
	frappe.reload_doctype("Sales Invoice")
	create_custom_fields(CUSTOM_FIELDS, update=True)
