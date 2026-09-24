"""Store BP Settings > Enforce Print Once as ON on sites that predate the switch.

The print-once lock was always on before the switch existed; writing the value
explicitly keeps it on and makes the checkbox show ticked. Only fills a
missing value, never overrides one someone already saved.
"""

import frappe


def execute():
	if not frappe.db.sql(
		"select 1 from `tabSingles` where doctype = %s and field = %s", ("BP Settings", "enforce_print_once")
	):
		frappe.db.set_single_value("BP Settings", "enforce_print_once", 1)
