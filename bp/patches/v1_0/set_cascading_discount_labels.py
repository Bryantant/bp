"""Show the four discount steps with the same short labels on Sales Order and Sales Invoice.

Bry's decision (2026-09-27): item discount is four cascading steps, labelled
"% Disk 1", "Disk 1", "% Disk 2", "Disk 2" and shown in the item grid. On
bp.localhost these labels were set by hand as Property Setters on Sales
Invoice Item only, so Sales Order Item still showed "Discount 1 %" etc. and
neither reached the repo (task HT-24).

Both item tables get the same labels, grid visibility and widths, so a
Sales Order and the invoice made from it look the same.

Idempotent: Property Setter records are keyed by (doctype, fieldname,
property) and make_property_setter replaces an existing one.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

DOCTYPES = ("Sales Invoice Item", "Sales Order Item")

FIELDS = [
	# (fieldname, label, grid columns)
	("custom_discount1_percentage", "% Disk 1", 1),
	("custom_discount1_amount", "Disk 1", 2),
	("custom_discount2_percentage", "% Disk 2", 1),
	("custom_discount2_amount", "Disk 2", 2),
]


def execute():
	for doctype in DOCTYPES:
		for fieldname, label, columns in FIELDS:
			if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname}):
				continue
			for prop, value, prop_type in (
				("label", label, "Data"),
				("in_list_view", 1, "Check"),
				("columns", columns, "Int"),
			):
				make_property_setter(
					doctype,
					fieldname,
					prop,
					value,
					prop_type,
					validate_fields_for_doctype=False,
				)
		frappe.clear_cache(doctype=doctype)
