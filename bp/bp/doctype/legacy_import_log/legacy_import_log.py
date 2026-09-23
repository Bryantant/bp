# Copyright (c) 2026, Hicom System and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# Statuses an admin still has to decide on: the ERP document no longer
# matches the old system and Legacy Import deliberately does not fix it on
# its own (see bp.utils.legacy_import.runner).
NEEDS_DECISION = ("Changed in Legacy", "Cancelled in Legacy")
# Cancelling is also allowed for a document this batch created -- that is how
# a single imported document is taken back out of ERP.
CANCELLABLE = NEEDS_DECISION + ("Created", "Re-synced")


class LegacyImportLog(Document):
	pass


def _get_log_for_action(name, allowed=NEEDS_DECISION):
	frappe.only_for(("System Manager", "Accounts Manager"))
	log = frappe.get_doc("Legacy Import Log", name)
	if log.status not in allowed:
		frappe.throw(_("Only logs with status {0} can be acted on.").format(" / ".join(allowed)))
	return log


@frappe.whitelist()
def resync(name):
	"""Cancel the ERP document and re-create it (as an amendment) from the old system's current data."""
	from bp.utils.legacy_import.runner import resync_log

	log = _get_log_for_action(name)
	if log.status != "Changed in Legacy":
		frappe.throw(_("Re-sync is only possible for documents that were changed in the old system."))
	return resync_log(log)


@frappe.whitelist()
def cancel_in_erp(name):
	"""Cancel the ERP document -- either because the old system reversed it, or
	because this one imported document should be taken back out of ERP."""
	from bp.utils.legacy_import.runner import cancel_log

	return cancel_log(_get_log_for_action(name, allowed=CANCELLABLE))


@frappe.whitelist()
def ignore(name):
	"""Keep the ERP document as it is and stop flagging this difference."""
	from bp.utils.legacy_import.runner import ignore_log

	return ignore_log(_get_log_for_action(name))
