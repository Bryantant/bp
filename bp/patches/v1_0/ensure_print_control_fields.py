"""Recreate the Sales Invoice print control fields when a site lacks them.

They used to come from fixtures/custom_field.json, which was dropped with the
move away from fixture-based customization, so a fresh site would miss them
while bp.overrides.sales_invoice and the invoice print formats still use them.
Idempotent: create_custom_fields only adds what is missing.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

_AUDIT = {"read_only": 1, "allow_on_submit": 1, "no_copy": 1, "print_hide": 1}

FIELDS = {
	"Sales Invoice": [
		{
			"fieldname": "bp_print_control_section",
			"fieldtype": "Section Break",
			"label": "Print Control",
			"insert_after": "against_income_account",
			"collapsible": 1,
			"print_hide": 1,
		},
		{
			"fieldname": "bp_print_status",
			"fieldtype": "Select",
			"label": "Print Status",
			"options": "Not Printed\nPrinted",
			"default": "Not Printed",
			"insert_after": "bp_print_control_section",
			**_AUDIT,
		},
		{
			"fieldname": "bp_print_count",
			"fieldtype": "Int",
			"label": "Print Count",
			"default": "0",
			"insert_after": "bp_print_status",
			**_AUDIT,
		},
		{
			"fieldname": "bp_print_control_cb",
			"fieldtype": "Column Break",
			"insert_after": "bp_print_count",
			"print_hide": 1,
		},
		{
			"fieldname": "bp_last_printed_by",
			"fieldtype": "Link",
			"label": "Last Printed By",
			"options": "User",
			"insert_after": "bp_print_control_cb",
			**_AUDIT,
		},
		{
			"fieldname": "bp_last_printed_at",
			"fieldtype": "Datetime",
			"label": "Last Printed At",
			"insert_after": "bp_last_printed_by",
			**_AUDIT,
		},
	]
}


def execute():
	create_custom_fields(FIELDS, ignore_validate=True, update=False)
