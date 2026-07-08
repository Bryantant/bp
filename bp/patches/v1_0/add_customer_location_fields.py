"""Add Titik Koordinat (GPS coordinate) fields to Customer.

Adds a Data field storing "latitude,longitude" -- the exact string format
Google Maps gives when copying coordinates from a long-pressed pin -- plus an
HTML field used purely as a client-side rendering target for the map preview
and "Open in Google Maps" action (see public/js/customer.js). This app no
longer uses fixtures for custom fields, so they are created here in code.

Idempotent: create_custom_fields(update=True) updates any existing field
matching (dt, fieldname) instead of duplicating it, so this patch is safe to
re-run.

Runs post_model_sync: Custom Field creation needs the Customer doctype's
metadata already migrated.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Customer": [
		{
			"fieldname": "custom_section_lokasi",
			"fieldtype": "Section Break",
			"label": "Store Location",
			"insert_after": "custom_salesman",
		},
		{
			"fieldname": "custom_titik_koordinat",
			"fieldtype": "Data",
			"label": "Titik Koordinat (Lat,Lng)",
			"insert_after": "custom_section_lokasi",
			"description": (
				"Paste directly from Google Maps: long-press the store location on the map, "
				"tap the coordinates that appear to copy them, then paste here. "
				"Format: latitude,longitude (e.g. -6.2088,106.8456)."
			),
		},
		{
			"fieldname": "custom_peta_lokasi",
			"fieldtype": "HTML",
			"label": "Peta Lokasi",
			"insert_after": "custom_titik_koordinat",
			"depends_on": "eval:doc.custom_titik_koordinat",
			"read_only": 1,
		},
	]
}


def execute():
	frappe.reload_doctype("Customer")
	create_custom_fields(CUSTOM_FIELDS, update=True)
