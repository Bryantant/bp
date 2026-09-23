"""Preview / run / re-sync for the Legacy Import doctype.

Flow for one batch (a date range):
1. Pull every delivery order / receiving in the range from the old system,
   plus older ones touched (LasUpdDt) since the range start.
2. Classify each against ERP by Old System No (custom_legacy_no):
	- confirmed, not in ERP             -> Ready (Run creates + submits it)
	- confirmed, in ERP, unchanged      -> Already Imported
	- confirmed, in ERP, newer LasUpdDt -> Changed in Legacy
	- draft/cancelled, in ERP           -> Cancelled in Legacy
	- draft/cancelled, not in ERP       -> Skipped
   plus ERP documents in the range whose number no longer exists in the old
   system at all (a reversed draft that was then deleted) -> Cancelled in Legacy.
3. Run: create + submit each Ready document in its own transaction, so one
   bad document never blocks the rest of the day. Receivings go first so the
   day's goods are in stock before that day's sales take them out.

"Changed/Cancelled in Legacy" are only flagged -- an admin decides per
document from the Legacy Import Log (re-sync / cancel in ERP / ignore).
Running a batch again is safe: nothing already in ERP is created twice.
"""

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, getdate, now_datetime, strip_html

from bp.utils.legacy_db import get_legacy_connection
from bp.utils.legacy_import import (
	CONFIRMED_STATUSES,
	PURCHASE_INVOICE,
	SALES_INVOICE,
	LegacyImportError,
	legacy_status_label,
)
from bp.utils.legacy_import import purchase_invoice as pi_mapper
from bp.utils.legacy_import import sales_invoice as si_mapper
from bp.utils.legacy_import.context import ImportContext
from bp.utils.legacy_import.source import fetch_one, fetch_purchase_invoices, fetch_sales_invoices

BUILDERS = {
	SALES_INVOICE: (si_mapper.build_sales_invoice, si_mapper.expected_amount),
	PURCHASE_INVOICE: (pi_mapper.build_purchase_invoice, pi_mapper.expected_amount),
}
# Log statuses that record something done to ERP; a later preview/run of the
# same batch must not overwrite them with "Already Imported".
FINAL_LOG_STATUSES = ("Created", "Re-synced", "Cancelled in ERP", "Ignored")
PROGRESS_EVENT = "legacy_import_progress"


# ---------------------------------------------------------------------------
# Classification (pure -- unit tested without a legacy connection)
# ---------------------------------------------------------------------------


def classify(legacy_doc, existing):
	"""Return (status, message) for a legacy doc given its ERP doc (dict or None)."""
	confirmed = legacy_doc["status"] in CONFIRMED_STATUSES[legacy_doc["doctype"]]
	label = legacy_status_label(legacy_doc["status"])

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
	ctx = ImportContext().prefetch([p["legacy_doc"] for p in plan if p["legacy_doc"]])
	drop_stale_logs(batch.name, plan)

	for entry in plan:
		if entry["status"] == "Ready":
			try:
				BUILDERS[entry["legacy_doc"]["doctype"]][0](entry["legacy_doc"], ctx)
			except LegacyImportError as e:
				entry["status"], entry["message"] = "Error", str(e)
		write_log(batch.name, entry)

	update_summary(batch.name, status="Previewed")
	frappe.db.commit()


def enqueue_run(batch):
	ensure_enabled()
	running = frappe.get_all(
		"Legacy Import",
		filters={"status": ["in", ("Queued", "Running")], "name": ["!=", batch.name]},
		pluck="name",
	)
	if running:
		frappe.throw(_("Legacy Import {0} is still running. Wait for it to finish.").format(running[0]))
	if batch.status in ("Queued", "Running"):
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
		ctx = ImportContext().prefetch([p["legacy_doc"] for p in plan if p["legacy_doc"]])
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
	build, expected_amount = BUILDERS[legacy_doc["doctype"]]
	try:
		doc = build(legacy_doc, ctx)
		doc.insert()
		check_amount(doc, expected_amount(legacy_doc), ctx.tolerance)
		doc.submit()
		entry.update(status="Created", erp_name=doc.name, erp_amount=doc.grand_total, message=None)
	except Exception as e:
		frappe.db.rollback()
		entry.update(status="Error", erp_name=None, erp_amount=None, message=error_text(e))
		if not isinstance(e, (LegacyImportError, frappe.ValidationError)):
			frappe.log_error(title=f"Legacy Import {legacy_doc['legacy_no']} failed")
	finally:
		frappe.clear_messages()


def check_amount(doc, expected, tolerance):
	difference = flt(doc.grand_total) - flt(expected)
	if abs(difference) > flt(tolerance):
		raise LegacyImportError(
			f"ERP total {flt(doc.grand_total):,.2f} differs from old system total {flt(expected):,.2f} "
			f"by {difference:,.2f} (tolerance {flt(tolerance):,.2f})"
		)


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
	"""Return the batch's plan: one entry per legacy doc (and per orphaned ERP doc)."""
	legacy_docs = []
	conn = get_legacy_connection()
	try:
		# Receivings first: see module docstring.
		if batch.import_purchase_invoice:
			legacy_docs += fetch_purchase_invoices(conn, batch.from_date, batch.to_date)
		if batch.import_sales_invoice:
			legacy_docs += fetch_sales_invoices(conn, batch.from_date, batch.to_date)
	finally:
		conn.close()

	plan = []
	for doctype in (PURCHASE_INVOICE, SALES_INVOICE):
		docs = [d for d in legacy_docs if d["doctype"] == doctype]
		if not docs and not _selected(batch, doctype):
			continue
		existing = existing_erp_documents(doctype, [d["legacy_no"] for d in docs])
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
					"doctype": doctype,
					"legacy_no": legacy_doc["legacy_no"],
					"status": status,
					"message": message,
					"erp_name": erp["name"] if erp else None,
					"erp_amount": erp["grand_total"] if erp else None,
				}
			)

		seen = {d["legacy_no"] for d in docs}
		for orphan in orphaned_erp_documents(doctype, batch.from_date, batch.to_date, seen):
			plan.append(
				{
					"legacy_doc": None,
					"doctype": doctype,
					"legacy_no": orphan.custom_legacy_no,
					"legacy_date": orphan.posting_date,
					"status": "Cancelled in Legacy",
					"message": _("Not found in the old system any more (deleted there)"),
					"erp_name": orphan.name,
					"erp_amount": orphan.grand_total,
				}
			)
	return plan


