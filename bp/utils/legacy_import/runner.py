"""Preview / run / re-sync / revert for the Legacy Import doctype.

Flow for one batch (a date range):
1. For every selected kind (kinds.py), pull its documents in the range from
   the old system, plus older ones touched (LasUpdDt) since the range start.
2. Classify each against ERP by (custom_legacy_type, custom_legacy_no):
	- confirmed, not in ERP             -> Ready (Run creates + submits it)
	- confirmed, in ERP, unchanged      -> Already Imported
	- confirmed, in ERP, newer LasUpdDt -> Changed in Legacy
	- draft/cancelled, in ERP           -> Cancelled in Legacy
	- draft/cancelled, not in ERP       -> Skipped
   plus ERP documents in the range whose number no longer exists in the old
   system at all (a reversed draft that was then deleted) -> Cancelled in Legacy.
3. Run: create + submit each Ready document in its own transaction, so one
   bad document never blocks the rest, kind by kind in kinds.ORDERED -- goods
   in before goods out, invoices before the receipts that settle them.

"Changed/Cancelled in Legacy" are only flagged -- an admin decides per
document from the Legacy Import Log (re-sync / cancel in ERP / ignore).
Running a batch again is safe: nothing already in ERP is created twice.
"""

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, getdate, now_datetime, strip_html

from bp.utils.legacy_db import get_legacy_connection
from bp.utils.legacy_import import SALES_RETURN, STOCK_MUTATION, LegacyImportError, legacy_status_label
from bp.utils.legacy_import.context import ImportContext
from bp.utils.legacy_import.kinds import ORDERED, get_kind, selected_kinds
from bp.utils.legacy_import.kinds import check_amount as _check_amount
from bp.utils.legacy_import.source import fetch, fetch_legacy_costs, fetch_one, fetch_payment_methods

# Log statuses that record something done to ERP; a later preview/run of the
# same batch must not overwrite them with "Already Imported".
FINAL_LOG_STATUSES = ("Created", "Re-synced", "Cancelled in ERP", "Ignored")
# A batch in one of these states has a background job working on it.
BUSY_STATUSES = ("Queued", "Running")
PROGRESS_EVENT = "legacy_import_progress"


# ---------------------------------------------------------------------------
# Classification (pure -- unit tested without a legacy connection)
# ---------------------------------------------------------------------------


def classify(legacy_doc, existing):
	"""Return (status, message) for a legacy doc given its ERP doc (dict or None)."""
	kind = get_kind(legacy_doc["kind"])
	confirmed = kind.is_confirmed(legacy_doc["status"])
	label = legacy_status_label(legacy_doc["status"], kind.key)

	if not existing:
		if confirmed:
			return "Ready", None
		return "Skipped", _("Status in old system: {0}").format(label)

	if not confirmed:
		return "Cancelled in Legacy", _("Status in old system is now {0}").format(label)

	if existing.get("docstatus") == 0:
		return "Already Imported", _("ERP document {0} is still a Draft").format(existing["name"])

	legacy_updated = legacy_doc.get("updated_at")
	imported_updated = existing.get("custom_legacy_updated_at")
	if legacy_updated and (
		not imported_updated or get_datetime(legacy_updated) > get_datetime(imported_updated)
	):
		return "Changed in Legacy", _("Changed in old system at {0} (imported version: {1})").format(
			legacy_updated, imported_updated or "-"
		)

	return "Already Imported", None


def in_range(legacy_doc, from_date, to_date):
	return getdate(from_date) <= legacy_doc["date"] <= getdate(to_date)


# ---------------------------------------------------------------------------
# Whitelisted entry points (called from legacy_import.py)
# ---------------------------------------------------------------------------


def ensure_enabled():
	if not frappe.db.get_single_value("BP Settings", "legacy_import_enabled"):
		frappe.throw(_("Legacy Import is disabled in BP Settings."))


def preview(batch):
	ensure_enabled()
	plan = collect(batch)
	# Documents this batch would create count as present for the receipts and
	# payments that settle them -- otherwise a Preview would flag every
	# receipt for an invoice imported in the same batch.
	ctx = build_context(plan, pending=True)
	drop_stale_logs(batch.name, plan)

	for entry in plan:
		if entry["status"] == "Ready":
			try:
				get_kind(entry["kind"]).build(entry["legacy_doc"], ctx)
			except LegacyImportError as e:
				entry["status"], entry["message"] = "Error", str(e)
		write_log(batch.name, entry)

	update_summary(batch.name, status="Previewed")
	frappe.db.commit()


