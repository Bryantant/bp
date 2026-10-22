import frappe
from frappe import _


def validate(doc, method=None):
	"""Mode of Payment is required to submit a Pay or Receive Payment Entry.

	An Internal Transfer may go without one (Bry 2026-10-21). The form makes
	the field mandatory from the first save for Pay and Receive (Client Script
	"Payment Entry - Mode of Payment Wajib"); this check covers API and Data
	Import. It runs on submit only (docstatus 1), so a draft saved outside the
	form is not blocked.
	"""
	if doc.docstatus == 1 and doc.payment_type in ("Pay", "Receive") and not doc.mode_of_payment:
		frappe.throw(
			_("Mode of Payment is required before approving this Payment Entry."),
			title=_("Missing Mode of Payment"),
		)
