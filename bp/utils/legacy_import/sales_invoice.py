"""Legacy delivery order (deliorde + dodetail) -> Sales Invoice.

In the old system the delivery order IS the sales invoice: Confirm moves the
stock, creates the AR invoice ("I" + DONumber) and posts GL. So it maps to a
Sales Invoice with update_stock=1 (the client decided on no separate
Delivery Note step).

Discounts (Form_FmDeliOrdeDt.txt):
	DiscAmnt  = DiscPerc  * Qty * Price / 100
	DiscAmnt2 = DiscPerc2 * (Qty * Price - DiscAmnt) / 100   (compounds)
	Discamnt3 = manual amount per line
	line net  = Qty * Price - DiscAmnt - DiscAmnt2 - Discamnt3
	DO net    = sum(line net) - ndisc1                        (header amount)
DiscPerc and DiscPerc2 are what the user typed; they go to Discount 1 % and
Discount 2 %, which compound the same way (bp.utils.cascading_discount,
recomputed by the Sales Invoice before_validate hook). DiscAmnt and DiscAmnt2
are only those percentages in money, so they are not carried over: Discount 1
Amount and Discount 2 Amount are separate steps of their own and would take
the discount a second time. The manual per-line amount and the header discount
have no line-level equivalent, so they go to the invoice's header
Additional Discount.
"""

from datetime import time

import frappe
from frappe.utils import add_days, flt, get_datetime, getdate

from bp.utils.legacy_import import LegacyImportError


def legacy_line_net(line):
	gross = flt(line["Quantity"]) * flt(line["Price"])
	return gross - flt(line["DiscAmnt"]) - flt(line["DiscAmnt2"]) - flt(line["Discamnt3"])


def legacy_sales_total(header, lines):
	return sum(legacy_line_net(line) for line in lines) - flt(header.get("ndisc1"))


def expected_amount(legacy_doc):
	"""The total ERP must reproduce: the old system's AR invoice, else the DO's own lines."""
	if legacy_doc["amount"] is not None:
		return flt(legacy_doc["amount"])
	return legacy_sales_total(legacy_doc["header"], legacy_doc["lines"])


def posting_time_from(created_at, posting_date):
	"""Keep the old system's entry time when it was entered on the posting date itself,
	otherwise post at the end of that day (it was keyed in later)."""
	if created_at and getdate(created_at) == getdate(posting_date):
		return get_datetime(created_at).time()
	return time(23, 59, 59)


def build_sales_invoice(legacy_doc, ctx):
	h = legacy_doc["header"]
	problems = []

	if not ctx.has_customer(h["CustCode"]):
		problems.append(f"customer {h['CustCode']} not found or disabled")
	warehouse = ctx.warehouse(h["BranchCode"])
	if not warehouse:
		problems.append(f"old system branch {h['BranchCode']} is not mapped to a warehouse in BP Settings")
	sales_person = ctx.sales_person(h["SaleCode"])
	if not sales_person:
		problems.append(f"no enabled Sales Person with code {h['SaleCode']}")
	ctx.check_currency(h["CurrCode"], problems)
	lines = ctx.check_lines(legacy_doc["lines"], problems)
	for line in lines:
		if line.get("BranchCode") and not ctx.warehouse(line["BranchCode"]):
			problems.append(f"row {line['RowNumber']}: branch {line['BranchCode']} is not mapped")

	if problems:
		raise LegacyImportError("; ".join(problems))

	posting_date = getdate(h["DODatesx"])
	is_cash = int(h["CashFlag"] or 0) == -1
	credit_days = 0 if is_cash else int(h["CredTerm"] or 0)

	si = frappe.new_doc("Sales Invoice")
	si.update(
		{
			"company": ctx.company,
			"customer": h["CustCode"].strip(),
			"posting_date": posting_date,
			"posting_time": posting_time_from(h["CreaDate"], posting_date),
			"set_posting_time": 1,
			"due_date": add_days(posting_date, credit_days),
			# The old system's own credit term wins over the party's ERP Payment
			# Terms Template (which would reject a longer due date): one due date.
			"ignore_default_payment_terms_template": 1,
			"set_warehouse": warehouse,
			"update_stock": 1,
			"ignore_pricing_rule": 1,
			# Keep the receivable identical to the old system's invoice amount.
			"disable_rounded_total": 1,
			"bp_sales_person": sales_person,
			"po_no": (h["CustPONo"] or "").strip() or None,
			"custom_order_by": (h["OrderByx"] or "").strip() or None,
			"remarks": (h["DONotesx"] or "").strip() or None,
			"custom_legacy_type": legacy_doc["kind"],
			"custom_legacy_no": legacy_doc["legacy_no"],
			"custom_legacy_created_by": legacy_doc["created_by"],
			"custom_legacy_updated_at": legacy_doc["updated_at"],
		}
	)

	extra_discount = flt(h.get("ndisc1"))
	for line in lines:
		qty = flt(line["Quantity"])
		item_code = line["ItemCode"].strip()
		row = {
			"item_code": item_code,
			"qty": qty,
			"uom": ctx.uom(line["UnitMeas"]),
			"conversion_factor": flt(line["Packing"]) or 1,
			"warehouse": ctx.warehouse(line.get("BranchCode")) or warehouse,
			"price_list_rate": flt(line["Price"]),
			"custom_discount1_percentage": flt(line["DiscPerc"]),
			"custom_discount2_percentage": flt(line["DiscPerc2"]),
		}
		if (line.get("DescTamb") or "").strip():
			row["description"] = f"{ctx.item_name(item_code)}\n{line['DescTamb'].strip()}"
		si.append("items", row)
		extra_discount += flt(line["Discamnt3"])

	if extra_discount:
		si.apply_discount_on = "Net Total"
		si.discount_amount = extra_discount

	return si
