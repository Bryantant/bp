"""Update Titik Koordinat field to document Google Maps link support.

custom_titik_koordinat now also accepts a Google Maps link (a short share
link or a full URL) in addition to a raw "latitude,longitude" pair -- see
public/js/customer.js and bp.overrides.customer.resolve_maps_link. This patch
only updates the field's label/description to reflect that; no schema change
is needed since it was always a plain Data field.

Idempotent: create_custom_fields(update=True) is safe to re-run.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Customer": [
		{
			"fieldname": "custom_titik_koordinat",
			"fieldtype": "Data",
			"label": "Titik Koordinat / Link Google Maps",
			"insert_after": "custom_section_lokasi",
			"description": (
				'Paste coordinates as "latitude,longitude" (e.g. -6.2088,106.8456), '
				"or paste a Google Maps link -- a share link (maps.app.goo.gl/...) copied "
				"from the Maps app, or the full URL from a browser address bar."
			),
		},
	]
}


def execute():
	frappe.reload_doctype("Customer")
	create_custom_fields(CUSTOM_FIELDS, update=True)
