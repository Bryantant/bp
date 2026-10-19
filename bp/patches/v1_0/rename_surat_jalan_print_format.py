"""Rename the no-price Sales Invoice print format "Surat Jalan" to "Delivery Order"
(Bry 2026-10-19). "Surat Jalan" now means the Delivery Note print "Surat Jalan
Sementara", and Delivery Notes are numbered SJ-, so this print shows DO- + the
invoice number instead of SJ-.

rename_doc updates the Link fields (BP Settings > Print Lock Formats, BP
Warehouse Print); the print history in BP Invoice Print Log keeps the format
name in a Data field, so it is updated here too. Then the template is re-synced.

Idempotent: renames only while "Surat Jalan" exists and "Delivery Order" does not.
"""

import frappe

from bp.patches.v1_0 import create_do_invoice_print_formats

OLD = "Surat Jalan"
NEW = "Delivery Order"


def execute():
	if frappe.db.exists("Print Format", OLD) and not frappe.db.exists("Print Format", NEW):
		frappe.rename_doc("Print Format", OLD, NEW, force=True)
	frappe.db.sql(
		"UPDATE `tabBP Invoice Print Log` SET print_format = %s WHERE print_format = %s", (NEW, OLD)
	)
	create_do_invoice_print_formats.execute()
