"""Restrict the remaining out-of-scope DocTypes from the BP Feature Scope
sheet (https://docs.google.com/spreadsheets/d/11csjs1Hu1-cWYQnfgUQHuJ4Q0z9bmB4ibX0xgR_51Vw,
gid 697742285) to System Manager only.

Same approach as restrict_banking_doctypes_to_system_manager.py and
restrict_share_budget_subscription_to_system_manager.py: delete any existing
Custom DocPerm rows for each target DocType and replace them with a single
System Manager row whose rights are the union of whatever standard DocPerm
rows already existed (so System Manager loses no capability that any other
role previously had).

Bank Guarantee is included here even though it was previously un-restricted
by undo_banking_setup_section_restriction.py — the new scope sheet marks it
out of scope again and Bry confirmed reversing that earlier undo.

Deliberately excludes three other out-of-scope rows from this pass:
  - Cost Center — already independently restricted to System Manager only
    (2026-08-04, outside any tracked patch). The 2026-07-29 patch comment on
    restrict_share_budget_subscription_to_system_manager.py explains why it
    normally should NOT be restricted (Sales User/Purchase User/Accounts
    User/Auditor pick it as a link field on unrelated transactions). Bry
    chose to leave the current (restricted) state alone rather than restore
    it — not touched by this patch either way.
  - Incoterm, Shipping Rule — both are Link fields on nearly every Sales/
    Purchase/Stock transaction (Sales/Purchase Order, Quotation, Sales/
    Purchase Invoice, POS Invoice, Delivery Note, Purchase Receipt, RFQ,
    Supplier Quotation, Shipment). Restricting them would blank out that
    field for Sales/Purchase/Stock roles on core transaction forms — the
    same cross-functional risk class as Cost Center. Confirmed with Bry.

Also NOT covered here because a Module Settings toggle already handles them
(per Bry's tool priority: Module Settings first, RPM only if no settings
option exists), and both toggles are already off on this site:
  - Accounting Dimension Filter — Accounts Settings.enable_accounting_dimensions
  - Party Link ("Common Party Accounting") — Accounts Settings.enable_common_party_accounting

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
	"Bank Guarantee",
	"Bank Transaction",
	"Cheque Print Template",
	"Delivery Trip",
	"Quality Inspection Parameter",
	"Quality Inspection Parameter Group",
	"Share Type",
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
