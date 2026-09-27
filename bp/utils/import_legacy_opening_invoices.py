"""Bring the old system's still-unpaid invoices in as ERP opening balances.

Everything from the cut-off date onwards is imported as real documents by
Legacy Import. What came before it is represented by its remaining balance
only, so that payments imported later have something to settle against --
in the old system most receipts pay invoices that are weeks or months old.

This fills ERPNext's own **Opening Invoice Creation Tool** rather than
writing invoices directly: it is the native, supported path, it posts against
the company's Temporary Opening account, and the resulting documents are
flagged `is_opening = Yes` so they stay out of sales/purchase reporting.

Source: `invoices` (AR) / `apinvoice` (AP), every non-cancelled invoice dated
before the cutoff that still owed something **on that date** -- the invoice
amount less the payments made before the cutoff. An invoice paid after the
cutoff still belongs here: its payment is imported as a document later and
needs this invoice to settle against.

One row per legacy invoice (not one per customer), with the legacy number in
`invoice_number` and the original date kept as the posting date, so the AR
ageing in ERP matches the old system. Fiscal Years the old invoices fall into
are created first, because ERPNext refuses to post into a year it does not
know.

Usage (from the bench directory):

    # Dry run first -- prints what would be created, writes nothing.
    bench --site bp.localhost execute bp.utils.import_legacy_opening_invoices.run

    # For real (--kwargs is eval'd as Python, not JSON):
    bench --site bp.localhost execute bp.utils.import_legacy_opening_invoices.run \\
        --kwargs "{'dry_run': False}"

    # Purchase side, or a different cut-off:
    bench --site bp.localhost execute bp.utils.import_legacy_opening_invoices.run \\
        --kwargs "{'invoice_type': 'Purchase', 'cutoff': '2026-01-01', 'dry_run': False}"

The tool inserts each invoice with `set_name = invoice_number`, so the ERP
document is named after the legacy invoice (IF25120123) and no site rule has
to be relaxed -- it also passes `ignore_mandatory`. Re-running is safe: a
legacy number that already exists in ERP is skipped and reported.
"""

import csv
import math
import os

import frappe
from frappe.utils import add_days, flt, formatdate, getdate

from bp.utils.legacy_db import fetch_all, get_legacy_connection

DEFAULT_CUTOFF = "2026-09-01"
# The tool runs its rows inline below 50 and enqueues above it; chunking keeps
# every run synchronous, so what this script reports is what really happened.
CHUNK = 49
# The tool's grid Upload refuses a CSV with more than 5000 data rows
# (frappe/public/js/frappe/form/grid.js, setup_allow_bulk_edit).
UPLOAD_MAX_ROWS = 5000

SOURCES = {
	"Sales": {
		"party_type": "Customer",
		"party_field": "CustCode",
		"table": "invoices",
		"doctype": "Sales Invoice",
		"payment_table": "arpaymen",
		"payment_note": "arrecnot",
		"payment_key": "RecNotNo",
		"payment_date": "RecNotDt",
	},
	"Purchase": {
		"party_type": "Supplier",
		"party_field": "SuppCode",
		"table": "apinvoice",
		"doctype": "Purchase Invoice",
		"payment_table": "appaymen",
		"payment_note": "appaynot",
		"payment_key": "PayNotNo",
		"payment_date": "PayNotDt",
	},
}