def build_context(plan, pending=False):
	ctx = ImportContext().prefetch([p["legacy_doc"] for p in plan if p["legacy_doc"]])
	conn = get_legacy_connection()
	try:
		ctx.payment_methods = fetch_payment_methods(conn)
		# Goods coming in that ERP may not be able to value (missing_valuation_rate)
		incoming = [
			p["legacy_doc"]
			for p in plan
			if p["kind"] in (SALES_RETURN, STOCK_MUTATION) and p["status"] == "Ready" and p["legacy_doc"]
		]
		if incoming:
			ctx.legacy_costs = fetch_legacy_costs(
				conn,
				[line["ItemCode"].strip() for doc in incoming for line in doc["lines"]],
				max(doc["date"] for doc in incoming),
			)
	finally:
		conn.close()
	if pending:
		ctx.pending = {(p["kind"], p["legacy_no"]) for p in plan if p["status"] == "Ready"}
	return ctx


def enqueue_run(batch):
	ensure_enabled()
	running = frappe.get_all(
		"Legacy Import",
		filters={"status": ["in", BUSY_STATUSES], "name": ["!=", batch.name]},
		pluck="name",
	)
	if running:
		frappe.throw(_("Legacy Import {0} is still running. Wait for it to finish.").format(running[0]))
	if batch.status in BUSY_STATUSES:
		frappe.throw(_("This batch is already {0}.").format(batch.status))

	batch.db_set({"status": "Queued", "run_by": frappe.session.user, "error_message": None})
	frappe.enqueue(
		"bp.utils.legacy_import.runner.run_batch",
		queue="long",
		timeout=3600,
		batch_name=batch.name,
		job_id=f"legacy_import::{batch.name}",
		deduplicate=True,
		enqueue_after_commit=True,
	)


def enqueue_revert(batch):
	"""Queue a revert of everything this batch created.

	Deliberately does NOT require legacy_import_enabled: after cutover the
	switch is off, and that is exactly when someone may still need to undo a
	batch.
	"""
	busy = frappe.get_all(
		"Legacy Import",
		filters={"status": ["in", BUSY_STATUSES], "name": ["!=", batch.name]},
		pluck="name",
	)
	if busy:
		frappe.throw(_("Legacy Import {0} is still running. Wait for it to finish.").format(busy[0]))
	if batch.status in BUSY_STATUSES:
		frappe.throw(_("This batch is already {0}.").format(batch.status))
	if not revertable_logs(batch.name):
		frappe.throw(_("This batch has no documents left to cancel."))

	batch.db_set({"status": "Queued", "run_by": frappe.session.user, "error_message": None})
	frappe.enqueue(
		"bp.utils.legacy_import.runner.revert_batch",
		queue="long",
		timeout=3600,
		batch_name=batch.name,
		job_id=f"legacy_import_revert::{batch.name}",
		deduplicate=True,
		enqueue_after_commit=True,
	)


def revertable_logs(batch_name):
	"""Logs whose ERP document this batch created and that is still live,
	in kinds.revert_order: payments before the invoices they settle, sales
	before the receivings whose stock they used (cancelling a sale puts stock
	back, cancelling a receipt takes it out).
	"""
	logs = frappe.get_all(
		"Legacy Import Log",
		filters={
			"legacy_import": batch_name,
			"status": ["in", ("Created", "Re-synced")],
			"erp_name": ["is", "set"],
		},
		fields=["name", "legacy_doctype", "legacy_no", "erp_doctype", "erp_name", "legacy_date"],
	)
	return sorted(logs, key=lambda log: (_revert_rank(log.legacy_doctype), log.erp_name))


def _revert_rank(kind_key):
	try:
		return get_kind(kind_key).revert_order
	except KeyError:
		return 999


# ---------------------------------------------------------------------------
# Background job
# ---------------------------------------------------------------------------


