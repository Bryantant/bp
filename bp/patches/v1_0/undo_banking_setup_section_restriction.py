"""Undo the System-Manager-only restriction for the "Setup" child menu of the
Banking workspace sidebar.

restrict_banking_doctypes_to_system_manager.py restricted all 12 Banking
sidebar links, including the "Setup" section-break's children (Bank, Bank
Account, Bank Account Type, Bank Account Subtype, Bank Guarantee, Plaid
Settings). Bry asked to undo it for just that subset — removing their
Custom DocPerm rows restores the standard (JSON-defined) role permissions
that applied before that patch ran. The rest of the Banking sidebar (Bank
Clearance, Bank Reconciliation Tool, Unreconcile Payment, Process Payment
Reconciliation, Dunning, Dunning Type) stays restricted.

Idempotent: deleting rows that don't exist is a no-op.
"""

import frappe

DOCTYPES_TO_UNRESTRICT = [
	"Bank",
	"Bank Account",
	"Bank Account Type",
	"Bank Account Subtype",
	"Bank Guarantee",
	"Plaid Settings",
]


def execute():
	for doctype in DOCTYPES_TO_UNRESTRICT:
		frappe.db.delete("Custom DocPerm", {"parent": doctype, "role": "System Manager"})

	frappe.clear_cache()
