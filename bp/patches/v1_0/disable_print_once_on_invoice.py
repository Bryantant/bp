"""Printing from the Sales Invoice is always free (HT-171, Bry 2026-10-17).

Print-once lives only in the warehouse print queue (bp.warehouse_print), and
the BP Settings > Enforce Print Once switch was removed. Drop its stored value
so nothing can read a stale 1 from tabSingles.
"""

import frappe


def execute():
	frappe.db.delete("Singles", {"doctype": "BP Settings", "field": "enforce_print_once"})