def run_batch(batch_name):
	batch = frappe.get_doc("Legacy Import", batch_name)
	batch.db_set({"status": "Running", "started_at": now_datetime(), "finished_at": None})
	frappe.db.commit()

	frappe.flags.bp_legacy_import = True
	try:
		plan = collect(batch)
		ctx = build_context(plan)
		drop_stale_logs(batch.name, plan)
		ready = [p for p in plan if p["status"] == "Ready"]

		for entry in plan:
			if entry["status"] != "Ready":
				write_log(batch_name, entry)
		frappe.db.commit()

		for i, entry in enumerate(ready, start=1):
			create_document(entry, ctx)
			write_log(batch_name, entry)
			frappe.db.commit()
			frappe.publish_realtime(
				PROGRESS_EVENT,
				{"done": i, "total": len(ready), "legacy_no": entry["legacy_no"]},
				doctype="Legacy Import",
				docname=batch_name,
			)

		summary = update_summary(batch_name)
		status = "Completed with Errors" if summary["error_count"] else "Completed"
		frappe.db.set_value("Legacy Import", batch_name, {"status": status, "finished_at": now_datetime()})
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.db.set_value(
			"Legacy Import",
			batch_name,
			{"status": "Failed", "finished_at": now_datetime(), "error_message": frappe.get_traceback()},
		)
		frappe.db.commit()
		frappe.log_error(title=f"Legacy Import {batch_name} failed")
	finally:
		frappe.flags.bp_legacy_import = False
		frappe.publish_realtime(
			PROGRESS_EVENT, {"finished": True}, doctype="Legacy Import", docname=batch_name
		)


def create_document(entry, ctx):
	"""Create + submit one Ready document; outcome is written back onto entry.

	The caller commits after every document, so on failure the rollback here
	discards only this document; the reason goes onto entry for its log.
	"""
	legacy_doc = entry["legacy_doc"]
	kind = get_kind(entry["kind"])
	try:
		doc = kind.build(legacy_doc, ctx)
		doc.insert()
		kind.check(doc, legacy_doc, ctx.tolerance)
		doc.submit()
		entry.update(status="Created", erp_name=doc.name, erp_amount=kind.erp_amount(doc), message=None)
	except Exception as e:
		frappe.db.rollback()
		entry.update(status="Error", erp_name=None, erp_amount=None, message=error_text(e))
		if not isinstance(e, (LegacyImportError, frappe.ValidationError)):
			frappe.log_error(title=f"Legacy Import {legacy_doc['legacy_no']} failed")
	finally:
		frappe.clear_messages()


def revert_batch(batch_name):
	"""Cancel every ERP document this batch created, one transaction each.

	A document that cannot be cancelled (a paid invoice, stock already
	consumed) is left alone with the reason on its log row; the rest still
	get reverted.
	"""
	batch = frappe.get_doc("Legacy Import", batch_name)
	batch.db_set({"status": "Running", "started_at": now_datetime(), "finished_at": None})
	frappe.db.commit()

	frappe.flags.bp_legacy_import = True
	errors = 0
	try:
		logs = revertable_logs(batch_name)
		for i, log in enumerate(logs, start=1):
			if not cancel_document(log):
				errors += 1
			frappe.db.commit()
			frappe.publish_realtime(
				PROGRESS_EVENT,
				{"done": i, "total": len(logs), "legacy_no": log.legacy_no},
				doctype="Legacy Import",
				docname=batch_name,
			)

		update_summary(batch_name)
		frappe.db.set_value(
			"Legacy Import",
			batch_name,
			{
				"status": "Reverted with Errors" if errors else "Reverted",
				"finished_at": now_datetime(),
			},
		)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.db.set_value(
			"Legacy Import",
			batch_name,
			{"status": "Failed", "finished_at": now_datetime(), "error_message": frappe.get_traceback()},
		)
		frappe.db.commit()
		frappe.log_error(title=f"Legacy Import revert {batch_name} failed")
	finally:
		frappe.flags.bp_legacy_import = False
		frappe.publish_realtime(
			PROGRESS_EVENT, {"finished": True}, doctype="Legacy Import", docname=batch_name
		)


def cancel_document(log):
	"""Cancel one imported document; returns False (and records why) on failure."""
	frappe.db.savepoint("legacy_revert_doc")
	try:
		doc = frappe.get_doc(_erp_doctype(log), log.erp_name)
		if doc.docstatus == 1:
			doc.cancel()
		elif doc.docstatus == 0:
			doc.delete()
		frappe.db.set_value(
			"Legacy Import Log",
			log.name,
			{
				"status": "Cancelled in ERP",
				"message": _("Cancelled by {0}").format(frappe.session.user),
			},
		)
		return True
	except Exception as e:
		frappe.db.rollback(save_point="legacy_revert_doc")
		frappe.db.set_value(
			"Legacy Import Log",
			log.name,
			"message",
			_("Could not cancel {0}: {1}").format(log.erp_name, error_text(e)),
		)
		return False
	finally:
		frappe.clear_messages()


