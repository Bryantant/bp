"""Restore standard role access to Payment Order.

Payment Order was locked to System Manager only via a manual Custom DocPerm
edit made outside any tracked patch (2026-07-29, same day as the banking
restriction patches but not recorded in one). The BP Feature Scope sheet
(https://docs.google.com/spreadsheets/d/11csjs1Hu1-cWYQnfgUQHuJ4Q0z9bmB4ibX0xgR_51Vw,
gid 697742285) marks Payment Order as an "orange" row — unresolved but to be
treated as in-scope — so that manual lock is reversed here, the same way
undo_banking_setup_section_restriction.py reversed part of the banking
restriction: delete the System Manager Custom DocPerm row so the standard
(JSON-defined) permissions apply again (Accounts User, Accounts Manager).

Idempotent: deleting a row that doesn't exist is a no-op.
"""

import frappe


def execute():
	frappe.db.delete("Custom DocPerm", {"parent": "Payment Order", "role": "System Manager"})

	frappe.clear_cache()
