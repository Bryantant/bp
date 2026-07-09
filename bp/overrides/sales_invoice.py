import frappe
from frappe import _
from frappe.utils import cint, now_datetime


def validate(doc, method=None):
	if not doc.bp_sales_person:
		frappe.throw("Sales Person is required.", title="Missing Sales Person")

	# Rebuild table unconditionally — catches REST/data-importer saves that skip the browser.
	doc.sales_team = []
	row = doc.append("sales_team", {})
	row.sales_person = doc.bp_sales_person
	row.allocated_percentage = 100


# ---------------------------------------------------------------------------
# Active invoice limit
#
# A Customer may cap how many of their submitted invoices can stay unpaid at
# once (Customer.custom_max_active_invoices; blank/0 = no limit). An invoice
# counts as "active" purely by outstanding_amount > 0 -- delivery status is
# not considered. Enforced only at submit (drafts are unrestricted), with no
# bypass: the only way past it is to pay off an existing open invoice.
# ---------------------------------------------------------------------------


def check_active_invoice_limit(doc, method=None):
	if doc.is_return:
		return

	limit = frappe.db.get_value("Customer", doc.customer, "custom_max_active_invoices")
	if not limit:
		return

	open_invoices = frappe.get_all(
		"Sales Invoice",
		filters={
			"customer": doc.customer,
			"docstatus": 1,
			"is_return": 0,
			"outstanding_amount": [">", 0],
			"name": ["!=", doc.name],
		},
		pluck="name",
		order_by="posting_date asc",
	)

	if len(open_invoices) >= limit:
		frappe.throw(
			_(
				"{0} has reached the maximum of {1} active (unpaid) invoice(s): {2}. "
				"Collect payment on one of these before submitting a new invoice."
			).format(doc.customer_name or doc.customer, limit, ", ".join(open_invoices)),
			title=_("Active Invoice Limit Reached"),
		)


# ---------------------------------------------------------------------------
# Print-once control + audit trail
#
# A submitted Sales Invoice may be printed once. Reprints are blocked until an
# Accounts Manager resets the lock. Every Printed / Blocked / Reset event is
# written to "BP Invoice Print Log".
#
# Enforcement lives at the real print path so it can't be bypassed:
#   - before_print  -> fires on the on-screen print view (and during PDF render)
#   - on_print_pdf  -> fires when a PDF is generated (interactive Download PDF)
# ---------------------------------------------------------------------------


def _log(doc, event_type, print_format=None, remarks=None):
	"""Append one audit row. Never let a logging failure break printing."""
	try:
		frappe.get_doc(
			{
				"doctype": "BP Invoice Print Log",
				"sales_invoice": doc.name,
				"event_type": event_type,
				"user": frappe.session.user,
				"timestamp": now_datetime(),
				"print_format": print_format or frappe.form_dict.get("format"),
				"remarks": remarks,
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="BP Invoice Print Log insert failed")


def _gate(doc, print_format, is_pdf):
	"""Block reprints of a submitted invoice; consume the allowance on a real print."""
	if getattr(doc, "docstatus", 0) != 1:
		return  # only submitted invoices are governed
	if frappe.flags.get("bp_print_done") == doc.name:
		return  # already handled in this same request
	if frappe.flags.read_only:
		return  # maintenance/replica — can't write; don't break printing

	if doc.get("bp_print_status") == "Printed":
		# Locked: record the attempt, then abort the render so no copy is produced.
		_log(doc, "Blocked", print_format, remarks="Reprint attempt blocked")
		frappe.db.commit()  # persist the Blocked row before the throw rolls back the request
		frappe.throw(
			_("This invoice has already been printed. Ask an Accounts Manager to reset it before reprinting."),
			title=_("Already Printed"),
		)

	# Not yet printed. A plain on-screen preview is allowed and does not consume;
	# only an actual print (trigger_print) or interactive PDF download consumes.
	actual = is_pdf or bool(frappe.form_dict.get("trigger_print"))
	if not actual:
		return

	_log(doc, "Printed", print_format)
	frappe.db.set_value(
		"Sales Invoice",
		doc.name,
		{
			"bp_print_status": "Printed",
			"bp_print_count": cint(doc.get("bp_print_count")) + 1,
			"bp_last_printed_by": frappe.session.user,
			"bp_last_printed_at": now_datetime(),
		},
		update_modified=False,
	)
	frappe.db.commit()
	frappe.flags.bp_print_done = doc.name


def before_print(doc, method=None, print_settings=None):
	"""doc_events hook — fires on the on-screen print view for a Sales Invoice."""
	_gate(doc, frappe.form_dict.get("format"), is_pdf=False)


def on_print_pdf(doctype=None, name=None, print_format=None, **kwargs):
	"""App hook — fires on PDF generation. Consume only for the interactive
	'Download PDF' request, not for programmatic/email/background PDF generation."""
	if doctype != "Sales Invoice" or not name:
		return
	if frappe.form_dict.get("doctype") != "Sales Invoice" or frappe.form_dict.get("name") != name:
		return
	doc = frappe.get_doc("Sales Invoice", name)
	_gate(doc, print_format, is_pdf=True)


def _reset_allowed_roles():
	"""Roles permitted to reset the print lock, read from BP Settings.

	System Manager is always allowed (safety net + they configure the list).
	The default set is seeded by a patch; an admin can edit it freely."""
	roles = ["System Manager"]
	try:
		roles += frappe.get_all(
			"BP Print Lock Reset Role",
			filters={"parent": "BP Settings", "parenttype": "BP Settings"},
			pluck="role",
		)
	except Exception:
		pass
	return list(set(roles))


@frappe.whitelist()
def can_reset_print_lock():
	"""Client helper — true if the current user holds an allowed reset role."""
	allowed = set(_reset_allowed_roles())
	return bool(allowed & set(frappe.get_roles()))


@frappe.whitelist()
def reset_print_lock(sales_invoice, reason=None):
	"""Reset the print lock so the invoice can be printed once more.

	Allowed roles are configured in BP Settings (Print Lock Reset Roles)."""
	frappe.only_for(_reset_allowed_roles())

	if not frappe.db.exists("Sales Invoice", sales_invoice):
		frappe.throw(_("Sales Invoice {0} not found.").format(sales_invoice))

	doc = frappe.get_doc("Sales Invoice", sales_invoice)
	frappe.db.set_value("Sales Invoice", sales_invoice, "bp_print_status", "Not Printed", update_modified=False)
	_log(doc, "Reset", remarks=(reason or "Print lock reset"))
	frappe.db.commit()
	return {"sales_invoice": sales_invoice, "bp_print_status": "Not Printed"}