def run(
	dry_run=True,
	invoice_type="Sales",
	cutoff=DEFAULT_CUTOFF,
	company=None,
	lift_freeze=False,
	recreate=False,
):
	"""Create opening invoices for legacy invoices still unpaid before `cutoff`.

	recreate: cancel and delete opening invoices carried over on an earlier
	run before creating them again -- needed when the cutoff moves, since the
	balance carried depends on it. Only ever touches invoices flagged
	is_opening whose name is one of the legacy numbers in scope.

	lift_freeze: the company's "Accounts Frozen Till Date" blocks posting into
	the years these invoices belong to, and ERPNext blocks Administrator from
	overriding it whatever roles it holds. Pass True to have the freeze lifted
	for the duration of this run and put back afterwards; the script prints
	both the removal and the restore.
	"""
	if invoice_type not in SOURCES:
		frappe.throw(f"invoice_type must be one of {', '.join(SOURCES)}")
	source = SOURCES[invoice_type]
	company = company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)

	rows = _fetch_unpaid(source, cutoff)
	purged = _purge_existing(source, rows, dry_run, lift_freeze) if recreate else []
	usable, skipped = _check_rows(rows, source, ignore_existing=set(purged))
	missing_years = _ensure_fiscal_years(usable, dry_run)

	created, failed = [], []
	if usable and not dry_run:
		_check_freeze(company, usable, lift_freeze)
		frozen_till = _set_freeze(company, None) if lift_freeze else None
		try:
			for start in range(0, len(usable), CHUNK):
				chunk = usable[start : start + CHUNK]
				_make_chunk(company, invoice_type, source, chunk)
				# The tool names each invoice after the legacy number, which is
				# how we tell afterwards what really got created.
				done = [row for row in chunk if frappe.db.exists(source["doctype"], row["legacy_no"])]
				created += done
				failed += [row for row in chunk if row not in done]
				print(f"  {len(created) + len(failed):>5}/{len(usable)} processed, {len(failed)} failed")
		finally:
			if lift_freeze:
				_set_freeze(company, frozen_till)
				print(f"Accounts Frozen Till Date restored to {frozen_till}.")

	_print_summary(invoice_type, cutoff, rows, usable, skipped, dry_run, missing_years, created, failed, purged)
	return {
		"found": len(rows),
		"purged": len(purged),
		"usable": len(usable),
		"created": len(created),
		"failed": len(failed),
		"skipped": skipped,
	}


def export(invoice_type="Sales", cutoff=DEFAULT_CUTOFF, out_dir=None):
	"""Write the opening invoices as CSV files for the tool's own Upload button.

	For re-doing the opening balances by hand -- e.g. after the training data is
	wiped -- without this script: the same rows `run()` would create, in the
	exact layout the Opening Invoice Creation Tool's grid Download produces and
	its Upload reads back. Nothing is written to the site.

	Layout the grid Upload expects: row 0 title, row 1 labels, row 2
	fieldnames (what it actually maps by), row 3 descriptions, rows 4-6 notes,
	data from row 7; dates in the system date format; at most UPLOAD_MAX_ROWS
	data rows per file, so larger sets are split into equal parts.

	Returns the written paths and the rows, for the caller to summarise.
	"""
	source = SOURCES[invoice_type]
	rows = _fetch_unpaid(source, cutoff)
	# Every row counts, whether or not it is in ERP right now: the file is for
	# a site where these balances have been cleared out again.
	usable, skipped = _check_rows(
		rows, source, ignore_existing={(r["InvoicNo"] or "").strip() for r in rows}
	)
	names = _party_names(source["party_type"], {row["party"] for row in usable})

	meta = frappe.get_meta("Opening Invoice Creation Tool Item")
	from frappe.model import no_value_fields

	fields = [df for df in meta.fields if df.fieldtype not in no_value_fields]
	date_format = frappe.db.get_single_value("System Settings", "date_format") or "dd-mm-yyyy"

	records = []
	for row in usable:
		record = _tool_row(source, invoice_type, row)
		record["party_name"] = names.get(row["party"], "")
		records.append(record)

	out_dir = out_dir or frappe.get_site_path("private", "files", "opening_invoice_upload")
	os.makedirs(out_dir, exist_ok=True)
	parts = max(1, math.ceil(len(records) / UPLOAD_MAX_ROWS))
	per_part = math.ceil(len(records) / parts) if records else 0
	label = "AR" if invoice_type == "Sales" else "AP"
	stamp = getdate(cutoff).strftime("%Y%m%d")

	paths = []
	for part in range(parts):
		chunk = records[part * per_part : (part + 1) * per_part]
		suffix = f"_{part + 1}of{parts}" if parts > 1 else ""
		path = os.path.join(out_dir, f"Opening_Invoice_{label}_cutoff{stamp}{suffix}.csv")
		_write_upload_csv(path, fields, chunk, date_format)
		paths.append(path)

	return {"paths": paths, "records": records, "skipped": skipped}


def _party_names(party_type, codes):
	if not codes:
		return {}
	title = "customer_name" if party_type == "Customer" else "supplier_name"
	return dict(
		frappe.get_all(party_type, filters={"name": ["in", list(codes)]}, fields=["name", title], as_list=True)
	)


def _write_upload_csv(path, fields, records, date_format):
	"""One file in the grid's Bulk Edit layout (see export())."""
	header = [
		["Bulk Edit Invoices"],
		[df.label for df in fields],
		[df.fieldname for df in fields],
		[
			(df.description or "") + (" " + date_format if df.fieldtype == "Date" else "")
			for df in fields
		],
		["The CSV format is case sensitive"],
		["Do not edit headers which are preset in the template"],
		["------"],
	]
	with open(path, "w", newline="", encoding="utf-8") as f:
		writer = csv.writer(f)
		writer.writerows(header)
		for record in records:
			writer.writerow([_upload_value(df, record.get(df.fieldname)) for df in fields])


