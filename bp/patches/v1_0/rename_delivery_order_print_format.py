"""Rename the no-price Sales Invoice print format "Delivery Order" to "Surat Jalan"
(Bry 2026-10-17; the print shows SJ-<invoice no>), then re-sync both legacy print
formats from bp/templates/print_formats. rename_doc also updates the links to it
(BP Settings > Print Lock Formats).

Idempotent: renames only while "Delivery Order" exists and "Surat Jalan" does not.
"""

import frappe

from bp.patches.v1_0 import create_do_invoice_print_formats

OLD = "Delivery Order"
NEW = "Surat Jalan"


def execute():
	if frappe.db.exists("Print Format", OLD) and not frappe.db.exists("Print Format", NEW):
		frappe.rename_doc("Print Format", OLD, NEW, force=True)
	create_do_invoice_print_formats.execute()
