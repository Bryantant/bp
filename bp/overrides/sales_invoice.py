import frappe
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from frappe import _
from frappe.utils import cint, now_datetime

from bp.patches.v1_0.allow_non_stock_sales_invoices import NON_STOCK_SERIES, WAREHOUSE_SERIES
from bp.utils.cascading_discount import calculate_cascading_discount


# ---------------------------------------------------------------------------
# Controller override
#
# Legacy Import (bp.utils.legacy_import) submits invoices the client already
# issued in the old system, so ERP's credit-limit block would be refusing an
# invoice the customer has physically received -- the same reasoning as the
# active invoice limit below. check_credit_limit() is called from core's
# on_submit and takes no bypass argument, so the only clean way to skip it is
# this controller override (registered via override_doctype_class in hooks.py).
# Outside an import run nothing changes.
# ---------------------------------------------------------------------------


class BPSalesInvoice(SalesInvoice):
	def check_credit_limit(self):
		if frappe.flags.get("bp_legacy_import") or not enforced("enforce_credit_limit"):
			return
		super().check_credit_limit()


def enforced(setting):
	"""Is this invoice control switched on in BP Settings?

	Both controls can be switched off while the site is being set up or
	trialled -- an empty/unsaved BP Settings must not silently disable them,
	so a missing value counts as enforced.
	"""
	# Read the raw row: get_single_value() casts a never-saved Check to 0, which
	# would make every newly added switch start life switched OFF.
	row = frappe.db.sql("select value from `tabSingles` where doctype = %s and field = %s", ("BP Settings", setting))
	return True if not row or row[0][0] is None else bool(cint(row[0][0]))


# ---------------------------------------------------------------------------
# Naming series — Source Warehouse token
#
# Registered via the `naming_series_variables` hook (hooks.py) so the native
# naming-series engine (frappe.model.naming.parse_naming_series) can resolve
# the "warehouse_name_code" token in the series pattern
# (warehouse_name_code.YY.MM.####) to the Warehouse's clean display name,
# instead of embedding the raw Warehouse Link value (which includes the
# company abbreviation, e.g. "A - BP").
# ---------------------------------------------------------------------------


def get_warehouse_name_code(doc, token=None):
	warehouse = doc.get("set_warehouse")
	if not warehouse:
		return ""
	return frappe.db.get_value("Warehouse", warehouse, "warehouse_name") or ""


def before_naming(doc, method=None):
	"""Pick the naming series for an invoice that carries no goods.

	The default series is built from the Source Warehouse
	(get_warehouse_name_code below), which a value-only invoice -- an AR debit
	note charging a principal for a promo claim, say -- does not have. Those
	get NON_STOCK_SERIES instead; see
	bp.patches.v1_0.allow_non_stock_sales_invoices.

	Runs on insert only, before the name is generated, and only matters when
	the user has not picked a series by hand.
	"""
	if doc.naming_series and doc.naming_series != WAREHOUSE_SERIES:
		# Somebody picked a series deliberately (API, Data Import, an amended
		# document): leave it. Only the default, which Frappe fills in from the
		# first option, is ours to change.
		return

	if doc.is_opening == "Yes":
		# Named after the legacy invoice number before it reaches here, so the
		# series is never used -- say so rather than set a misleading one.
		return

	# Update Stock is the deciding flag, not an empty Source Warehouse: the
	# warehouse is only mandatory while Update Stock is on, so "no warehouse"
	# can also mean a goods invoice that is simply not filled in yet, and that
	# one should keep the warehouse series and fail validation as usual.
	doc.naming_series = WAREHOUSE_SERIES if doc.update_stock else NON_STOCK_SERIES


def validate(doc, method=None):
	require_warehouse_when_stock_moves(doc)

	if not doc.bp_sales_person and doc.is_opening == "Yes":
		# An opening balance carries no salesperson of its own; use the
		# customer's, and accept none rather than blocking the import.
		doc.bp_sales_person = frappe.db.get_value("Customer", doc.customer, "bp_sales_person")
		if not doc.bp_sales_person:
			return

	if not doc.bp_sales_person:
		frappe.throw("Sales Person is required.", title="Missing Sales Person")

	# Rebuild table unconditionally — catches REST/data-importer saves that skip the browser.
	doc.sales_team = []
	row = doc.append("sales_team", {})
	row.sales_person = doc.bp_sales_person
	row.allocated_percentage = 100


