# Copyright (c) 2026, Hicom System and contributors
# For license information, please see license.txt

"""One end-of-day pull from the old system during the migration week.

The work itself lives in bp.utils.legacy_import.runner; this controller only
guards the form and exposes the Preview / Run buttons.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import date_diff, getdate, today

MAX_RANGE_DAYS = 31


class LegacyImport(Document):
	def validate(self):
		if getdate(self.from_date) > getdate(self.to_date):
			frappe.throw(_("From Date cannot be after To Date."))
		if getdate(self.to_date) > getdate(today()):
			frappe.throw(_("To Date cannot be in the future."))
		if date_diff(self.to_date, self.from_date) >= MAX_RANGE_DAYS:
			frappe.throw(_("A batch can cover at most {0} days.").format(MAX_RANGE_DAYS))
		if not (self.import_sales_invoice or self.import_purchase_invoice):
			frappe.throw(_("Select at least one document type to import."))
		if not self.is_new() and self.status in ("Queued", "Running"):
			frappe.throw(_("Cannot change a batch while it is running."))

	def on_trash(self):
		if frappe.db.exists(
			"Legacy Import Log",
			{"legacy_import": self.name, "status": ["in", ("Created", "Re-synced")]},
		):
			frappe.throw(_("This batch created documents in ERP and cannot be deleted."))
		frappe.db.delete("Legacy Import Log", {"legacy_import": self.name})


def _get_batch(name):
	frappe.only_for(("System Manager", "Accounts Manager"))
	batch = frappe.get_doc("Legacy Import", name)
	batch.check_permission("write")
	return batch


@frappe.whitelist()
def preview(name):
	from bp.utils.legacy_import.runner import preview as run_preview

	batch = _get_batch(name)
	if batch.status in ("Queued", "Running"):
		frappe.throw(_("This batch is already {0}.").format(batch.status))
	run_preview(batch)


@frappe.whitelist()
def run_import(name):
	from bp.utils.legacy_import.runner import enqueue_run

	enqueue_run(_get_batch(name))
