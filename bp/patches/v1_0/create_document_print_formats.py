"""Create/refresh the legacy-layout print formats for the buying, stock and
accounting documents (recreating the legacy Access prints PrtPOForm,
PrtRDOForm, PrtStockMut*, PrtRNForm/PrtPNForm, PrtCRNForm/PrtCPNForm) and make
the first one per doctype its Default Print Format. HTML/CSS live in
bp/templates/print_formats (see docs/print-format-rules.md).

Idempotent: safe to re-run after editing a template.
"""

import os

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from bp.patches.v1_0.create_do_invoice_print_formats import upsert

# The first format of each doctype becomes its Default Print Format. Purchase
# Invoice and Stock Entry default to the no-price variant, as the legacy prints
# did unless "Cetak Harga" / "Print Price" was ticked.
FORMATS = [
	{"name": "Purchase Order", "doc_type": "Purchase Order", "template": "purchase_order.html", "style": "purchase_order.css"},
	{"name": "Penerimaan Barang", "doc_type": "Purchase Invoice", "template": "penerimaan_barang.html", "style": "penerimaan_barang.css"},
	{"name": "Penerimaan Barang Harga", "doc_type": "Purchase Invoice", "template": "penerimaan_barang_harga.html", "style": "penerimaan_barang_harga.css"},
	{"name": "Mutasi Barang", "doc_type": "Stock Entry", "template": "mutasi_barang.html", "style": "mutasi_barang.css"},
	{"name": "Mutasi Barang Harga", "doc_type": "Stock Entry", "template": "mutasi_barang_harga.html", "style": "mutasi_barang_harga.css"},
	{"name": "Payment Note", "doc_type": "Payment Entry", "template": "payment_note.html", "style": "payment_note.css"},
	{"name": "Journal Voucher", "doc_type": "Journal Entry", "template": "journal_voucher.html", "style": "journal_voucher.css"},
]


def execute():
	folder = frappe.get_app_path("bp", "templates", "print_formats")
	ready = [s for s in FORMATS if os.path.exists(os.path.join(folder, s["template"]))]
	upsert(ready)
	done = set()
	for spec in ready:
		if spec["doc_type"] in done:
			continue
		done.add(spec["doc_type"])
		make_property_setter(spec["doc_type"], None, "default_print_format", spec["name"], "Data", for_doctype=True)
	frappe.clear_cache()
