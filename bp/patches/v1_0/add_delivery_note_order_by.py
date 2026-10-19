"""Delivery Note: Order By (Pemesan), as on the old Surat Jalan Sementara form.

The old form (FmDOCon, docon.OrderByx, free text up to 20 characters) holds who
at the customer placed the order, often the site or department ("ATLAS COPCO
BATAM WS"); about 85% of the slips since 2024 carry it. It prints as "Order By"
on the Surat Jalan Sementara print format. Same fieldname and label as the
Sales Invoice field (add_sales_invoice_order_by_field), so the value carries
over when one document is made from the other.

The form layout saved in Customize Form fixes the field order, so the field is
also placed there, under Customer's Purchase Order No.

Idempotent: create_custom_fields(update=True) and a field_order insert that
skips a field already in place.
"""

import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ANCHOR = "po_no"
FIELD = "custom_order_by"

CUSTOM_FIELDS = {
	"Delivery Note": [
		{
			"fieldname": FIELD,
			"fieldtype": "Data",
			"label": "Order By",
			"insert_after": ANCHOR,
			"description": "Printed on the Surat Jalan Sementara print format.",
		}
	]
}


def execute():
	create_custom_fields(CUSTOM_FIELDS, update=True)

	name = frappe.db.get_value("Property Setter", {"doc_type": "Delivery Note", "property": "field_order"})
	if name:
		order = json.loads(frappe.db.get_value("Property Setter", name, "value"))
		if FIELD in order:
			order.remove(FIELD)
		order.insert(order.index(ANCHOR) + 1, FIELD)
		frappe.db.set_value("Property Setter", name, "value", json.dumps(order))
	frappe.clear_cache(doctype="Delivery Note")
