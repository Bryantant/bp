"""Legacy stock mutation (stockmut + stockmutdt) -> Stock Entry.

Form_FmStockMut / Form_FmStockMutRel write one table, told apart by
`Transaction`:
	1 "Masuk"    goods in at BranchCode         -> Material Receipt
	2 "Keluar"   goods out of BranchCode        -> Material Issue
	3 Relokasi   BranchCode -> BranchCodeDest   -> Material Transfer

The old system posts no GL for any of them. `Price` only matters for goods in:
it is required there and feeds the month-end moving-average cost run, while
for goods out it is locked and for relocations it is informational. So only a
Material Receipt gets an explicit rate (Price is per UnitMeas, the ERP rate
is per stock unit, hence / Packing); issues and transfers are valued by ERP
at the running average, just as the old HPP run did. A goods-in line typed
without a price is left to ERP when the item has a valuation in that
warehouse, and otherwise gets the same fallback as a return
(ImportContext.missing_valuation_rate).

ERP does post Material Receipt/Issue to the company's Stock Adjustment
account -- that is the difference ERP adds, not a mapping choice.
"""

import frappe
from frappe.utils import flt, getdate

from bp.utils.legacy_import import LegacyImportError
from bp.utils.legacy_import.sales_invoice import posting_time_from

PURPOSES = {1: "Material Receipt", 2: "Material Issue", 3: "Material Transfer"}


def expected_amount(legacy_doc):
	# Stock documents carry no money figure worth comparing: goods out and
	# transfers are valued by ERP. check_quantity() compares quantities instead.
	return None


def legacy_stock_qty(lines):
	return sum(flt(line["Quantity"]) * (flt(line["Packing"]) or 1) for line in lines if flt(line["Quantity"]) > 0)


def check_quantity(doc, legacy_doc, tolerance=None):
	"""Total stock quantity moved must match the old system's Quantity x Packing."""
	expected = legacy_stock_qty(legacy_doc["lines"])
	moved = sum(flt(row.transfer_qty) for row in doc.items)
	if abs(moved - expected) > 0.0001:
		raise LegacyImportError(f"ERP moves {moved:,.4f} stock units, old system {expected:,.4f}")


def check_stock_entry_type(ctx, purpose, problems):
	if purpose and not ctx.stock_entry_type(purpose):
		problems.append(f"no Stock Entry Type with purpose {purpose} on this site")


def new_stock_entry(legacy_doc, ctx, purpose):
	h = legacy_doc["header"]
	posting_date = getdate(h["MutDate"])
	se = frappe.new_doc("Stock Entry")
	se.update(
		{
			"company": ctx.company,
			"stock_entry_type": ctx.stock_entry_type(purpose),
			"purpose": purpose,
			"posting_date": posting_date,
			"posting_time": posting_time_from(h["CreaDate"], posting_date),
			"set_posting_time": 1,
			"remarks": " -- ".join(p for p in ((h["Alasan"] or "").strip(), (h["MutNote"] or "").strip()) if p)
			or None,
			"custom_legacy_type": legacy_doc["kind"],
			"custom_legacy_no": legacy_doc["legacy_no"],
			"custom_legacy_created_by": legacy_doc["created_by"],
			"custom_legacy_updated_at": legacy_doc["updated_at"],
		}
	)
	return se


def item_row(line, ctx, source=None, target=None, rate=None):
	row = {
		"item_code": line["ItemCode"].strip(),
		"qty": flt(line["Quantity"]),
		"uom": ctx.uom(line["UnitMeas"]),
		"conversion_factor": flt(line["Packing"]) or 1,
		"s_warehouse": source,
		"t_warehouse": target,
	}
	if rate is not None:
		row.update({"basic_rate": rate, "set_basic_rate_manually": 1})
	return row


def build_stock_mutation(legacy_doc, ctx):
	h = legacy_doc["header"]
	problems = []

	transaction = int(h["Trans"] or 0)
	purpose = PURPOSES.get(transaction)
	if not purpose:
		problems.append(f"unknown Transaction {h['Trans']}")

	source = target = None
	warehouse = ctx.warehouse(h["BranchCode"])
	if not warehouse:
		problems.append(f"old system branch {h['BranchCode']} is not mapped to a warehouse in BP Settings")
	if transaction == 1:
		target = warehouse
	elif transaction == 2:
		source = warehouse
	elif transaction == 3:
		source = warehouse
		target = ctx.warehouse(h["BranchCodeDest"])
		if not target:
			problems.append(
				f"destination branch {h['BranchCodeDest'] or '(empty)'} is not mapped to a warehouse in BP Settings"
			)
		elif target == source:
			problems.append(f"transfer from {h['BranchCode']} to itself")

	check_stock_entry_type(ctx, purpose, problems)
	lines = ctx.check_lines(legacy_doc["lines"], problems)

	rates = []
	for line in lines:
		rate = None
		if transaction == 1 and flt(line["Price"]) > 0:
			rate = flt(line["Price"]) / (flt(line["Packing"]) or 1)
		elif transaction == 1 and target:
			code = line["ItemCode"].strip()
			rate = ctx.missing_valuation_rate(code, target, getdate(h["MutDate"]))
			if rate == 0 and not ctx.pending:
				problems.append(f"item {code} has no price and no stock valuation in ERP yet")
		rates.append(rate or None)

	if problems:
		raise LegacyImportError("; ".join(problems))

	se = new_stock_entry(legacy_doc, ctx, purpose)
	for line, rate in zip(lines, rates):
		se.append("items", item_row(line, ctx, source=source, target=target, rate=rate))
	return se
