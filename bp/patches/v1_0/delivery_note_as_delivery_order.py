"""Delivery Note is called "Delivery Order" on screen and numbered DO- (Bry 2026-11-03).

  - Translation (language en, as the site's "Salesman" for Sales Person) of every label that says Delivery Note.
    The DocType itself stays "Delivery Note": only what the user reads changes.
  - Delivery Note series: DO-<warehouse code>.YY.MM.#### is the default (SJ- was the default before; both stay
    in the list for earlier documents).
Idempotent.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

TRANSLATIONS = {
	"Delivery Note": "Delivery Order",
	"Delivery Notes": "Delivery Orders",
	"Delivery Note Item": "Delivery Order Item",
	"Delivery Note Trends": "Delivery Order Trends",
	"Return Against Delivery Note": "Return Against Delivery Order",
	"Against Delivery Note Item": "Against Delivery Order Item",
	"Update Billed Amount in Delivery Note": "Update Billed Amount in Delivery Order",
	"Skip Delivery Note": "Skip Delivery Order",
}
DO_SERIES = "DO-.warehouse_name_code.YY.MM.####"


def execute():
	for source, target in TRANSLATIONS.items():
		name = frappe.db.get_value("Translation", {"language": "en", "source_text": source})
		if name:
			frappe.db.set_value("Translation", name, "translated_text", target)
		else:
			frappe.get_doc(
				{"doctype": "Translation", "language": "en", "source_text": source, "translated_text": target}
			).insert(ignore_permissions=True)

	options = frappe.db.get_value(
		"Property Setter", {"doc_type": "Delivery Note", "field_name": "naming_series", "property": "options"}, "value"
	) or "\n".join(
		d for d in (frappe.get_meta("Delivery Note").get_field("naming_series").options or "").split("\n") if d
	)
	rest = [o for o in options.split("\n") if o and o != DO_SERIES]
	make_property_setter(
		"Delivery Note", "naming_series", "options", "\n".join([DO_SERIES] + rest), "Text"
	)
	make_property_setter("Delivery Note", "naming_series", "default", DO_SERIES, "Text")
	frappe.clear_cache()