def _upload_value(df, value):
	if value in (None, ""):
		return ""
	if df.fieldtype == "Date":
		# The Upload converts with the user's date format, so write it in that.
		return formatdate(value)
	if df.fieldtype == "Currency":
		# Plain digits and a dot: grouping separators would be misread by flt().
		return f"{flt(value, 2):.2f}"
	return value


def _tool_row(source, invoice_type, row):
	return {
		"party_type": source["party_type"],
		"party": row["party"],
		"outstanding_amount": row["outstanding"],
		"posting_date": row["date"],
		"due_date": row["due_date"],
		"invoice_number": row["legacy_no"],
		"item_name": f"Saldo awal {row['legacy_no']}",
		"qty": 1,
		# On the purchase side this becomes the Purchase Invoice's Supplier
		# Invoice Date, keeping the bill's own date visible.
		"supplier_invoice_date": row["date"] if invoice_type == "Purchase" else None,
	}


def _make_chunk(company, invoice_type, source, chunk):
	"""Hand one chunk to the Opening Invoice Creation Tool (a Single doctype).

	Kept under the tool's own 50-row threshold so it creates the invoices
	inline instead of enqueueing them, which is what lets this script report
	what actually happened rather than what it asked for.
	"""
	tool = frappe.get_single("Opening Invoice Creation Tool")
	tool.company = company
	tool.invoice_type = invoice_type
	tool.create_missing_party = 0
	tool.set("invoices", [])
	for row in chunk:
		tool.append("invoices", _tool_row(source, invoice_type, row))
	tool.save()
	tool.make_invoices()
	frappe.db.commit()


def _purge_existing(source, rows, dry_run, lift_freeze):
	"""Remove opening invoices carried over by an earlier run of this script."""
	names = [
		row["InvoicNo"].strip()
		for row in rows
		if frappe.db.get_value(source["doctype"], row["InvoicNo"].strip(), "is_opening") == "Yes"
	]
	if dry_run or not names:
		return names

	company = frappe.db.get_value(source["doctype"], names[0], "company")
	frozen_till = _set_freeze(company, None) if lift_freeze else None
	try:
		for name in names:
			doc = frappe.get_doc(source["doctype"], name)
			if doc.docstatus == 1:
				doc.cancel()
			doc.delete()
			frappe.db.commit()
	finally:
		if lift_freeze:
			_set_freeze(company, frozen_till)
	return names


def _fetch_unpaid(source, cutoff):
	"""Invoices still owing **on the cutoff date**.

	Not "still owing today": an invoice from before the cutoff that was paid
	afterwards was part of the balance being carried over, and the payment
	that settled it is imported as a document later -- it needs this invoice
	to settle against. What is carried is therefore the invoice amount less
	only the payments made before the cutoff.
	"""
	conn = get_legacy_connection()
	try:
		return fetch_all(
			conn,
			f"""
			SELECT i.InvoicNo, i.InvDate, i.{source["party_field"]} AS party, i.CredTerm, i.AmtInv,
				IFNULL(SUM(CASE WHEN n.{source["payment_date"]} < %s AND n.RNStatus <> 9
					THEN p.AmonPaid END), 0) AS paid_before
			FROM {source["table"]} i
			LEFT JOIN {source["payment_table"]} p ON p.InvoDNNo = i.InvoicNo
			LEFT JOIN {source["payment_note"]} n ON n.{source["payment_key"]} = p.{source["payment_key"]}
			WHERE i.InvDate < %s AND i.InvStatu <> 9
			GROUP BY i.InvoicNo, i.InvDate, i.{source["party_field"]}, i.CredTerm, i.AmtInv
			HAVING i.AmtInv - paid_before > 0
			ORDER BY i.InvDate, i.InvoicNo
			""",
			(getdate(cutoff), getdate(cutoff)),
		)
	finally:
		conn.close()


