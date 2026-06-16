import frappe
from frappe import _


def validate(doc, method=None):
	"""Approval-phase rule for Payment Entry.

	Mode of Payment is left to the Accounts Manager who approves the document,
	so it must NOT block the Accounts User saving the initial draft. During a
	workflow Approve the doc reaches validate() with docstatus already set to 1
	(submit), whereas a plain draft save runs with docstatus 0 — so we only
	enforce the field when the document is being submitted/approved.
	"""
	if doc.docstatus == 1 and not doc.mode_of_payment:
		frappe.throw(
			_("Mode of Payment is required before approving this Payment Entry."),
			title=_("Missing Mode of Payment"),
		)
