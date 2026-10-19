"""Point the BP Admin Gudang home page at /desk (v16 desk route).

The role was created with home page "app/bp-warehouse-print". On v16 the desk
lives at /desk, so "/" rendered that path through the website router and showed
"Page not found". Only the old value is replaced; a home page set by hand stays.
"""

import frappe

ROLE = "BP Admin Gudang"
OLD_HOME_PAGE = "app/bp-warehouse-print"
NEW_HOME_PAGE = "desk/bp-warehouse-print"


def execute():
	if frappe.db.get_value("Role", ROLE, "home_page") == OLD_HOME_PAGE:
		frappe.db.set_value("Role", ROLE, "home_page", NEW_HOME_PAGE)
		frappe.cache.delete_key("home_page")
