"""Let a Sales Invoice exist without a warehouse, for value-only billing.

Every Sales Invoice here sells goods, so require_sales_invoice_source_warehouse
made Source Warehouse mandatory -- the warehouse-based naming series
(add_sales_invoice_warehouse_naming_series) needs it to resolve a code from.

The old system also bills things that move no goods: an AR debit note
(`invoices` rows numbered D…, InvType 2) charging a principal for promo
claims, rebates or reimbursed salary. In ERP those are Sales Invoices with
Update Stock off and no warehouse, which the two rules above would reject.

So:
- Source Warehouse is mandatory only while the invoice updates stock, which
  is still every goods invoice.
- Value-only invoices get their own series. "NDB" rather than "ND" on
  purpose: Sales Invoice already carries custom_nd_invoice_no, which refers
  to the client's separate ND System, and two meanings of "ND" on one site
  would be read wrong sooner or later.

Idempotent: Property Setters are keyed by (doctype, fieldname, property) and
replaced on re-run.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

WAREHOUSE_SERIES = "warehouse_name_code.YY.MM.####"
NON_STOCK_SERIES = "NDB-.YY.-.####"

NAMING_SERIES_OPTIONS = "\n".join(
	[
		WAREHOUSE_SERIES,
		NON_STOCK_SERIES,
		"ACC-SINV-.YYYY.-",
		"ACC-SINV-RET-.YYYY.-",
	]
)


def execute():
	frappe.reload_doctype("Sales Invoice")

	# reqd wins over mandatory_depends_on, so it has to come off first.
	make_property_setter(
		doctype="Sales Invoice",
		fieldname="set_warehouse",
		property="reqd",
		value="0",
		property_type="Check",
	)
	make_property_setter(
		doctype="Sales Invoice",
		fieldname="set_warehouse",
		property="mandatory_depends_on",
		value="eval:doc.update_stock",
		property_type="Data",
	)
	make_property_setter(
		doctype="Sales Invoice",
		fieldname="naming_series",
		property="options",
		value=NAMING_SERIES_OPTIONS,
		property_type="Text",
	)
