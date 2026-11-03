"""Create the "Payment Entry" print format (A4): the Payment Entry as ERP holds it (its own
sections and labels), with the header, fonts and bottom block of the legacy prints, and make it the
Default Print Format of Payment Entry (Bry, 2026-11-04). "Payment Note" (the Access receipt/payment
note layout) stays available in the Print dialog.
Template in bp/templates/print_formats/payment_entry.html + .css.

Idempotent: re-running re-syncs the DB copy from the template files and re-sets the default.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from bp.patches.v1_0.create_do_invoice_print_formats import upsert


def execute():
	upsert([{"name": "Payment Entry", "doc_type": "Payment Entry", "template": "payment_entry.html", "style": "payment_entry.css"}])
	make_property_setter("Payment Entry", None, "default_print_format", "Payment Entry", "Data", for_doctype=True)
	frappe.clear_cache()
