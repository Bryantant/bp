"""Swap the names of the two goods-out print formats (Bry 2026-11-03: the names were the wrong way round).

  Sales Invoice  no-price print : "Delivery Order"        -> "Surat Jalan"
  Delivery Note  print          : "Surat Jalan Sementara" -> "Delivery Order"

The templates stay delivery_order.html (Sales Invoice) and surat_jalan_sementara.html (Delivery Note); only the
Print Format names change. frappe.rename_doc follows the Link fields (BP Settings > Warehouse Print Formats,
BP Warehouse Print). The default print format of Delivery Note and the Data field print_format of the BP Invoice
Print Log (history of the Sales Invoice print) are moved here. Idempotent.

To refresh these two prints from their templates use SPECS below (the older patches still carry the old names).
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

SPECS = [
	{"name": "Surat Jalan", "doc_type": "Sales Invoice", "template": "delivery_order.html", "style": "delivery_order.css"},
	{
		"name": "Delivery Order",
		"doc_type": "Delivery Note",
		"template": "surat_jalan_sementara.html",
		"style": "surat_jalan_sementara.css",
	},
]


def execute():
	# 1. Sales Invoice print: Delivery Order -> Surat Jalan (the name is free, "Surat Jalan" went to Delivery Order on 2026-10-19)
	if (
		frappe.db.exists("Print Format", {"name": "Delivery Order", "doc_type": "Sales Invoice"})
		and not frappe.db.exists("Print Format", "Surat Jalan")
	):
		frappe.rename_doc("Print Format", "Delivery Order", "Surat Jalan", force=True)
		if frappe.db.table_exists("BP Invoice Print Log"):
			frappe.db.sql(
				"update `tabBP Invoice Print Log` set print_format = 'Surat Jalan' where print_format = 'Delivery Order'"
			)

	# 2. Delivery Note print: Surat Jalan Sementara -> Delivery Order
	if (
		frappe.db.exists("Print Format", {"name": "Surat Jalan Sementara", "doc_type": "Delivery Note"})
		and not frappe.db.exists("Print Format", "Delivery Order")
	):
		frappe.rename_doc("Print Format", "Surat Jalan Sementara", "Delivery Order", force=True)

	if frappe.db.exists("Print Format", {"name": "Delivery Order", "doc_type": "Delivery Note"}):
		make_property_setter("Delivery Note", None, "default_print_format", "Delivery Order", "Data", for_doctype=True)

	frappe.clear_cache()
