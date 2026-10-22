"""Remove Legacy Import: the daily document import from the old system is not used (Bry, 2026-10-23).

The code is gone from the app; this drops what migrate leaves behind on a site: the DocTypes
Legacy Import, Legacy Import Log and the two BP Settings mapping tables (with their database
tables), and the BP Settings values of the removed fields. Documents that were imported keep
their custom_legacy_* fields. The old-system database connection in BP Settings stays: the
master, opening invoice, item price and salesman importers (bp.utils.import_legacy_*) use it.

Runs after model sync, so BP Settings no longer points at the mapping tables.
"""

import frappe

DOCTYPES = ("Legacy Import Log", "Legacy Import", "BP Legacy Warehouse Map", "BP Legacy Payment Method Map")
SETTINGS_FIELDS = (
	"legacy_import_enabled",
	"legacy_amount_tolerance",
	"legacy_warehouse_map",
	"legacy_payment_method_map",
)


def execute():
	for doctype in DOCTYPES:
		if frappe.db.exists("DocType", doctype):
			frappe.delete_doc("DocType", doctype, force=True, ignore_permissions=True, ignore_missing=True)
		# delete_doc (and migrate's orphan cleanup) keep the table; drop it too
		frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `tab{doctype}`")
	frappe.db.delete("Singles", {"doctype": "BP Settings", "field": ["in", SETTINGS_FIELDS]})
	for doctype in DOCTYPES:
		frappe.db.delete("Workspace Link", {"link_to": doctype})
	frappe.clear_cache()
