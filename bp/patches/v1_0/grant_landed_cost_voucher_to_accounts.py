"""Let the accounting team book freight and duties with Landed Cost Voucher.

Decision: freight and import duties go into the item's cost through Landed
Cost Voucher (not straight to expense). Purchase Invoices are created by
Accounts User / Accounts Manager, but standard Landed Cost Voucher
permissions only cover Stock Manager, so the people who receive the freight
bill could not allocate it.

add_permission() first copies the standard rows into Custom DocPerm (see
lesson 46/84), so Stock Manager keeps its access.

Idempotent: rows are added once, rights are (re)set on every run.
"""

import frappe
from frappe.permissions import add_permission, update_permission_property

ROLES = ("Accounts User", "Accounts Manager")
RIGHTS = ("read", "write", "create", "submit", "cancel", "amend", "report", "print")


def execute():
	for role in ROLES:
		if not frappe.db.exists(
			"Custom DocPerm",
			{"parent": "Landed Cost Voucher", "role": role, "permlevel": 0, "if_owner": 0},
		):
			add_permission("Landed Cost Voucher", role, 0)
		for right in RIGHTS:
			update_permission_property("Landed Cost Voucher", role, 0, right, 1, validate=False)

	frappe.clear_cache(doctype="Landed Cost Voucher")