def check_amount(doc, expected, tolerance):
	"""Invoice-style check on grand_total (kept for callers and tests of the invoice kinds)."""
	_check_amount(doc.grand_total, expected, tolerance)


def _erp_doctype(log):
	"""The ERP doctype a log row points at -- recorded on the log, else from its kind."""
	return log.get("erp_doctype") or get_kind(log.legacy_doctype).erp_doctype


def error_text(e):
	"""A message an admin can act on.

	Some Frappe exceptions (DoesNotExistError, LinkValidationError) carry an
	empty str(), so fall back to the last traceback line instead of printing
	a bare class name.
	"""
	text = strip_html(str(e)).strip()
	if not text:
		trace = frappe.get_traceback(with_context=False).strip().splitlines()
		text = f"{e.__class__.__name__}: {trace[-1]}" if trace else e.__class__.__name__
	return text[:1000]


# ---------------------------------------------------------------------------
# Collect + classify
# ---------------------------------------------------------------------------


def collect(batch):
	"""Return the batch's plan: one entry per legacy doc (and per orphaned ERP doc),
	kind by kind in processing order."""
	kinds = selected_kinds(batch)
	legacy_docs = {}
	conn = get_legacy_connection()
	try:
		for kind in kinds:
			legacy_docs[kind.key] = fetch(conn, kind.key, batch.from_date, batch.to_date)
	finally:
		conn.close()

	plan = []
	for kind in kinds:
		docs = legacy_docs[kind.key]
		existing = existing_erp_documents(kind, [d["legacy_no"] for d in docs])
		docs.sort(key=lambda d: (d["date"], d["legacy_no"]))

		for legacy_doc in docs:
			erp = existing.get(legacy_doc["legacy_no"])
			if not erp and not in_range(legacy_doc, batch.from_date, batch.to_date):
				# Older document touched in the old system but never imported
				# (from before the migration started) -- not this batch's business.
				continue
			status, message = classify(legacy_doc, erp)
			plan.append(
				{
					"legacy_doc": legacy_doc,
					"kind": kind.key,
					"legacy_no": legacy_doc["legacy_no"],
					"status": status,
					"message": message,
					"erp_name": erp["name"] if erp else None,
					"erp_amount": erp.get("amount") if erp else None,
				}
			)

		seen = {d["legacy_no"] for d in docs}
		for orphan in orphaned_erp_documents(kind, batch.from_date, batch.to_date, seen):
			plan.append(
				{
					"legacy_doc": None,
					"kind": kind.key,
					"legacy_no": orphan.custom_legacy_no,
					"legacy_date": orphan.posting_date,
					"status": "Cancelled in Legacy",
					"message": _("Not found in the old system any more (deleted there)"),
					"erp_name": orphan.name,
					"erp_amount": orphan.get("amount"),
				}
			)
	return plan


def _erp_fields(kind):
	fields = ["name", "docstatus", "custom_legacy_no", "custom_legacy_updated_at", "posting_date"]
	if kind.amount_field:
		fields.append(f"{kind.amount_field} as amount")
	return fields


def existing_erp_documents(kind, legacy_nos):
	"""ERP documents of this kind, keyed by legacy number.

	Matched on (custom_legacy_type, custom_legacy_no): legacy numbers repeat
	across kinds -- a return and a set share the yymm+#### format, and both
	stock kinds become Stock Entries, both payment kinds Journal Entries.
	"""
	existing = {}
	legacy_nos = list(dict.fromkeys(legacy_nos))
	for i in range(0, len(legacy_nos), 500):
		for row in frappe.get_all(
			kind.erp_doctype,
			filters={
				"custom_legacy_type": kind.key,
				"custom_legacy_no": ["in", legacy_nos[i : i + 500]],
				"docstatus": ["<", 2],
			},
			fields=_erp_fields(kind),
		):
			existing[row.custom_legacy_no] = row
	return existing


def orphaned_erp_documents(kind, from_date, to_date, seen_legacy_nos):
	rows = frappe.get_all(
		kind.erp_doctype,
		filters={
			"custom_legacy_type": kind.key,
			"custom_legacy_no": ["is", "set"],
			"docstatus": 1,
			"posting_date": ["between", [from_date, to_date]],
		},
		fields=_erp_fields(kind),
	)
	return [r for r in rows if r.custom_legacy_no not in seen_legacy_nos]


