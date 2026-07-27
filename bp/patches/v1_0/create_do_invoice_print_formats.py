"""Create/refresh the "Sales Invoice" and "Delivery Order" Custom HTML/Jinja
Print Formats for Sales Invoice, recreating the client's legacy paper layouts
(see legacy_print_format/*.png) -- one document, two distinct printouts since
this client doesn't use a separate Delivery Note doctype.

HTML/CSS source lives in bp/templates/print_formats/*.html + *.css (real repo
files, not fixtures -- see docs/print-format-rules.md) and is copied verbatim
into the Print Format's html/css fields here (CSS in its own field, not
inlined via <style> in the html), so re-running this patch after editing a
template re-syncs the DB copy.

Idempotent: safe to re-run.
"""

import frappe

FORMATS = [
	{"name": "Sales Invoice", "template": "sales_invoice.html", "style": "sales_invoice.css"},
	{"name": "Delivery Order", "template": "delivery_order.html", "style": "delivery_order.css"},
]


def execute():
	for spec in FORMATS:
		html = frappe.read_file(
			frappe.get_app_path("bp", "templates", "print_formats", spec["template"]),
			raise_not_found=True,
		)
		css = frappe.read_file(
			frappe.get_app_path("bp", "templates", "print_formats", spec["style"]),
			raise_not_found=True,
		)

		if frappe.db.exists("Print Format", spec["name"]):
			pf = frappe.get_doc("Print Format", spec["name"])
		else:
			pf = frappe.new_doc("Print Format")
			pf.name = spec["name"]

		pf.update(
			{
				"doc_type": "Sales Invoice",
				"module": "BP",
				"print_format_type": "Jinja",
				"custom_format": 1,
				"print_format_builder": 0,
				"standard": "No",
				"disabled": 0,
				"pdf_generator": "chrome",
				"page_number": "Hide",
				"margin_top": 10,
				"margin_bottom": 10,
				"margin_left": 10,
				"margin_right": 10,
				"html": html,
				"css": css,
			}
		)
		pf.save(ignore_permissions=True)
