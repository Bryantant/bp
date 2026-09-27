"""Add two-tier cascading discount fields to Sales Invoice Item and Sales
Order Item.

Discount 1 is the supplier-side/claimable discount (a rebate the company can
later claim back from the item's supplier); Discount 2 is the internal
company-policy discount. The four fields are four separate steps, each
applied to the price left by the one before it: Discount 1 %, Discount 1
Amount, Discount 2 %, Discount 2 Amount (bp.utils.cascading_discount, wired
via the "before_validate" doc_event). A percentage and the amount next to it
are not one discount typed two ways. The native
rate/discount_percentage/discount_amount fields are recomputed from these as
the effective combined discount -- bp/templates/print_formats/
sales_invoice.html still renders discount_percentage/discount_amount as-is.

custom_ prefix: this logic is new and not backed by any pre-existing field
(same reasoning as add_sales_invoice_order_by_field.py).

No precision set on the Percent/Currency fields -- they inherit the same
system Float/Currency precision as the native discount_percentage/
discount_amount/price_list_rate fields they are kept in sync with, avoiding
rounding drift between them.

No no_copy -- so "Make Sales Invoice" (Sales Order -> Sales Invoice mapping)
carries these fields over automatically via Frappe's default field-name
matching in frappe.model.mapper.

Idempotent: create_custom_fields(update=True) is safe to re-run.

Runs post_model_sync: Custom Field creation needs both doctypes' metadata
already migrated.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

DISCOUNT_FIELDS = [
	{
		"fieldname": "custom_discount1_percentage",
		"fieldtype": "Percent",
		"label": "Discount 1 %",
		"insert_after": "discount_amount",
		"description": "Step 1: percentage off the Price List Rate.",
	},
	{
		"fieldname": "custom_discount1_amount",
		"fieldtype": "Currency",
		"label": "Discount 1 Amount",
		"insert_after": "custom_discount1_percentage",
		"options": "currency",
		"description": "Step 2: amount per unit off the price after Discount 1 %.",
	},
	{
		"fieldname": "custom_discount2_percentage",
		"fieldtype": "Percent",
		"label": "Discount 2 %",
		"insert_after": "custom_discount1_amount",
		"description": "Step 3: percentage off the price after Discount 1.",
	},
	{
		"fieldname": "custom_discount2_amount",
		"fieldtype": "Currency",
		"label": "Discount 2 Amount",
		"insert_after": "custom_discount2_percentage",
		"options": "currency",
		"description": "Step 4: amount per unit off the price after Discount 2 %.",
	},
]

CUSTOM_FIELDS = {
	"Sales Invoice Item": DISCOUNT_FIELDS,
	"Sales Order Item": DISCOUNT_FIELDS,
}


def execute():
	frappe.reload_doctype("Sales Invoice Item")
	frappe.reload_doctype("Sales Order Item")
	create_custom_fields(CUSTOM_FIELDS, update=True)
