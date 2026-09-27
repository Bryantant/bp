"""Enable the CTN unit again.

Many legacy prices and conversions are stored per CTN (carton), e.g.
BEV-00253 1 CTN = 24 PCS. With the UOM disabled those rows could not be
picked in transactions and items priced only in CTN looked unpriced.

Idempotent.
"""

import frappe


def execute():
	if frappe.db.exists("UOM", "CTN"):
		frappe.db.set_value("UOM", "CTN", "enabled", 1)
