"""Backfill Customer custom fields that existed live but were never captured
in source.

These three fields were created directly on the bp.localhost site and are
missing from every patch and fixture in this app, so a fresh site build from
this repo would come up without them:

- custom_cn_initial: read by INITIAL_FIELD in bp.overrides.naming to generate
  Customer/Supplier names (e.g. C0276); populated client-side from the first
  letter of customer_name by the "Client Script" fixture. Without it,
  Customer autoname throws.
- custom_customer_sejak: a free-standing Date field; no other code depends
  on it.
- custom_salesman: the "Sales Team" section break. It is also the
  insert_after anchor that bp.patches.v1_0.add_customer_location_fields
  relies on for custom_section_lokasi, so this patch must run before that
  one (see patches.txt) or that field lands in the wrong position on a
  fresh site.

Idempotent: create_custom_fields(update=True) is safe to re-run.

Runs post_model_sync: Custom Field creation needs the Customer doctype's
metadata already migrated.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Customer": [
		{
			"fieldname": "custom_cn_initial",
			"fieldtype": "Data",
			"label": "cn_initial",
			"insert_after": "naming_series",
			"length": 1,
			"hidden": 1,
			"read_only": 1,
			"translatable": 1,
		},
		{
			"fieldname": "custom_customer_sejak",
			"fieldtype": "Date",
			"label": "Customer Sejak",
			"insert_after": "customer_group",
		},
		{
			"fieldname": "custom_salesman",
			"fieldtype": "Section Break",
			"label": "Sales Team",
			"insert_after": "image",
		},
	]
}


def execute():
	frappe.reload_doctype("Customer")
	create_custom_fields(CUSTOM_FIELDS, update=True)