# ---------------------------------------------------------------------------
# Logs + summary
# ---------------------------------------------------------------------------


def drop_stale_logs(batch_name, plan):
	"""Remove log rows from an earlier run of this batch that the current plan
	no longer covers -- e.g. a delivery order that was re-dated in the old
	system. Rows that record something done to ERP (Created, Re-synced, ...)
	are kept, since the ERP document they point at still exists.
	"""
	current = {(e["kind"], e["legacy_no"]) for e in plan}
	for log in frappe.get_all(
		"Legacy Import Log",
		filters={"legacy_import": batch_name, "status": ["not in", FINAL_LOG_STATUSES]},
		fields=["name", "legacy_doctype", "legacy_no"],
	):
		if (log.legacy_doctype, log.legacy_no) not in current:
			frappe.delete_doc("Legacy Import Log", log.name, ignore_permissions=True, force=True)


def write_log(batch_name, entry):
	"""Upsert the batch's log row for this legacy document."""
	legacy_doc = entry.get("legacy_doc") or {}
	name = frappe.db.get_value(
		"Legacy Import Log",
		{"legacy_import": batch_name, "legacy_doctype": entry["kind"], "legacy_no": entry["legacy_no"]},
	)
	log = frappe.get_doc("Legacy Import Log", name) if name else frappe.new_doc("Legacy Import Log")
	if name and log.status in FINAL_LOG_STATUSES and entry["status"] == "Already Imported":
		return log

	kind = get_kind(entry["kind"])
	expected = kind.expected_amount(legacy_doc) if legacy_doc else None

	log.update(
		{
			"legacy_import": batch_name,
			"legacy_doctype": entry["kind"],
			"legacy_no": entry["legacy_no"],
			"legacy_date": legacy_doc.get("date") or entry.get("legacy_date"),
			"legacy_party": legacy_doc.get("party"),
			"legacy_status": legacy_doc.get("status"),
			"legacy_amount": expected,
			"legacy_updated_at": legacy_doc.get("updated_at"),
			"legacy_created_by": legacy_doc.get("created_by"),
			"status": entry["status"],
			"message": entry.get("message"),
			"erp_doctype": kind.erp_doctype if entry.get("erp_name") else None,
			"erp_name": entry.get("erp_name"),
			"erp_amount": entry.get("erp_amount"),
		}
	)
	log.flags.ignore_permissions = True
	log.save()
	return log


def kind_summary(batch_name):
	"""Per kind: document counts by outcome, and old-system vs ERP amounts.

	Amounts are only comparable within one kind (an invoice total and a
	receipt total mean different things), so they are never added across kinds.
	"""
	rows = frappe.db.sql(
		"""
		SELECT legacy_doctype, status, COUNT(*) n,
			SUM(CASE WHEN status NOT IN ('Skipped', 'Cancelled in Legacy', 'Cancelled in ERP')
				THEN legacy_amount ELSE 0 END) legacy_amount,
			SUM(CASE WHEN status IN ('Created', 'Already Imported', 'Changed in Legacy', 'Re-synced', 'Ignored')
				THEN erp_amount ELSE 0 END) erp_amount
		FROM `tabLegacy Import Log` WHERE legacy_import = %s
		GROUP BY legacy_doctype, status
		""",
		batch_name,
		as_dict=True,
	)
	summary = {}
	for kind in ORDERED:
		kind_rows = [r for r in rows if r.legacy_doctype == kind.key]
		if not kind_rows:
			continue
		counts = {r.status: r.n for r in kind_rows}
		summary[kind.key] = {
			"found": sum(counts.values()),
			"created": counts.get("Created", 0) + counts.get("Re-synced", 0),
			"already_imported": counts.get("Already Imported", 0),
			"ready": counts.get("Ready", 0),
			"skipped": counts.get("Skipped", 0),
			"errors": counts.get("Error", 0),
			"changed": counts.get("Changed in Legacy", 0),
			"cancelled_in_legacy": counts.get("Cancelled in Legacy", 0),
			"legacy_amount": flt(sum(flt(r.legacy_amount) for r in kind_rows)) if kind.amount_field else None,
			"erp_amount": flt(sum(flt(r.erp_amount) for r in kind_rows)) if kind.amount_field else None,
		}
	return summary


