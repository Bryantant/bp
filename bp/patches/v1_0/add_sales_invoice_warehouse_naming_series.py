"""Add a Source-Warehouse naming series to Sales Invoice, set as default.

Sales Invoice names via the native "naming_series:" autoname mechanism.
`naming_series` is a core field (not a custom field), so it can't be changed
via create_custom_fields -- the native way to change its `options` is a
Property Setter, which is what this patch creates.

The new series is `warehouse_name_code.YY.MM.####`. "warehouse_name_code" is
not a real fieldname -- it's a custom naming-series token registered via the
`naming_series_variables` hook (see hooks.py and
bp.overrides.sales_invoice.get_warehouse_name_code), which resolves the
invoice's Source Warehouse (set_warehouse) to its clean Warehouse Name (e.g.
"A"), rather than the raw Warehouse Link value (e.g. "A - BP").
Naming-series dots are pure delimiters (stripped when the name is resolved,
never reinserted -- see frappe.model.naming.parse_naming_series), so the
resulting name is a plain, unseparated string like A26070001 (warehouse name
+ 2-digit year + 2-digit month + 4-digit counter).

Inserted as the first line of `options` -- Frappe's naming code treats the
first line as the default naming series when no explicit `default` property
is set (frappe.model.naming.get_default_naming_series) -- while the two
existing series remain selectable for any edge cases (e.g. return invoices).

Idempotent: Property Setter records are keyed by (doctype, fieldname,
property), and PropertySetter.validate() deletes any existing record for
that key before inserting the new one, so re-running this patch just
re-applies the same options string.

Runs post_model_sync: needs the Sales Invoice doctype's metadata already
migrated.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

NAMING_SERIES_OPTIONS = "\n".join(
	[
		"warehouse_name_code.YY.MM.####",
		"ACC-SINV-.YYYY.-",
		"ACC-SINV-RET-.YYYY.-",
	]
)


def execute():
	frappe.reload_doctype("Sales Invoice")
	make_property_setter(
		doctype="Sales Invoice",
		fieldname="naming_series",
		property="options",
		value=NAMING_SERIES_OPTIONS,
		property_type="Text",
	)
