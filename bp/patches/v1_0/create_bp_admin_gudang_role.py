"""Role for the warehouse admin who prints from the BP Warehouse Print queue (HT-171).

The role gets desk access and lands on the queue. It is deliberately not given
Sales Invoice access: printing from the invoice itself is free, so a warehouse
admin who could open invoices could bypass the print-once queue.

Idempotent: creates the role if missing and only fills an empty home page.
"""

import frappe

ROLE = "BP Admin Gudang"
HOME_PAGE = "app/bp-warehouse-print"


def execute():
	if not frappe.db.exists("Role", ROLE):
		frappe.get_doc(
			{"doctype": "Role", "role_name": ROLE, "desk_access": 1, "home_page": HOME_PAGE}
		).insert(ignore_permissions=True)
		return
	role = frappe.get_doc("Role", ROLE)
	role.desk_access = 1
	if not role.home_page:
		role.home_page = HOME_PAGE
	role.save(ignore_permissions=True)
