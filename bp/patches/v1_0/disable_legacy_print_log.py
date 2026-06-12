"""Disable the legacy DB-only "Invoice Print Log" feature.

The old print-once control was built from Server Scripts + Client Scripts created
directly in the database (module "Custom"). It is superseded by the bp-app
"BP Invoice Print Log" doctype + before_print/on_print_pdf hooks.

This patch only DISABLES the old artifacts (reversible). It deliberately does NOT
delete the old Custom doctype "Invoice Print Log" or its data — deleting a DocType
is a forbidden action that must be done manually with the owner's sign-off.
"""

import frappe

LEGACY_SERVER_SCRIPTS = [
	"Invoice Print Log Enforce Print Once",
	"Sales Invoice Print Log Create",
]

LEGACY_CLIENT_SCRIPTS = [
	"Invoice Print Log Form",
	"Sales Invoice Print Log Buttons",
]


def execute():
	for name in LEGACY_SERVER_SCRIPTS:
		if frappe.db.exists("Server Script", name):
			frappe.db.set_value("Server Script", name, "disabled", 1)

	for name in LEGACY_CLIENT_SCRIPTS:
		if frappe.db.exists("Client Script", name):
			frappe.db.set_value("Client Script", name, "enabled", 0)
