"""Purchase Invoice: Received By (Diterima Oleh), as in the old receiving dialog.

The old system's receiving form (FmReceDeli) records who took the goods in
(pcrecdor.ReceivBy, free text such as a warehouse name or "TOKO"). Users type
it on each invoice; old documents are not filled.
"""

import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Purchase Invoice": [
		{
			"fieldname": "custom_received_by",
			"fieldtype": "Data",
			"label": "Received By",
			"insert_after": "bill_no",
			"no_copy": 1,
			"allow_on_submit": 1,
			"description": "Who received the goods (Diterima Oleh).",
		}
	]
}


def execute():
	create_custom_fields(CUSTOM_FIELDS, update=True)

	# The form layout saved in Customize Form fixes the field order; place the
	# field there too, under Supplier Invoice No.
	name = frappe.db.get_value(
		"Property Setter", {"doc_type": "Purchase Invoice", "property": "field_order"}
	)
	if not name:
		return
	order = json.loads(frappe.db.get_value("Property Setter", name, "value"))
	if "custom_received_by" in order:
		order.remove("custom_received_by")
	order.insert(order.index("bill_no") + 1, "custom_received_by")
	frappe.db.set_value("Property Setter", name, "value", json.dumps(order))
	frappe.clear_cache(doctype="Purchase Invoice")
