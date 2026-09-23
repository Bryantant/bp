"""Restrict Share Management, Budget, and Subscription workspace sidebar
DocTypes to System Manager only.

Same approach as restrict_banking_doctypes_to_system_manager.py: delete any
existing Custom DocPerm rows for each target DocType and replace them with a
single System Manager row whose rights are the union of whatever standard
DocPerm rows already existed (so System Manager loses no capability that any
other role previously had).

Deliberately excludes:
  - Customer, Supplier, Item (Subscription sidebar's Setup section) — shared
    master doctypes used across Sales/Purchase/Stock, not specific to
    subscriptions.
  - Cost Center (Budget sidebar) — several roles (Sales User, Purchase User,
    Employee, HR Manager/User, Auditor) hold narrow read-only access to pick
    it as a link field in unrelated transactions; restricting it would break
    that system-wide, not just in Budget.
Both exclusions were confirmed with Bry.

Idempotent: re-running recomputes the same union from standard DocPerm
(untouched by this patch) and replaces Custom DocPerm rows each time.
"""

import frappe

RIGHT_FIELDS = [
	"read",
	"write",
	"create",
	"delete",
	"submit",
	"cancel",
	"amend",
	"report",
	"export",
	"import",
	"share",
	"print",
	"email",
]

TARGET_DOCTYPES = [
	"Shareholder",
	"Share Transfer",
	"Budget",
	"Accounting Dimension",
	"Cost Center Allocation",
	"Subscription",
	"Subscription Plan",
	"Subscription Settings",
]


def execute():
	for doctype in TARGET_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue

		standard_perms = frappe.get_all(
			"DocPerm",
			filters={"parent": doctype, "permlevel": 0},
			fields=RIGHT_FIELDS,
		)
		if not standard_perms:
			continue

		union = {field: 1 if any(row.get(field) for row in standard_perms) else 0 for field in RIGHT_FIELDS}

		frappe.db.delete("Custom DocPerm", {"parent": doctype})

		doc = frappe.new_doc("Custom DocPerm")
		doc.parent = doctype
		doc.parenttype = "DocType"
		doc.parentfield = "permissions"
		doc.role = "System Manager"
		doc.permlevel = 0
		doc.update(union)
		doc.insert(ignore_permissions=True)

	frappe.clear_cache()