def _selected(batch, doctype):
	return batch.import_sales_invoice if doctype == SALES_INVOICE else batch.import_purchase_invoice


def existing_erp_documents(doctype, legacy_nos):
	existing = {}
	legacy_nos = list(dict.fromkeys(legacy_nos))
	for i in range(0, len(legacy_nos), 500):
		for row in frappe.get_all(
			doctype,
			filters={"custom_legacy_no": ["in", legacy_nos[i : i + 500]], "docstatus": ["<", 2]},
			fields=["name", "docstatus", "custom_legacy_no", "custom_legacy_updated_at", "grand_total"],
		):
			existing[row.custom_legacy_no] = row
	return existing


def orphaned_erp_documents(doctype, from_date, to_date, seen_legacy_nos):
	rows = frappe.get_all(
		doctype,
		filters={
			"custom_legacy_no": ["is", "set"],
			"docstatus": 1,
			"posting_date": ["between", [from_date, to_date]],
		},
		fields=["name", "custom_legacy_no", "posting_date", "grand_total"],
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
	current = {(e["doctype"], e["legacy_no"]) for e in plan}
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
		{"legacy_import": batch_name, "legacy_doctype": entry["doctype"], "legacy_no": entry["legacy_no"]},
	)
	log = frappe.get_doc("Legacy Import Log", name) if name else frappe.new_doc("Legacy Import Log")
	if name and log.status in FINAL_LOG_STATUSES and entry["status"] == "Already Imported":
		return log

	expected = None
	if legacy_doc:
		expected = BUILDERS[entry["doctype"]][1](legacy_doc)

	log.update(
		{
			"legacy_import": batch_name,
			"legacy_doctype": entry["doctype"],
			"legacy_no": entry["legacy_no"],
			"legacy_date": legacy_doc.get("date") or entry.get("legacy_date"),
			"legacy_party": legacy_doc.get("party"),
			"legacy_status": legacy_doc.get("status"),
			"legacy_amount": expected,
			"legacy_updated_at": legacy_doc.get("updated_at"),
			"legacy_created_by": legacy_doc.get("created_by"),
			"status": entry["status"],
			"message": entry.get("message"),
			"erp_doctype": entry["doctype"] if entry.get("erp_name") else None,
			"erp_name": entry.get("erp_name"),
			"erp_amount": entry.get("erp_amount"),
		}
	)
	log.flags.ignore_permissions = True
	log.save()
	return log


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
	conn = get_legacy_connection()
	try:
		legacy_doc = fetch_one(conn, log.legacy_doctype, log.legacy_no)
	finally:
		conn.close()

	if not legacy_doc or legacy_doc["status"] not in CONFIRMED_STATUSES[log.legacy_doctype]:
		frappe.throw(_("{0} is no longer confirmed in the old system; use Cancel in ERP instead.").format(log.legacy_no))

	ctx = ImportContext().prefetch([legacy_doc])
	build, expected_amount = BUILDERS[log.legacy_doctype]

	frappe.flags.bp_legacy_import = True
	try:
		old = frappe.get_doc(log.legacy_doctype, log.erp_name)
		if old.docstatus == 1:
			old.cancel()
		try:
			new = build(legacy_doc, ctx)
		except LegacyImportError as e:
			frappe.throw(str(e))
		new.amended_from = old.name
		new.insert()
		try:
			check_amount(new, expected_amount(legacy_doc), ctx.tolerance)
		except LegacyImportError as e:
			frappe.throw(str(e))
		new.submit()
	finally:
		frappe.flags.bp_legacy_import = False

	log.db_set(
		{
			"status": "Re-synced",
			"erp_doctype": log.legacy_doctype,
			"erp_name": new.name,
			"erp_amount": new.grand_total,
			"legacy_updated_at": legacy_doc["updated_at"],
			"legacy_status": legacy_doc["status"],
			"legacy_amount": expected_amount(legacy_doc),
			"message": _("Replaced {0} by {1}").format(old.name, new.name),
		}
	)
	update_summary(log.legacy_import)
	return new.name


def cancel_log(log):
	doc = frappe.get_doc(log.legacy_doctype, log.erp_name)
	if doc.docstatus == 1:
		doc.cancel()
	elif doc.docstatus == 0:
		doc.delete()
	log.db_set({"status": "Cancelled in ERP", "message": _("Cancelled by {0}").format(frappe.session.user)})
	update_summary(log.legacy_import)
	return log.status


def ignore_log(log):
	# For a changed document, accept the old system's newer timestamp as seen so
	# the next batch does not flag the same change again.
	if log.status == "Changed in Legacy" and log.legacy_updated_at and log.erp_name:
		frappe.db.set_value(
			log.legacy_doctype, log.erp_name, "custom_legacy_updated_at", log.legacy_updated_at,
			update_modified=False,
		)
	log.db_set({"status": "Ignored", "message": _("Ignored by {0}").format(frappe.session.user)})
	update_summary(log.legacy_import)
	return log.status
