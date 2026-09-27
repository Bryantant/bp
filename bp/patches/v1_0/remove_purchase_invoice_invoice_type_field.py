"""Remove Purchase Invoice's Invoice Type (Cash/Credit) field.

It existed only to feed the PF/PC naming series, which
bp.patches.v1_0.name_invoices_and_returns_by_warehouse replaced with
P + warehouse code. Invoices already named PF/PC keep their names.

Idempotent: does nothing once the field is gone.
"""

import frappe

FIELD = "custom_invoice_type"


def execute():
	name = frappe.db.get_value("Custom Field", {"dt": "Purchase Invoice", "fieldname": FIELD})
	if name:
		frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
	frappe.db.delete("Property Setter", {"doc_type": "Purchase Invoice", "field_name": FIELD})
	if frappe.db.has_column("Purchase Invoice", FIELD):
		frappe.db.sql_ddl(f"ALTER TABLE `tabPurchase Invoice` DROP COLUMN `{FIELD}`")
	frappe.clear_cache(doctype="Purchase Invoice")
