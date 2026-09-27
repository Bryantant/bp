"""Read-only queries against the legacy trading database.

Every fetch returns "legacy docs": plain dicts shaped the same for every kind
so the runner does not care which table they came from:

	{kind, legacy_no, date, party, status, updated_at, created_by,
	 amount, header, lines}

`amount` is the old system's own AR/AP invoice total for delivery orders and
receivings (invoices.AmtInv / apinvoice.AmtInv, keyed "I" + document number),
or None when there is no such row -- a draft, since Confirm is what creates
it, or a kind that has no invoice at all. Builders compute an expected total
from the lines when it is None.

Each kind is described by a SourceSpec; `fetch()` and `fetch_one()` work for
all of them.
"""

from dataclasses import dataclass
from datetime import timedelta

from frappe.utils import add_days, flt, getdate

from bp.utils.legacy_db import fetch_all
from bp.utils.legacy_import import (
	AP_PAYMENT,
	AR_RECEIPT,
	PURCHASE_INVOICE,
	SALES_INVOICE,
	SALES_RETURN,
	STOCK_MUTATION,
	STOCK_SET,
)

IN_CHUNK = 500


@dataclass(frozen=True)
class SourceSpec:
	header_sql: str  # SELECT ... FROM <table> h [LEFT JOIN ...]; no WHERE
	date_col: str  # qualified date column used for the range
	key: str  # document-number column in the header result
	status: str  # status column in the header result
	party: str | None  # customer/supplier column in the header result
	lines_sql: str | None  # "... WHERE <key> IN ({placeholders}) ORDER BY ..."
	amount: str | None = None  # legacy invoice total column, if any


SPECS = {
	SALES_INVOICE: SourceSpec(
		header_sql="""
			SELECT h.DONumber, h.DODatesx, h.CustCode, h.SaleCode, h.BranchCode, h.CurrCode,
				h.CredTerm, h.CashFlag, h.CustPONo, h.OrderByx, h.DONotesx, h.DOStatus,
				h.disc1, h.ndisc1, h.CreaUser, h.CreaDate, h.LasUpdDt, i.AmtInv
			FROM deliorde h
			LEFT JOIN invoices i ON i.InvoicNo = CONCAT('I', h.DONumber)
		""",
		date_col="h.DODatesx",
		key="DONumber",
		status="DOStatus",
		party="CustCode",
		lines_sql="""
			SELECT DONumber, RowNumber, ItemCode, DescTamb, Quantity, UnitMeas, Packing, Price,
				DiscPerc, DiscAmnt, DiscPerc2, DiscAmnt2, Discamnt3, BranchCode
			FROM dodetail WHERE DONumber IN ({placeholders})
			ORDER BY DONumber, RowNumber
		""",
		amount="AmtInv",
	),
	PURCHASE_INVOICE: SourceSpec(
		header_sql="""
			SELECT h.RecDOrNo, h.RecDOrDt, h.SuppCode, h.SuppDONo, h.BranchCode, h.CredTerm,
				h.CashFlag, h.RecDOrNt, h.RecDOrSt, h.PONo, h.CreaUser, h.CreaDate, h.LasUpdDt,
				a.AmtInv, a.CurrCode
			FROM pcrecdor h
			LEFT JOIN apinvoice a ON a.InvoicNo = CONCAT('I', h.RecDOrNo)
		""",
		date_col="h.RecDOrDt",
		key="RecDOrNo",
		status="RecDOrSt",
		party="SuppCode",
		lines_sql="""
			SELECT RecDOrNo, SequNumb, ItemCode, Quantity, UnitMeas, Packing, Price, CurrCode,
				DiscPerc, DiscAmt
			FROM pcrddeta WHERE RecDOrNo IN ({placeholders})
			ORDER BY RecDOrNo, SequNumb
		""",
		amount="AmtInv",
	),
	SALES_RETURN: SourceSpec(
		header_sql="""
			SELECT h.SalRetNo, h.SalRetDt, h.CustCode, h.SaleCode, h.CurrCode, h.SalRetNt,
				h.SalRetSt, h.BranchCode, h.Rusak, h.CreaUser, h.CreaDate, h.LasUpdDt
			FROM saleretu h
		""",
		date_col="h.SalRetDt",
		key="SalRetNo",
		status="SalRetSt",
		party="CustCode",
		lines_sql="""
			SELECT SalRetNo, RowNumber, ItemCode, Quantity, UnitMeas, Packing, Price, DiscPerc,
				DiscAmnt, ccy
			FROM saredeta WHERE SalRetNo IN ({placeholders})
			ORDER BY SalRetNo, RowNumber
		""",
	),
	STOCK_MUTATION: SourceSpec(
		header_sql="""
			SELECT h.MutNo, h.MutDate, h.MutStatus, h.`Transaction` AS Trans, h.Alasan, h.MutNote,
				h.BranchCode, h.BranchCodeDest, h.CurrCode, h.CreaUser, h.CreaDate, h.LasUpdDt
			FROM stockmut h
		""",
		date_col="h.MutDate",
		key="MutNo",
		status="MutStatus",
		party=None,
		lines_sql="""
			SELECT MutNo, RowNumber, ItemCode, Quantity, UnitMeas, Packing, Price, ccy
			FROM stockmutdt WHERE MutNo IN ({placeholders})
			ORDER BY MutNo, RowNumber
		""",
	),
	STOCK_SET: SourceSpec(
		header_sql="""
			SELECT h.MutNo, h.MutDate, h.MutStatus, h.Alasan, h.MutNote, h.BranchCode, h.CurrCode,
				h.CreaUser, h.CreaDate, h.LasUpdDt
			FROM stockmutset h
		""",
		date_col="h.MutDate",
		key="MutNo",
		status="MutStatus",
		party=None,
		lines_sql="""
			SELECT MutNo, RowNumber, `Transaction` AS Trans, ItemCode, Quantity, UnitMeas, Packing,
				Price, ccy
			FROM stockmutsetdt WHERE MutNo IN ({placeholders})
			ORDER BY MutNo, RowNumber
		""",
	),
	AR_RECEIPT: SourceSpec(
		header_sql="""
			SELECT h.RecNotNo, h.RecNotDt, h.CustCode, h.PaymNote, h.RNStatus, h.PayType,
				h.CreaUser, h.CreaDate, h.LasUpdDt
			FROM arrecnot h
		""",
		date_col="h.RecNotDt",
		key="RecNotNo",
		status="RNStatus",
		party="CustCode",
		lines_sql="""
			SELECT RecNotNo, SeqNo, InvoDNNo, CurrInDN, InDNAmon, CurrPaid, AmonPaid, MethodBy,
				DocNo, DocDueDt, Bank
			FROM arpaymen WHERE RecNotNo IN ({placeholders})
			ORDER BY RecNotNo, SeqNo
		""",
	),
	AP_PAYMENT: SourceSpec(
		header_sql="""
			SELECT h.PayNotNo, h.PayNotDt, h.SuppCode, h.PaymNote, h.RNStatus, h.PayType,
				h.CreaUser, h.CreaDate, h.LasUpdDt
			FROM appaynot h
		""",
		date_col="h.PayNotDt",
		key="PayNotNo",
		status="RNStatus",
		party="SuppCode",
		lines_sql="""
			SELECT PayNotNo, SeqNo, InvoDNNo, CurrInDN, InDNAmon, CurrPaid, AmonPaid, MethodBy,
				DocNo, DocDueDt, Bank
			FROM appaymen WHERE PayNotNo IN ({placeholders})
			ORDER BY PayNotNo, SeqNo
		""",
	),
}


