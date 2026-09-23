"""Add Invoice Type (Cash/Credit) field to Purchase Invoice.

Lets each Purchase Invoice record whether it's a Cash or Credit purchase.
Required so the Cash/Credit naming series (see
add_purchase_invoice_cash_credit_naming_series.py and
bp.overrides.purchase_invoice.get_invoice_type_code) always has a value to
resolve a naming code from.

Idempotent: create_custom_fields(update=True) is safe to re-run.

Runs post_model_sync: Custom Field creation needs the Purchase Invoice
doctype's metadata already migrated.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Purchase Invoice": [
		{
			"fieldname": "custom_invoice_type",
			"fieldtype": "Select",
			"label": "Invoice Type",
			"options": "Cash\nCredit",
			"insert_after": "naming_series",
			"reqd": 1,
		},
	]
}


def execute():
	frappe.reload_doctype("Purchase Invoice")
	create_custom_fields(CUSTOM_FIELDS, update=True)
