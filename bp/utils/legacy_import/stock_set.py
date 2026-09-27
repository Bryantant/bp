"""Legacy set/assembly (stockmutset + stockmutsetdt) -> Stock Entry (Repack).

Form_FmStockMutSet assembles finished "sets" from components at one branch:
detail lines with Transaction 1 are the finished items going IN, lines with
Transaction 2 are the components going OUT, all at the header BranchCode. On
Confirm the old system prices the set as total component value / total set
quantity; no GL is posted.

A Repack Stock Entry is the same thing: components out, finished items in,
the same warehouse, and ERP spreads the components' value over the finished
items. Legacy prices are therefore not copied -- ERP derives them the same
way the old system did, from the components' running average cost.
"""

from bp.utils.legacy_import import LegacyImportError
from bp.utils.legacy_import.stock_mutation import check_stock_entry_type, item_row, new_stock_entry

FINISHED, COMPONENT = 1, 2


def expected_amount(legacy_doc):
	return None


def build_stock_set(legacy_doc, ctx):
	h = legacy_doc["header"]
	problems = []

	warehouse = ctx.warehouse(h["BranchCode"])
	if not warehouse:
		problems.append(f"old system branch {h['BranchCode']} is not mapped to a warehouse in BP Settings")

	check_stock_entry_type(ctx, "Repack", problems)
	lines = ctx.check_lines(legacy_doc["lines"], problems)
	finished = [line for line in lines if int(line["Trans"] or 0) == FINISHED]
	components = [line for line in lines if int(line["Trans"] or 0) == COMPONENT]
	if lines and not finished:
		problems.append("no finished (IN) line")
	if lines and not components:
		problems.append("no component (OUT) line")

	if problems:
		raise LegacyImportError("; ".join(problems))

	se = new_stock_entry(legacy_doc, ctx, "Repack")
	for line in components:
		se.append("items", item_row(line, ctx, source=warehouse))
	for line in finished:
		row = item_row(line, ctx, target=warehouse)
		row["is_finished_item"] = 1
		se.append("items", row)
	return se