def require_warehouse_when_stock_moves(doc):
	"""Source Warehouse is mandatory for any invoice that moves stock.

	The Property Setter (bp.patches.v1_0.allow_non_stock_sales_invoices) makes
	the field conditionally mandatory so a value-only invoice -- an AR debit
	note for a principal's claim -- can be saved without one. But Frappe
	enforces `mandatory_depends_on` in the browser only: a server-side insert
	(Legacy Import, the REST API, Data Import) would otherwise slip through
	with no warehouse and a naming series that resolves to nothing. This keeps
	the rule where it has to hold.
	"""
	if doc.update_stock and not doc.set_warehouse:
		frappe.throw(
			_("Source Warehouse is required when the invoice updates stock."),
			title=_("Missing Source Warehouse"),
		)


# ---------------------------------------------------------------------------
# Two-tier cascading discount (Discount 1 = supplier/claimable, Discount 2 =
# internal policy)
#
# Authoritative server-side recompute: bp/public/js/sales_invoice.js keeps
# the same math in sync live in the browser, but this runs unconditionally on
# every save so REST/data-importer saves that skip the browser still end up
# with a correct rate -- same rationale as the sales_team rebuild in
# validate() above.
#
# Wired via "before_validate" (not "validate") in hooks.py so the final rate
# is in place before core's own validate() -> calculate_taxes_and_totals()
# computes amount/net_amount/totals from it.
# ---------------------------------------------------------------------------


def recalculate_cascading_discount(doc, method=None):
	for item in doc.get("items", []):
		if not item.get("price_list_rate"):
			# No list price to cascade from (item has no Item Price / no price list
			# match) -- leave whatever rate was entered untouched instead of
			# zeroing it out.
			continue
		result = calculate_cascading_discount(
			price_list_rate=item.get("price_list_rate"),
			discount1_percentage=item.get("custom_discount1_percentage"),
			discount1_amount=item.get("custom_discount1_amount"),
			discount2_percentage=item.get("custom_discount2_percentage"),
			discount2_amount=item.get("custom_discount2_amount"),
			rate_precision=item.precision("rate"),
			pct_precision=item.precision("custom_discount1_percentage"),
			amt_precision=item.precision("custom_discount1_amount"),
		)
		item.custom_discount1_percentage = result["discount1_percentage"]
		item.custom_discount1_amount = result["discount1_amount"]
		item.custom_discount2_percentage = result["discount2_percentage"]
		item.custom_discount2_amount = result["discount2_amount"]
		item.rate = result["rate"]
		item.discount_percentage = result["discount_percentage"]
		item.discount_amount = result["discount_amount"]


# ---------------------------------------------------------------------------
# Active invoice limit
#
# A Customer may cap how many of their submitted invoices can stay unpaid at
# once (Customer.custom_max_active_invoices; blank/0 = no limit). An invoice
# counts as "active" purely by outstanding_amount > 0 -- delivery status is
# not considered. Enforced only at submit (drafts are unrestricted). Two
# bypasses: Legacy Import (bp.utils.legacy_import), because those invoices
# were already issued in the old system and the limit cannot un-issue them,
# and the BP Settings switch used while the site is set up or trialled.
# ---------------------------------------------------------------------------


def check_active_invoice_limit(doc, method=None):
	if doc.is_return or frappe.flags.get("bp_legacy_import"):
		return

	if not enforced("enforce_active_invoice_limit"):
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
# A submitted Sales Invoice may be printed once. Reprints are blocked until a
# user with an allowed role (see _reset_allowed_roles) resets the lock. Every
# Printed / Blocked / Reset event is written to "BP Invoice Print Log".
#
# BP Settings > Enforce Print Once switches the blocking off: reprints are then
# allowed, but each print is still logged and counted, so the audit trail and
# bp_print_status stay accurate if the lock is switched back on later.
#
# Enforcement lives entirely in before_print, which fires on every print/PDF
# render (on-screen preview, on-screen "Print", single Download PDF, and bulk
# Download PDF from the list view) regardless of which pdf_generator is
# configured -- see the comment in _gate() for why the `on_print_pdf` app
# hook this used to also rely on is not usable for that purpose.
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


# Whitelisted endpoints that mean a human explicitly asked for a PDF right
# now -- as opposed to a background/email/automated PDF (e.g. "Attach Print"
# on submit, or a scheduled job), which runs with no matching `cmd` in
# frappe.form_dict and must NOT consume the print-once allowance.
#
# Both the single-invoice "Download PDF" button AND the List View's bulk
# "Print" action (selecting one or more rows -- the everyday way invoices
# actually get printed) must consume the lock.
_INTERACTIVE_PRINT_CMDS = {
	"frappe.utils.print_format.download_pdf",
	"frappe.utils.print_format.download_multi_pdf",
}


