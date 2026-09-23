"""Make Sales Invoice's Source Warehouse (set_warehouse) mandatory.

Captures in code a rule that was previously applied manually via Customize
Form on bp.localhost (a Property Setter already existed in the site DB but
wasn't exported as a fixture). Required so the warehouse-based naming series
(see add_sales_invoice_warehouse_naming_series.py and
bp.overrides.sales_invoice.get_warehouse_name_code) always has a value to
resolve a naming code from.

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
		fieldname="set_warehouse",
		property="reqd",
		value="1",
		property_type="Check",
	)
