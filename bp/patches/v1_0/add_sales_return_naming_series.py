"""Give sales returns their own naming series.

Sales Invoices that move stock are named from the warehouse
(warehouse_name_code.YY.MM.####, e.g. A26090001). Returns update stock too, so
without this they were numbered in the same series as sales and could not be
told apart by name. They now get an R in front, with their own counter:
RA26090001.

The series is picked in bp.overrides.sales_invoice.before_naming for any
return that updates stock -- imported by Legacy Import or made by hand -- so
both paths name them the same way.

The warehouse series stays FIRST: Frappe uses the first option as the
default, and before_naming only replaces that default.

Idempotent: the Property Setter is keyed by (doctype, fieldname, property)
and replaced on re-run.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from bp.patches.v1_0.allow_non_stock_sales_invoices import NON_STOCK_SERIES, WAREHOUSE_SERIES

RETURN_SERIES = "R.warehouse_name_code.YY.MM.####"

NAMING_SERIES_OPTIONS = "\n".join(
	[
		WAREHOUSE_SERIES,
		RETURN_SERIES,
		NON_STOCK_SERIES,
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
