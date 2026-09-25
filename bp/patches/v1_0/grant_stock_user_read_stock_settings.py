"""Let Stock User read Stock Settings.

The Stock Entry form (shown as "Stock Mutation") reads
Stock Settings.sample_retention_warehouse in its setup handler via
frappe.db.get_value. Standard Stock Settings permissions only give read to
Stock Manager (and Sales User), so a warehouse account holding only
Stock User got a "No permission for Stock Settings" popup every time it
opened a new Stock Mutation.

frappe.permissions.add_permission first copies the standard DocPerm rows
into Custom DocPerm (once any Custom DocPerm row exists it fully overrides
the standard ones), then adds a read-only Stock User row, so no existing
role loses access.

Idempotent: the Stock User row is only added when it is missing.
"""

import frappe
from frappe.permissions import add_permission


def execute():
	if not frappe.db.exists(
		"Custom DocPerm", {"parent": "Stock Settings", "role": "Stock User", "permlevel": 0, "if_owner": 0}
	):
		add_permission("Stock Settings", "Stock User", 0)

	frappe.clear_cache(doctype="Stock Settings")
