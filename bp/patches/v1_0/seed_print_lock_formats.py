"""Seed BP Settings > Print Lock Formats.

Print-once used to govern every Sales Invoice print. It now applies only to
the formats listed in BP Settings, so a Debit Note format prints freely, as
in the old system. Seeding the two invoice formats in use keeps today's
behaviour for goods invoices.

Idempotent: only seeds when the table is empty, so later edits stay.
"""

import frappe

DEFAULT_FORMATS = ["Sales Invoice", "Delivery Order"]


def execute():
	settings = frappe.get_single("BP Settings")
	if settings.get("print_lock_formats"):
		return

	for name in DEFAULT_FORMATS:
		if frappe.db.get_value("Print Format", name, "doc_type") == "Sales Invoice":
			settings.append("print_lock_formats", {"print_format": name})

	settings.save(ignore_permissions=True)
