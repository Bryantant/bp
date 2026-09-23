"""Restrict all DocTypes in the "Banking" workspace sidebar to System Manager only.

Custom DocPerm rows fully override a DocType's standard (JSON-defined)
permissions once any row exists for that DocType — so for each target
DocType we delete any existing Custom DocPerm rows and replace them with a
single System Manager row. The row's rights are the union of whatever
standard DocPerm rows already existed for that DocType (across all roles),
so System Manager loses no capability that any other role previously had —
it just becomes the only role that can use these DocTypes.

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
	"Bank",
	"Bank Account",
	"Bank Account Subtype",
	"Bank Account Type",
	"Bank Clearance",
	"Bank Guarantee",
	"Bank Reconciliation Tool",
	"Dunning",
	"Dunning Type",
	"Plaid Settings",
	"Process Payment Reconciliation",
	"Unreconcile Payment",
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
