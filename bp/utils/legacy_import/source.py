"""Read-only queries against the legacy trading database.

Every fetch returns "legacy docs": plain dicts shaped the same for both
document types so the runner does not care which table they came from:

	{doctype, legacy_no, date, party, status, updated_at, created_by,
	 amount, header, lines}

`amount` is the old system's own AR/AP invoice total (invoices.AmtInv /
apinvoice.AmtInv, keyed "I" + document number), or None when that row does
not exist -- e.g. the document is still a draft, since Confirm is what
creates it and Reverse/Cancel delete it.
"""

from datetime import timedelta

from frappe.utils import getdate

from bp.utils.legacy_db import fetch_all
from bp.utils.legacy_import import PURCHASE_INVOICE, SALES_INVOICE

IN_CHUNK = 500

SALES_HEADER_SQL = """
	SELECT d.DONumber, d.DODatesx, d.CustCode, d.SaleCode, d.BranchCode, d.CurrCode,
		d.CredTerm, d.CashFlag, d.CustPONo, d.OrderByx, d.DONotesx, d.DOStatus,
		d.disc1, d.ndisc1, d.CreaUser, d.CreaDate, d.LasUpdDt, i.AmtInv
	FROM deliorde d
	LEFT JOIN invoices i ON i.InvoicNo = CONCAT('I', d.DONumber)
"""

SALES_LINES_SQL = """
	SELECT DONumber, RowNumber, ItemCode, DescTamb, Quantity, UnitMeas, Packing, Price,
		DiscPerc, DiscAmnt, DiscPerc2, DiscAmnt2, Discamnt3, BranchCode
	FROM dodetail WHERE DONumber IN ({placeholders})
	ORDER BY DONumber, RowNumber
"""

PURCHASE_HEADER_SQL = """
	SELECT r.RecDOrNo, r.RecDOrDt, r.SuppCode, r.SuppDONo, r.BranchCode, r.CredTerm,
		r.CashFlag, r.RecDOrNt, r.RecDOrSt, r.PONo, r.CreaUser, r.CreaDate, r.LasUpdDt,
		a.AmtInv, a.CurrCode
	FROM pcrecdor r
	LEFT JOIN apinvoice a ON a.InvoicNo = CONCAT('I', r.RecDOrNo)
"""

PURCHASE_LINES_SQL = """
	SELECT RecDOrNo, SequNumb, ItemCode, Quantity, UnitMeas, Packing, Price, CurrCode,
		DiscPerc, DiscAmt
	FROM pcrddeta WHERE RecDOrNo IN ({placeholders})
	ORDER BY RecDOrNo, SequNumb
"""


def fetch_sales_invoices(conn, from_date, to_date, include_updated_before=True):
	"""Delivery orders dated in [from_date, to_date].

	With include_updated_before, also returns older delivery orders whose
	LasUpdDt falls on/after from_date -- the runner keeps those only if they
	were already imported, to catch a Reverse/edit of an earlier day.
	"""
	from_date, to_date = getdate(from_date), getdate(to_date)
	headers = fetch_all(conn, SALES_HEADER_SQL + " WHERE d.DODatesx BETWEEN %s AND %s", (from_date, to_date))
	if include_updated_before:
		headers += fetch_all(
			conn,
			SALES_HEADER_SQL + " WHERE d.DODatesx < %s AND d.LasUpdDt >= %s",
			(from_date, from_date),
		)
	lines = _fetch_lines(conn, SALES_LINES_SQL, [h["DONumber"] for h in headers], "DONumber")
	return [
		{
			"doctype": SALES_INVOICE,
			"legacy_no": h["DONumber"],
			"date": getdate(h["DODatesx"]),
			"party": h["CustCode"],
			"status": h["DOStatus"],
			"updated_at": h["LasUpdDt"],
			"created_by": h["CreaUser"],
			"amount": h["AmtInv"],
			"header": h,
			"lines": lines.get(h["DONumber"], []),
		}
		for h in headers
	]


def fetch_purchase_invoices(conn, from_date, to_date, include_updated_before=True):
	"""Receivings dated in [from_date, to_date]; see fetch_sales_invoices."""
	from_date, to_date = getdate(from_date), getdate(to_date)
	# RecDOrDt is a DATETIME: use a half-open range so a stray time part
	# on the last day is not lost.
	headers = fetch_all(
		conn,
		PURCHASE_HEADER_SQL + " WHERE r.RecDOrDt >= %s AND r.RecDOrDt < %s",
		(from_date, to_date + timedelta(days=1)),
	)
	if include_updated_before:
		headers += fetch_all(
			conn,
			PURCHASE_HEADER_SQL + " WHERE r.RecDOrDt < %s AND r.LasUpdDt >= %s",
			(from_date, from_date),
		)
	lines = _fetch_lines(conn, PURCHASE_LINES_SQL, [h["RecDOrNo"] for h in headers], "RecDOrNo")
	return [
		{
			"doctype": PURCHASE_INVOICE,
			"legacy_no": h["RecDOrNo"],
			"date": getdate(h["RecDOrDt"]),
			"party": h["SuppCode"],
			"status": h["RecDOrSt"],
			"updated_at": h["LasUpdDt"],
			"created_by": h["CreaUser"],
			"amount": h["AmtInv"],
			"header": h,
			"lines": lines.get(h["RecDOrNo"], []),
		}
		for h in headers
	]


def fetch_one(conn, doctype, legacy_no):
	if doctype == SALES_INVOICE:
		headers = fetch_all(conn, SALES_HEADER_SQL + " WHERE d.DONumber = %s", (legacy_no,))
		date_field, fetch = "DODatesx", fetch_sales_invoices
	else:
		headers = fetch_all(conn, PURCHASE_HEADER_SQL + " WHERE r.RecDOrNo = %s", (legacy_no,))
		date_field, fetch = "RecDOrDt", fetch_purchase_invoices
	if not headers:
		return None
	day = getdate(headers[0][date_field])
	return next(
		(d for d in fetch(conn, day, day, include_updated_before=False) if d["legacy_no"] == legacy_no),
		None,
	)


def _fetch_lines(conn, sql, numbers, key):
	grouped = {}
	numbers = list(dict.fromkeys(numbers))
	for i in range(0, len(numbers), IN_CHUNK):
		chunk = numbers[i : i + IN_CHUNK]
		rows = fetch_all(conn, sql.format(placeholders=", ".join(["%s"] * len(chunk))), chunk)
		for row in rows:
			grouped.setdefault(row[key], []).append(row)
	return grouped
