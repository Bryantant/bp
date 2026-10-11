"""Seed default Inquiry Purchase Roles in BP Settings.

The Inquiry page's Purchase tab shows purchase prices and suppliers. Until the
client decides whether sales staff may see it, only buying, stock and
accounting roles get it (System Manager always does, in code). Adding
"Sales User" here later opens it to sales without a code change.

Idempotent: only seeds when the table is empty, so later edits stay.
"""

import frappe

DEFAULT_ROLES = [
	"Purchase User",
	"Purchase Manager",
	"Stock User",
	"Stock Manager",
	"Accounts User",
	"Accounts Manager",
]


def execute():

	settings = frappe.get_single("BP Settings")
	if settings.get("inquiry_purchase_roles"):
		return

	for role in DEFAULT_ROLES:
		if frappe.db.exists("Role", role):
			settings.append("inquiry_purchase_roles", {"role": role})

	settings.save(ignore_permissions=True)
