"""Give sales admins and the accounting team access to Stock Mutation (Stock Entry).

DIPIN, WhatsApp 2026-10-08 (task HT-8): sales admins may relocate stock,
the accounting team may use every Stock Entry type. Standard permissions only
cover Stock and Manufacturing roles, so neither group could open it. The type
restriction for sales lives in bp/overrides/stock_entry.py.

No delete right: staff may cancel and amend their own documents, delete
stays with System Manager (Bry, 2026-09-27). Stock Entry Type gets read
access, otherwise the type field cannot be filled.

add_permission() first copies the standard rows into Custom DocPerm (see
lesson 46/84), so Stock and Manufacturing roles keep their access.

Idempotent: rows are added once, rights are (re)set on every run.
"""

import frappe
from frappe.permissions import add_permission, update_permission_property

ROLES = ("Sales User", "Accounts User", "Accounts Manager")
STOCK_ENTRY_RIGHTS = ("read", "write", "create", "submit", "cancel", "amend", "report", "print")


def execute():
	for doctype, rights in (("Stock Entry", STOCK_ENTRY_RIGHTS), ("Stock Entry Type", ("read",))):
		for role in ROLES:
			if not frappe.db.exists(
				"Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0}
			):
				add_permission(doctype, role, 0)
			for right in rights:
				update_permission_property(doctype, role, 0, right, 1, validate=False)
		frappe.clear_cache(doctype=doctype)
