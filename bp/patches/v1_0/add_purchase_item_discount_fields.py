"""Price and discount fields on Purchase Invoice Item and Purchase Order Item,
the same way as on Sales Invoice Item.

Bry's decision (2026-10-19): purchases use the Sales Invoice mechanism with
two steps only, as in the old receiving form (pcrddeta.DiscPerc, DiscAmt):

	Price List Rate -> % Disk 1 -> Disk 1 = Rate

The fields share their names with the sales side, so bp.utils.cascading_discount
and bp.discounts (discount_utils.bundle.js) work unchanged; the missing
Disk 2 fields read as 0. Price List Rate is what the user types or what
bp.utils.last_purchase_price fills; Rate and the core Discount (%) /
Discount Amount follow from the steps and are read only, as on Sales Invoice.

Idempotent: create_custom_fields(update=True) and make_property_setter
replace what is there.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from bp.patches.v1_0.add_item_cascading_discount_fields import DISCOUNT_FIELDS

DOCTYPES = ("Purchase Invoice Item", "Purchase Order Item")

PROPERTIES = [
	# (fieldname, property, value, property_type)
	("custom_discount1_percentage", "label", "% Disk 1", "Data"),
	("custom_discount1_percentage", "in_list_view", 1, "Check"),
	("custom_discount1_percentage", "columns", 1, "Int"),
	("custom_discount1_amount", "label", "Disk 1", "Data"),
	("custom_discount1_amount", "in_list_view", 1, "Check"),
	("custom_discount1_amount", "columns", 2, "Int"),
	("price_list_rate", "in_list_view", 1, "Check"),
	("rate", "in_list_view", 0, "Check"),
	("rate", "read_only", 1, "Check"),
	("discount_percentage", "read_only", 1, "Check"),
	("discount_amount", "read_only", 1, "Check"),
	("discount_and_margin", "hidden", 0, "Check"),
]


def execute():
	create_custom_fields({dt: DISCOUNT_FIELDS[:2] for dt in DOCTYPES}, update=True)
	for doctype in DOCTYPES:
		for fieldname, prop, value, prop_type in PROPERTIES:
			make_property_setter(
				doctype, fieldname, prop, value, prop_type, validate_fields_for_doctype=False
			)
		frappe.clear_cache(doctype=doctype)
