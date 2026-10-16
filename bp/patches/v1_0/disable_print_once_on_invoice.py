"""Printing from the Sales Invoice itself is free again (HT-171, Bry 2026-10-17).

Print-once now lives in the warehouse print queue (bp.warehouse_print). Prints
from the invoice are still logged and counted by bp.overrides.sales_invoice,
only no longer blocked. Runs once per site, so switching the lock back on later
in BP Settings sticks.
"""

import frappe


def execute():
	frappe.db.set_single_value("BP Settings", "enforce_print_once", 0)
