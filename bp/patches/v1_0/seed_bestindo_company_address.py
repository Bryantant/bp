"""Create the Company's own Address record if none exists yet.

Confirmed live on bp.localhost (2026-07-21): no Address is linked to Company
"PT. Bestindo Persada" at all, so Sales Invoice.company_address never
resolves and the legacy-style print formats' header address block would be
blank. Populates from the legacy paper layout (legacy_print_format/Sales
Invoice.png / Delivery Order.png).

Idempotent: does nothing if an is_your_company_address=1 Address linked to
this Company already exists.
"""

import frappe

COMPANY = "PT. Bestindo Persada"


def execute():
	linked = frappe.get_all(
		"Dynamic Link",
		filters={"link_doctype": "Company", "link_name": COMPANY, "parenttype": "Address"},
		pluck="parent",
	)
	for address in linked:
		if frappe.db.get_value("Address", address, "is_your_company_address"):
			return  # already set up

	frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": COMPANY,
			"address_type": "Office",
			"address_line1": "Union Industrial Park Blok D1 No.07",
			"address_line2": "Batu Ampar",
			"city": "Batam",
			"pincode": "29432",
			"country": "Indonesia",
			# Address.phone is fieldtype "Phone" -- Frappe validates it against
			# PHONE_NUMBER_PATTERN (digits/space/+/-/,/./*/#/parens only, <=20
			# chars), which rejects the legacy text verbatim ("... / 7480501
			# (Hunting)" has letters, a slash, and is too long). Storing the
			# primary number only; the secondary "hunting line" extension
			# isn't representable here without a custom field -- ask Bry if
			# that detail needs to be preserved.
			"phone": "(0778) 743 7488",
			"fax": "(0778) 743 7489",
			"is_your_company_address": 1,
			"links": [{"link_doctype": "Company", "link_name": COMPANY}],
		}
	).insert(ignore_permissions=True)