def fetch(conn, kind, from_date, to_date, include_updated_before=True):
	"""Legacy documents of one kind dated in [from_date, to_date].

	The range is half-open on the day after to_date, so a DATETIME column
	with a time part on the last day is not lost (DATE columns behave the same).

	With include_updated_before, also returns older documents whose LasUpdDt
	falls on/after from_date -- the runner keeps those only if they were
	already imported, to catch a Reverse/edit/cancel of an earlier day.
	"""
	spec = SPECS[kind]
	from_date, to_date = getdate(from_date), getdate(to_date)
	headers = fetch_all(
		conn,
		spec.header_sql + f" WHERE {spec.date_col} >= %s AND {spec.date_col} < %s",
		(from_date, to_date + timedelta(days=1)),
	)
	if include_updated_before:
		headers += fetch_all(
			conn,
			spec.header_sql + f" WHERE {spec.date_col} < %s AND h.LasUpdDt >= %s",
			(from_date, from_date),
		)
	return _to_legacy_docs(conn, kind, spec, headers)


def fetch_one(conn, kind, legacy_no):
	spec = SPECS[kind]
	headers = fetch_all(conn, spec.header_sql + f" WHERE h.{spec.key} = %s", (legacy_no,))
	docs = _to_legacy_docs(conn, kind, spec, headers)
	return docs[0] if docs else None


def _to_legacy_docs(conn, kind, spec, headers):
	lines = _fetch_lines(conn, spec.lines_sql, [h[spec.key] for h in headers], spec.key)
	date_col = spec.date_col.split(".")[-1]
	return [
		{
			"kind": kind,
			"legacy_no": h[spec.key],
			"date": getdate(h[date_col]),
			"party": h[spec.party] if spec.party else None,
			"status": h[spec.status],
			"updated_at": h["LasUpdDt"],
			"created_by": h["CreaUser"],
			"amount": h[spec.amount] if spec.amount else None,
			"header": h,
			"lines": lines.get(h[spec.key], []),
		}
		for h in headers
	]


def _fetch_lines(conn, sql, numbers, key):
	grouped = {}
	if not sql:
		return grouped
	numbers = list(dict.fromkeys(numbers))
	for i in range(0, len(numbers), IN_CHUNK):
		chunk = numbers[i : i + IN_CHUNK]
		rows = fetch_all(conn, sql.format(placeholders=", ".join(["%s"] * len(chunk))), chunk)
		for row in rows:
			grouped.setdefault(row[key], []).append(row)
	return grouped


def fetch_payment_methods(conn):
	"""methodtabldt: {(MetDesc, currency): {"accid": ..., "retur": bool}} -- one small table."""
	methods = {}
	for row in fetch_all(conn, "SELECT MetDesc, Ccyid, Accid, Retur FROM methodtabldt"):
		key = ((row["MetDesc"] or "").strip(), (row["Ccyid"] or "").strip())
		methods[key] = {"accid": (row["Accid"] or "").strip(), "retur": bool(row["Retur"])}
	return methods


def fetch_legacy_costs(conn, item_codes, up_to):
	"""{ItemCode: average cost per stock unit} as the old system had it on `up_to`.

	inventory is the old system's item ledger; invBalPrice on each movement is
	the running company-wide average cost (HPP) per smallest unit, which is
	ERP's stock UOM. One indexed lookup per item -- only called for the few
	hundred items a batch's returns touch.
	"""
	costs = {}
	for code in sorted(set(item_codes)):
		rows = fetch_all(
			conn,
			"SELECT invBalPrice FROM inventory WHERE ItemCode = %s AND invMoveDate < %s "
			"ORDER BY invMoveDate DESC, SeqId DESC LIMIT 1",
			[code, add_days(up_to, 1)],
		)
		if rows and flt(rows[0]["invBalPrice"]) > 0:
			costs[code] = flt(rows[0]["invBalPrice"])
	return costs
