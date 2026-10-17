"""Warehouse print queue (HT-171, meeting Mulyadi 15 Okt).

Admin AR sends a submitted Sales Invoice to the warehouse admin in one print
format ("Sales Invoice" with prices, "Surat Jalan" without). Each send is one
"BP Warehouse Print" row that the warehouse admin can print exactly once.
AR may send the same invoice again as often as needed; every send, print,
blocked reprint and reset is written to "BP Invoice Print Log".

Printing from the Sales Invoice itself stays free (BP Settings > Enforce
Print Once is off). The warehouse admin role has no access to Sales Invoice,
so the PDF is rendered here with print permissions bypassed, only for a row
that is still Pending.
"""

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from bp.overrides.sales_invoice import _force_commit, _locked_formats, _log, _reset_allowed_roles

DOCTYPE = "BP Warehouse Print"
PRINT_ROLES = ("BP Admin Gudang", "System Manager")


def _check_can_print():
	if not set(PRINT_ROLES) & set(frappe.get_roles()):
		frappe.throw(
			_("Only the BP Admin Gudang role can print from the warehouse queue."), frappe.PermissionError
		)


@frappe.whitelist()
def send_history(sales_invoice):
	"""Formats the invoice can be sent in, with how often each was sent and printed."""
	frappe.has_permission("Sales Invoice", "read", sales_invoice, throw=True)
	rows = frappe.get_all(
		DOCTYPE,
		filters={"sales_invoice": sales_invoice},
		fields=["print_format", "status", "printed_by", "printed_at"],
		order_by="creation asc",
	)
	formats = sorted(_locked_formats())
	history = {f: {"sent": 0, "printed": 0, "pending": 0, "last_printed_by": None} for f in formats}
	for row in rows:
		h = history.setdefault(
			row.print_format, {"sent": 0, "printed": 0, "pending": 0, "last_printed_by": None}
		)
		h["sent"] += 1
		if row.status == "Printed":
			h["printed"] += 1
			h["last_printed_by"] = frappe.utils.get_fullname(row.printed_by) if row.printed_by else None
		else:
			h["pending"] += 1
	return {"formats": formats, "history": history}


@frappe.whitelist(methods=["POST"])
def send_to_warehouse(sales_invoice, print_format):
	"""Queue one print of the invoice in the given format for the warehouse admin."""
	frappe.has_permission("Sales Invoice", "read", sales_invoice, throw=True)
	doc = frappe.get_doc(
		{
			"doctype": DOCTYPE,
			"sales_invoice": sales_invoice,
			"print_format": print_format,
			"status": "Pending",
			"sent_by": frappe.session.user,
			"sent_at": now_datetime(),
		}
	).insert()  # create permission on BP Warehouse Print decides who may send
	invoice = frappe.get_doc("Sales Invoice", sales_invoice)
	_log(invoice, "Sent", print_format, remarks=doc.name, warehouse_print=doc.name)
	return doc.name


def _get_pending(name, log_blocked):
	"""Lock the queue row and make sure it may still be printed."""
	row = frappe.db.get_value(
		DOCTYPE,
		name,
		["name", "sales_invoice", "print_format", "status", "print_count"],
		as_dict=True,
		for_update=True,
	)
	if not row:
		frappe.throw(_("{0} {1} not found.").format(DOCTYPE, name))
	if frappe.db.get_value("Sales Invoice", row.sales_invoice, "docstatus") != 1:
		frappe.throw(
			_("Sales Invoice {0} is no longer submitted (cancelled?). Ask AR to send it again.").format(
				row.sales_invoice
			)
		)
	if row.status == "Printed":
		if log_blocked:
			_log(
				frappe._dict(name=row.sales_invoice),
				"Blocked",
				row.print_format,
				remarks=_("Reprint attempt from warehouse queue {0}").format(name),
				warehouse_print=name,
			)
			_force_commit()  # keep the Blocked row although the throw rolls the request back
		frappe.throw(
			_(
				"{0} has already been printed. Ask AR to send it again, or a user with the {1} role to reset it."
			).format(name, " / ".join(sorted(_reset_allowed_roles()))),
			title=_("Already Printed"),
		)
	return row


@frappe.whitelist(methods=["POST"])
def check_print(name):
	"""Called by the queue before it opens the PDF tab, so a blocked reprint
	shows a normal message instead of an error page."""
	_check_can_print()
	_get_pending(name, log_blocked=True)
	return True


@frappe.whitelist(methods=["GET"])
def print_pdf(name):
	"""Render the queued invoice as PDF and use up the row's single print."""
	_check_can_print()
	row = _get_pending(name, log_blocked=True)
	now = now_datetime()

	# The invoice print formats stamp "printed by / at" from these fields, so set
	# them before rendering: the warehouse copy then shows who printed it and when.
	# bp_print_status is left alone; it belongs to the invoice-level lock.
	frappe.db.set_value(
		"Sales Invoice",
		row.sales_invoice,
		{
			"bp_last_printed_by": frappe.session.user,
			"bp_last_printed_at": now,
			"bp_print_count": cint(frappe.db.get_value("Sales Invoice", row.sales_invoice, "bp_print_count"))
			+ 1,
		},
		update_modified=False,
	)

	# The queue row is the lock here. Mark the invoice as handled for this request
	# so the invoice-level gate (bp.overrides.sales_invoice._gate, active when
	# Enforce Print Once is on) does not block or count this render again.
	frappe.flags.ignore_print_permissions = True
	frappe.flags.bp_print_done = row.sales_invoice
	try:
		pdf = frappe.get_print("Sales Invoice", row.sales_invoice, row.print_format, as_pdf=True)
	finally:
		frappe.flags.ignore_print_permissions = False
		frappe.flags.bp_print_done = None

	frappe.db.set_value(
		DOCTYPE,
		name,
		{
			"status": "Printed",
			"printed_by": frappe.session.user,
			"printed_at": now,
			"print_count": cint(row.print_count) + 1,
		},
	)
	_log(
		frappe._dict(name=row.sales_invoice), "Printed", row.print_format, remarks=name, warehouse_print=name
	)
	frappe.local.flags.commit = True  # GET requests are rolled back unless told otherwise

	frappe.local.response.filename = f"{row.sales_invoice}-{row.print_format}.pdf".replace(" ", "-")
	frappe.local.response.filecontent = pdf
	frappe.local.response.type = "pdf"


@frappe.whitelist(methods=["POST"])
def reset(name, reason):
	"""Let a printed queue row be printed once more."""
	frappe.only_for(_reset_allowed_roles())
	if not (reason or "").strip():
		frappe.throw(_("Reason is required."))
	row = frappe.db.get_value(
		DOCTYPE, name, ["sales_invoice", "print_format", "status"], as_dict=True, for_update=True
	)
	if not row:
		frappe.throw(_("{0} {1} not found.").format(DOCTYPE, name))
	if row.status != "Printed":
		frappe.throw(_("{0} has not been printed yet.").format(name))
	frappe.db.set_value(DOCTYPE, name, "status", "Pending")
	_log(
		frappe._dict(name=row.sales_invoice), "Reset", row.print_format, remarks=reason, warehouse_print=name
	)
	return "Pending"
