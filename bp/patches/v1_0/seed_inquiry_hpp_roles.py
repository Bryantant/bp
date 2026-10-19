"""Seed default Inquiry HPP Roles in BP Settings.

The Inquiry page's HPP column shows the item's cost (valuation rate). In the old
program only users with "Inquiry Harga Pokok" (N0911) saw it: admins, the
supervisor and the purchasing staff, never the sales admins (Bry, 2026-10-19).
Start with the same roles as the Purchase tab; System Manager always sees it,
in code.

Idempotent: only seeds when the table is empty, so later edits stay.
"""

import frappe

from bp.patches.v1_0.seed_inquiry_purchase_roles import DEFAULT_ROLES


def execute():
	settings = frappe.get_single("BP Settings")
	if settings.get("inquiry_hpp_roles"):
		return

	for role in DEFAULT_ROLES:
		if frappe.db.exists("Role", role):
			settings.append("inquiry_hpp_roles", {"role": role})

	settings.save(ignore_permissions=True)
