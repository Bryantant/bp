"""Force-hide Sales Invoice's naming_series field.

With the warehouse-based series now auto-derived from Source Warehouse (see
add_sales_invoice_warehouse_naming_series.py), users no longer need to pick a
series manually. Mirrors the identical treatment already applied to Purchase
Invoice (Purchase Invoice-naming_series-depends_on = "eval: 0").

Note: this makes the existing "ACC-SINV-RET-.YYYY.-" return series
unreachable via this field, same tradeoff already accepted for Purchase
Invoice's return series -- Frappe still auto-fills the default (first-line)
series on save even though the field is never rendered
(frappe.model.naming.set_name_by_naming_series).

Idempotent: Property Setter records are keyed by (doctype, fieldname,
property), and PropertySetter.validate() deletes any existing record for
that key before inserting the new one.

Runs post_model_sync: needs the Sales Invoice doctype's metadata already
migrated.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	frappe.reload_doctype("Sales Invoice")
	make_property_setter(
		doctype="Sales Invoice",
		fieldname="naming_series",
		property="depends_on",
		value="eval: 0",
		property_type="Data",
	)