def update_summary(batch_name, status=None):
	counts = dict(
		frappe.db.sql(
			"SELECT status, COUNT(*) FROM `tabLegacy Import Log` WHERE legacy_import = %s GROUP BY status",
			batch_name,
		)
	)
	totals = frappe.db.sql(
		"""
		SELECT
			SUM(CASE WHEN status NOT IN ('Skipped', 'Cancelled in Legacy', 'Cancelled in ERP')
				THEN legacy_amount ELSE 0 END),
			SUM(CASE WHEN status IN ('Created', 'Already Imported', 'Changed in Legacy', 'Re-synced', 'Ignored')
				THEN erp_amount ELSE 0 END)
		FROM `tabLegacy Import Log` WHERE legacy_import = %s
		""",
		batch_name,
	)[0]

	summary = {
		"found_count": sum(counts.values()),
		"ready_count": counts.get("Ready", 0),
		"created_count": counts.get("Created", 0) + counts.get("Re-synced", 0),
		"already_imported_count": counts.get("Already Imported", 0),
		"skipped_count": counts.get("Skipped", 0),
		"error_count": counts.get("Error", 0),
		"changed_in_legacy_count": counts.get("Changed in Legacy", 0),
		"cancelled_in_legacy_count": counts.get("Cancelled in Legacy", 0),
		"total_legacy_amount": flt(totals[0]),
		"total_erp_amount": flt(totals[1]),
	}
	if status:
		summary["status"] = status
	frappe.db.set_value("Legacy Import", batch_name, summary)
	return summary


# ---------------------------------------------------------------------------
# Admin decisions on a flagged log (Legacy Import Log buttons)
# ---------------------------------------------------------------------------


def resync_log(log):
	"""Cancel the ERP document and re-create it as an amendment from the old system's current data."""
	ensure_enabled()
	kind = get_kind(log.legacy_doctype)
	conn = get_legacy_connection()
	try:
		legacy_doc = fetch_one(conn, kind.key, log.legacy_no)
	finally:
		conn.close()

	if not legacy_doc or not kind.is_confirmed(legacy_doc["status"]):
		frappe.throw(_("{0} is no longer confirmed in the old system; use Cancel in ERP instead.").format(log.legacy_no))

	ctx = build_context(
		[{"legacy_doc": legacy_doc, "kind": kind.key, "legacy_no": log.legacy_no, "status": "Ready"}]
	)

	frappe.flags.bp_legacy_import = True
	try:
		old = frappe.get_doc(kind.erp_doctype, log.erp_name)
		if old.docstatus == 1:
			old.cancel()
		try:
			new = kind.build(legacy_doc, ctx)
		except LegacyImportError as e:
			frappe.throw(str(e))
		new.amended_from = old.name
		new.insert()
		try:
			kind.check(new, legacy_doc, ctx.tolerance)
		except LegacyImportError as e:
			frappe.throw(str(e))
		new.submit()
	finally:
		frappe.flags.bp_legacy_import = False

	log.db_set(
		{
			"status": "Re-synced",
			"erp_doctype": kind.erp_doctype,
			"erp_name": new.name,
			"erp_amount": kind.erp_amount(new),
			"legacy_updated_at": legacy_doc["updated_at"],
			"legacy_status": legacy_doc["status"],
			"legacy_amount": kind.expected_amount(legacy_doc),
			"message": _("Replaced {0} by {1}").format(old.name, new.name),
		}
	)
	update_summary(log.legacy_import)
	return new.name


def cancel_log(log):
	"""Cancel the one ERP document this log points at (the Log's own button)."""
	frappe.flags.bp_legacy_import = True
	try:
		if not cancel_document(log):
			frappe.throw(frappe.db.get_value("Legacy Import Log", log.name, "message"))
	finally:
		frappe.flags.bp_legacy_import = False
	update_summary(log.legacy_import)
	return "Cancelled in ERP"


def ignore_log(log):
	# For a changed document, accept the old system's newer timestamp as seen so
	# the next batch does not flag the same change again.
	if log.status == "Changed in Legacy" and log.legacy_updated_at and log.erp_name:
		frappe.db.set_value(
			_erp_doctype(log), log.erp_name, "custom_legacy_updated_at", log.legacy_updated_at,
			update_modified=False,
		)
	log.db_set({"status": "Ignored", "message": _("Ignored by {0}").format(frappe.session.user)})
	update_summary(log.legacy_import)
	return log.status
