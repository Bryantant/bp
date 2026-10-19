"""Create/refresh the "Surat Jalan Sementara" print format for Delivery Note and
make it the default (Bry 2026-10-19), recreating the old Surat Jalan Sementara
print (Access report PrtDOSForm). Source in
bp/templates/print_formats/surat_jalan_sementara.html + .css.

Idempotent: safe to re-run after editing the template.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from bp.patches.v1_0.create_do_invoice_print_formats import upsert

FORMAT = {
	"name": "Surat Jalan Sementara",
	"doc_type": "Delivery Note",
	"template": "surat_jalan_sementara.html",
	"style": "surat_jalan_sementara.css",
}


def execute():
	upsert([FORMAT])
	make_property_setter(
		"Delivery Note", None, "default_print_format", FORMAT["name"], "Data", for_doctype=True
	)
	frappe.clear_cache(doctype="Delivery Note")
