"""Seed default Print Lock Reset Roles in BP Settings.

Keeps behavior identical to the previous hardcoded list (Accounts Manager +
System Manager) the first time the settings doctype is created. Idempotent:
only seeds when the table is empty so an admin's later edits aren't clobbered.
"""

import frappe

DEFAULT_ROLES = ["Accounts Manager"]  # System Manager is always allowed in code


def execute():
	settings = frappe.get_single("BP Settings")
	if settings.get("print_lock_reset_roles"):
		return  # already configured — don't override admin choices

	for role in DEFAULT_ROLES:
		if frappe.db.exists("Role", role):
			settings.append("print_lock_reset_roles", {"role": role})

	settings.save(ignore_permissions=True)
