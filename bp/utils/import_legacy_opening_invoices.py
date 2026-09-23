"""Bring the old system's still-unpaid invoices in as ERP opening balances.

Everything from the cut-off date onwards is imported as real documents by
Legacy Import. What came before it is represented by its remaining balance
only, so that payments imported later have something to settle against --
in the old system most receipts pay invoices that are weeks or months old.

This fills ERPNext's own **Opening Invoice Creation Tool** rather than
writing invoices directly: it is the native, supported path, it posts against
the company's Temporary Opening account, and the resulting documents are
flagged `is_opening = Yes` so they stay out of sales/purchase reporting.

Source: `invoices` (AR) / `apinvoice` (AP), rows whose status is neither Full
Paid (5) nor Cancelled (9) and where AmtInv > AmtPaid. The **remaining**
amount is what is carried over, not the original invoice value, so an invoice
already half paid in the old system comes in at its balance.

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

import frappe
from frappe.utils import add_days, flt, getdate

from bp.utils.legacy_db import fetch_all, get_legacy_connection

DEFAULT_CUTOFF = "2026-01-01"
# Legacy InvStatu: 5 = Full Paid, 9 = Cancelled -- everything else can still owe.
SETTLED_STATUSES = (5, 9)

SOURCES = {
	"Sales": {
		"party_type": "Customer",
		"party_field": "CustCode",
		"table": "invoices",
		"doctype": "Sales Invoice",
	},
	"Purchase": {
		"party_type": "Supplier",
		"party_field": "SuppCode",
		"table": "apinvoice",
		"doctype": "Purchase Invoice",
	},
}


def run(dry_run=True, invoice_type="Sales", cutoff=DEFAULT_CUTOFF, company=None, lift_freeze=False):
	"""Create opening invoices for legacy invoices still unpaid before `cutoff`.

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
	usable, skipped = _check_rows(rows, source)
	missing_years = _ensure_fiscal_years(usable, dry_run)

	tool = frappe.new_doc("Opening Invoice Creation Tool")
	tool.company = company
	tool.invoice_type = invoice_type
	tool.create_missing_party = 0
	for row in usable:
		tool.append(
			"invoices",
			{
				"party_type": source["party_type"],
				"party": row["party"],
				"outstanding_amount": row["outstanding"],
				"posting_date": row["date"],
				"due_date": row["due_date"],
				"invoice_number": row["legacy_no"],
				"item_name": f"Saldo awal {row['legacy_no']}",
				"qty": 1,
				# On the purchase side this becomes the Purchase Invoice's
				# Supplier Invoice Date, keeping the bill's own date visible.
				"supplier_invoice_date": row["date"] if invoice_type == "Purchase" else None,
			},
		)

	created, failed = [], []
	if usable and not dry_run:
		_check_freeze(company, usable, lift_freeze)
		frozen_till = _set_freeze(company, None) if lift_freeze else None
		try:
			tool.insert()
			# The tool inserts each invoice with set_name = invoice_number, so
			# the ERP document is named after the legacy invoice (IF25120123),
			# which is also how we tell afterwards what really got created.
			tool.make_invoices()
			frappe.db.commit()
		finally:
			if lift_freeze:
				_set_freeze(company, frozen_till)
				print(f"Accounts Frozen Till Date restored to {frozen_till}.")
		created = [row for row in usable if frappe.db.exists(source["doctype"], row["legacy_no"])]
		failed = [row for row in usable if row not in created]
		_fix_purchase_invoice_type(invoice_type, created)

	_print_summary(invoice_type, cutoff, rows, usable, skipped, dry_run, tool, missing_years, created, failed)
	return {
		"found": len(rows),
		"usable": len(usable),
		"created": len(created),
		"failed": len(failed),
		"skipped": skipped,
	}


def _fetch_unpaid(source, cutoff):
	conn = get_legacy_connection()
	try:
		return fetch_all(
			conn,
			f"""
			SELECT InvoicNo, InvDate, {source["party_field"]} AS party, CredTerm,
				AmtInv, AmtPaid, InvStatu
			FROM {source["table"]}
			WHERE InvDate < %s AND InvStatu NOT IN %s AND AmtInv > AmtPaid
			ORDER BY InvDate, InvoicNo
			""",
			(getdate(cutoff), SETTLED_STATUSES),
		)
	finally:
		conn.close()


def _check_rows(rows, source):
	"""Split the legacy rows into what can be imported and what cannot."""
	usable, skipped = [], {"party_missing": [], "already_in_erp": [], "zero_amount": []}
	for row in rows:
		legacy_no = (row["InvoicNo"] or "").strip()
		party = (row["party"] or "").strip()
		outstanding = flt(row["AmtInv"]) - flt(row["AmtPaid"])
		date = getdate(row["InvDate"])

		if outstanding <= 0:
			skipped["zero_amount"].append(legacy_no)
			continue
		if not frappe.db.exists(source["party_type"], party):
			skipped["party_missing"].append(f"{legacy_no} ({party})")
			continue
		# The tool names each invoice after the legacy number, so that name
		# existing already means this balance was carried over before.
		if frappe.db.exists(source["doctype"], legacy_no):
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


def _fix_purchase_invoice_type(invoice_type, created):
	"""Label opening Purchase Invoices as Credit.

	custom_invoice_type is a mandatory Select the tool knows nothing about, so
	Frappe fills it with the first option ("Cash") -- wrong for a balance that
	is still outstanding. It only labels the document here: the name was set
	from the legacy number, so the Cash/Credit naming series is not involved.
	"""
	if invoice_type != "Purchase":
		return
	for row in created:
		frappe.db.set_value(
			"Purchase Invoice", row["legacy_no"], "custom_invoice_type", "Credit", update_modified=False
		)
	frappe.db.commit()


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


def _print_summary(invoice_type, cutoff, rows, usable, skipped, dry_run, tool, missing_years, created, failed):
	mode = "(DRY RUN, nothing written)" if dry_run else "(COMMITTED)"
	total = sum(r["outstanding"] for r in usable)
	print(f"\n--- legacy opening invoices {mode} ---")
	print(f"Type:                 {invoice_type} (before {cutoff})")
	print(f"Legacy rows unpaid:   {len(rows)}")
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
