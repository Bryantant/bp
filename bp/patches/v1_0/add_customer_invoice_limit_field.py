"""Add Max Active Invoices field to Customer.

Lets ops cap how many submitted-but-unpaid Sales Invoices a customer may have
open at once (see bp.overrides.sales_invoice.check_active_invoice_limit,
wired via the "before_submit" doc_event). Blank/0 means no limit -- existing
customers aren't retroactively restricted until someone opts them in by
setting a number.

Idempotent: create_custom_fields(update=True) is safe to re-run.

Runs post_model_sync: Custom Field creation needs the Customer doctype's
metadata already migrated.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Customer": [
		{
			"fieldname": "custom_max_active_invoices",
			"fieldtype": "Int",
			"label": "Max Active Invoices",
			"insert_after": "credit_limits",
			"non_negative": 1,
			"description": (
				"Maximum number of submitted invoices allowed to stay unpaid at once for this "
				"customer. Leave blank or 0 for no limit. An invoice counts as active until it "
				"is fully paid."
			),
		},
	]
}


def execute():
	frappe.reload_doctype("Customer")
	create_custom_fields(CUSTOM_FIELDS, update=True)