def _check_rows(rows, source, ignore_existing=()):
	"""Split the legacy rows into what can be imported and what cannot.

	ignore_existing holds the legacy numbers being replaced this run: on a dry
	run they are still in ERP, and counting them as "already there" would
	understate what the real run would create.
	"""
	usable, skipped = [], {"party_missing": [], "already_in_erp": [], "zero_amount": []}
	for row in rows:
		legacy_no = (row["InvoicNo"] or "").strip()
		party = (row["party"] or "").strip()
		outstanding = flt(row["AmtInv"]) - flt(row["paid_before"])
		date = getdate(row["InvDate"])

		if outstanding <= 0:
			skipped["zero_amount"].append(legacy_no)
			continue
		if not frappe.db.exists(source["party_type"], party):
			skipped["party_missing"].append(f"{legacy_no} ({party})")
			continue
		# The tool names each invoice after the legacy number, so that name
		# existing already means this balance was carried over before.
		if legacy_no not in ignore_existing and frappe.db.exists(source["doctype"], legacy_no):
			skipped["already_in_erp"].append(legacy_no)
			continue

		usable.append(
			{
				"legacy_no": legacy_no,
				"party": party,
				"outstanding": outstanding,
				"date": date,
				"due_date": add_days(date, int(row["CredTerm"] or 0)),
			}
		)
	return usable, skipped


def _ensure_fiscal_years(usable, dry_run):
	"""Create the Fiscal Years the old invoices fall into.

	These invoices keep their real dates so AR ageing matches the old system,
	and ERPNext refuses to post into a year it does not know
	(FiscalYearError). The years created are empty apart from these opening
	balances.
	"""
	if not usable:
		return []

	oldest = min(row["date"] for row in usable).year
	existing = set(frappe.get_all("Fiscal Year", pluck="name"))
	newest = min(int(y) for y in existing if y.isdigit()) if existing else oldest

	missing = [str(year) for year in range(oldest, newest) if str(year) not in existing]
	if dry_run:
		return missing

	for year in missing:
		frappe.get_doc(
			{
				"doctype": "Fiscal Year",
				"year": year,
				"year_start_date": f"{year}-01-01",
				"year_end_date": f"{year}-12-31",
			}
		).insert(ignore_permissions=True)
	frappe.db.commit()
	return missing


def _check_freeze(company, usable, lift_freeze):
	"""Stop early, with the options spelled out, when the books are frozen."""
	frozen_till = frappe.db.get_value("Company", company, "accounts_frozen_till_date")
	if not frozen_till or lift_freeze:
		return
	if min(row["date"] for row in usable) > getdate(frozen_till):
		return
	frappe.throw(
		f"{company} has Accounts Frozen Till Date = {frozen_till}, and these opening invoices are "
		f"dated before it. ERPNext blocks Administrator from posting past a freeze whatever roles it "
		f"holds. Either re-run with lift_freeze=True (the freeze is removed for the run and put back "
		f"straight after), or clear the date on the Company yourself first."
	)


def _set_freeze(company, value):
	previous = frappe.db.get_value("Company", company, "accounts_frozen_till_date")
	frappe.db.set_value("Company", company, "accounts_frozen_till_date", value)
	frappe.db.commit()
	if value is None:
		print(f"Accounts Frozen Till Date ({previous}) lifted for this run.")
	return previous


def _print_summary(invoice_type, cutoff, rows, usable, skipped, dry_run, missing_years, created, failed, purged):
	mode = "(DRY RUN, nothing written)" if dry_run else "(COMMITTED)"
	total = sum(r["outstanding"] for r in usable)
	print(f"\n--- legacy opening invoices {mode} ---")
	print(f"Type:                 {invoice_type} (before {cutoff})")
	print(f"Legacy rows open:     {len(rows)}")
	if purged:
		verb = "would be replaced" if dry_run else "replaced"
		print(f"Earlier openings {verb}: {len(purged)}")
	print(f"Opening invoices:     {len(usable)}" + ("" if dry_run else f" -> created {len(created)}, failed {len(failed)}"))
	print(f"Total outstanding:    {total:,.2f}")
	print(f"Parties:              {len({r['party'] for r in usable})}")
	for reason, items in skipped.items():
		if items:
			print(f"Skipped - {reason}: {len(items)} -> {', '.join(items[:5])}{' ...' if len(items) > 5 else ''}")
	if usable:
		oldest, newest = min(r["date"] for r in usable), max(r["date"] for r in usable)
		print(f"Invoice dates:        {oldest} .. {newest}")
	if missing_years:
		verb = "would be created" if dry_run else "created"
		print(f"Fiscal Years {verb}: {', '.join(missing_years)}")
	if dry_run:
		print("\nThis was a dry run. Re-run with --kwargs \"{'dry_run': False}\" to write.")
	elif failed:
		print(f"\nFAILED ({len(failed)}): {', '.join(r['legacy_no'] for r in failed[:10])}")
		print("See Error Log 'Opening invoice creation failed' for the reason of each.")
