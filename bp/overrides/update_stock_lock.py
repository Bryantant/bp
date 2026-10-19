"""Update Stock is fixed once an invoice is saved (Bry 2026-10-19).

The name is given on the first save from Update Stock (INV-/SR- with a warehouse
code for goods, ND-/AR-NC- without, see before_naming in sales_invoice.py and
purchase_invoice.py). Flipping the flag on a saved draft would leave a goods
invoice under a non-goods number or the other way round, so it may only be set
while the document is new. public/js/update_stock_lock.js makes the checkbox read
only in the form; this check also covers API and Data Import.
"""

import frappe
from frappe import _
from frappe.utils import cint


def validate(doc, method=None):
	if doc.is_new() or not doc.meta.has_field("update_stock"):
		return

	before = doc.get_doc_before_save()
	if before and cint(before.get("update_stock")) != cint(doc.get("update_stock")):
		frappe.throw(
			_("Update Stock cannot be changed after the document is saved. Delete this draft and create a new one."),
			title=_("Update Stock Locked"),
		)