def _force_commit():
	"""Commit immediately, bypassing both safeguards that make a plain
	frappe.db.commit() unreliable here:

	1. Document.hook()'s compose() increments db._disable_transaction_control
	   while a doc_events hook (like before_print) is running, specifically to
	   stop hooks from committing mid-transaction -- so a plain commit() call
	   from inside before_print is always a silent no-op (just a warning).
	2. Download PDF (single or bulk) is a GET request, and frappe/app.py's
	   request teardown *always* rolls back GET requests unless something set
	   frappe.local.flags.commit -- and if we're about to frappe.throw(), the
	   teardown's exception path rolls back unconditionally regardless of that
	   flag. The only way for a row to survive an imminent throw is to commit
	   it for real, right now.
	"""
	saved = frappe.db._disable_transaction_control
	frappe.db._disable_transaction_control = 0
	try:
		frappe.db.commit()
	finally:
		frappe.db._disable_transaction_control = saved


def _gate(doc, print_format):
	"""Block reprints of a submitted invoice; consume the allowance on a real print."""
	if getattr(doc, "docstatus", 0) != 1:
		return  # only submitted invoices are governed
	if frappe.flags.get("bp_print_done") == doc.name:
		return  # already handled in this same request
	if frappe.flags.read_only:
		return  # maintenance/replica — can't write; don't break printing

	if doc.get("bp_print_status") == "Printed" and enforced("enforce_print_once"):
		# Locked: record the attempt, then abort the render so no copy is produced.
		_log(doc, "Blocked", print_format, remarks="Reprint attempt blocked")
		_force_commit()  # persist the Blocked row before the throw rolls back the request
		frappe.throw(
			_("This invoice has already been printed. Ask a user with the {0} role to reset it before reprinting.").format(
				_reset_allowed_roles_label()
			),
			title=_("Already Printed"),
		)

	# Not yet printed. A plain on-screen preview (or the in-dialog preview
	# AJAX call) does not consume the allowance -- only an actual print
	# consumes: the on-screen "Print" button (trigger_print=1 on the
	# /printview route) or an interactive Download PDF request, single or
	# bulk. Detected here in before_print rather than via the `on_print_pdf`
	# app hook because before_print fires for every render regardless of
	# which pdf_generator is configured (wkhtmltopdf or chrome) -- when a
	# custom pdf_generator hook is set (this site uses "chrome"), Frappe
	# returns the PDF before ever calling on_print_pdf, so that hook never
	# fired here and the lock was silently never consumed.
	actual = bool(frappe.form_dict.get("trigger_print")) or frappe.form_dict.get("cmd") in _INTERACTIVE_PRINT_CMDS
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
	# Download PDF (single or bulk) is a GET request. frappe/app.py's request
	# teardown rolls back every GET by default (GETs are conventionally
	# read-only) -- this flag is Frappe's own sanctioned way for a GET handler
	# to say "I intentionally wrote data, please commit" (see e.g. CRM's
	# crm.api: frappe.local.flags.commit = True). Without it, the write above
	# would be silently discarded and the invoice would stay reprint-able
	# forever, however many times before_print correctly detects the print.
	frappe.local.flags.commit = True
	frappe.flags.bp_print_done = doc.name


def before_print(doc, method=None, print_settings=None):
	"""doc_events hook — fires on every print/PDF render for a Sales Invoice,
	regardless of pdf_generator. The sole enforcement point; see _gate()."""
	_gate(doc, frappe.form_dict.get("format"))


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


def _reset_allowed_roles_label():
	"""Role name(s) for the "Already Printed" message, built from the same
	source as _reset_allowed_roles() so the wording never drifts from what BP
	Settings actually allows (e.g. if the child table is left empty, the
	message correctly names System Manager instead of a role nobody in that
	state can use). No leading article ("a"/"an") so multi-word and plural
	role names always read correctly in the "role to reset it" sentence."""
	roles = sorted(_reset_allowed_roles())
	if len(roles) == 1:
		return roles[0]
	return "{0} or {1}".format(", ".join(roles[:-1]), roles[-1])


@frappe.whitelist()
def print_lock_state():
	"""Client helper -- BP Settings is System Manager-only, so the form asks here
	whether the lock is on and whether this user may reset it."""
	return {"enforced": enforced("enforce_print_once"), "can_reset": can_reset_print_lock()}


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
