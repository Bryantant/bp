"""Stock Mutation (Stock Entry) rules by role.

DIPIN confirmed on WhatsApp 2026-10-08 (task HT-8): sales admins may only
relocate stock between warehouses; the accounting team may use every type.
A user is "sales only" when they hold Sales User (the BP Sales User copy of
2026-10-19 was merged back into it on 2026-10-23) but none of the roles that
already had full Stock Entry access or the accounting roles below. Such a
user may only post the Material Transfer purpose (type "Relokasi Barang").
"""

import frappe
from frappe import _

from bp.patches.v1_0.apply_document_numbering_oct15 import STOCK_ENTRY_SERIES

SALES_ROLES = {"Sales User"}
FULL_ACCESS_ROLES = {
	"Stock User",
	"Stock Manager",
	"Manufacturing User",
	"Manufacturing Manager",
	"Accounts User",
	"Accounts Manager",
	"System Manager",
}
SALES_PURPOSE = "Material Transfer"


def is_sales_only(user=None):
	roles = set(frappe.get_roles(user))
	return bool(roles & SALES_ROLES) and not roles & FULL_ACCESS_ROLES


def validate(doc, method=None):
	if doc.purpose != SALES_PURPOSE and is_sales_only():
		frappe.throw(
			_("Sales staff may only create Stock Mutation of type {0}.").format(
				frappe.bold(get_sales_entry_type() or SALES_PURPOSE)
			),
			title=_("Not Allowed"),
		)


@frappe.whitelist()
def get_sales_entry_type():
	return frappe.db.get_value("Stock Entry Type", {"purpose": SALES_PURPOSE}, "name", order_by="name asc")


def before_naming(doc, method=None):
	"""Number by type (meeting 2026-10-15): MI Barang Masuk, MO Barang Keluar,
	MA Rakit Set, MR Relokasi Barang. A purpose outside the four keeps the
	series it came with."""
	if doc.naming_series and doc.naming_series not in STOCK_ENTRY_SERIES.values():
		return
	series = STOCK_ENTRY_SERIES.get(doc.purpose)
	if series:
		doc.naming_series = series
