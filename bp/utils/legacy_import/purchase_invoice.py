"""Legacy receiving (pcrecdor + pcrddeta) -> Purchase Invoice.

In the old system Confirm on a receiving moves the stock and creates the AP
invoice ("I" + RecDOrNo). The client combines receipt and invoice in ERP, so
it maps to a Purchase Invoice with update_stock=1. CashFlag -1 is a cash
purchase, which drives the Cash/Credit Invoice Type (and so the PC/PF naming
series, see bp.overrides.purchase_invoice).

Receiving lines carry a single discount tier:
	line net = Quantity * Price - DiscAmt   (DiscAmt = DiscPerc * Qty * Price / 100)
"""

import frappe
from frappe.utils import add_days, flt, getdate

from bp.utils.legacy_import import LegacyImportError


def legacy_line_net(line):
	gross = flt(line["Quantity"]) * flt(line["Price"])
	discount = flt(line["DiscAmt"]) or gross * flt(line["DiscPerc"]) / 100
	return gross - discount


def legacy_purchase_total(lines):
	return sum(legacy_line_net(line) for line in lines)


def expected_amount(legacy_doc):
	if legacy_doc["amount"] is not None:
		return flt(legacy_doc["amount"])
	return legacy_purchase_total(legacy_doc["lines"])


def build_purchase_invoice(legacy_doc, ctx):
	h = legacy_doc["header"]
	problems = []

	if not ctx.has_supplier(h["SuppCode"]):
		problems.append(f"supplier {h['SuppCode']} not found or disabled")
	warehouse = ctx.warehouse(h["BranchCode"])
	if not warehouse:
		problems.append(f"old system branch {h['BranchCode']} is not mapped to a warehouse in BP Settings")
	lines = ctx.check_lines(legacy_doc["lines"], problems)
	currency = h.get("CurrCode") or next((line["CurrCode"] for line in lines if line.get("CurrCode")), None)
	ctx.check_currency(currency, problems)

	if problems:
		raise LegacyImportError("; ".join(problems))

	posting_date = getdate(h["RecDOrDt"])
	is_cash = int(h["CashFlag"] or 0) == -1
	credit_days = 0 if is_cash else int(h["CredTerm"] or 0)

	pi = frappe.new_doc("Purchase Invoice")
	pi.update(
		{
			"company": ctx.company,
			"supplier": h["SuppCode"].strip(),
			"posting_date": posting_date,
			# Receivings post at the start of the day so goods received that day
			# are in stock before the day's sales invoices (posted at their entry
			# time) take them out.
			"posting_time": "00:00:00",
			"set_posting_time": 1,
			"due_date": add_days(posting_date, credit_days),
			# The old system's own credit term wins over the party's ERP Payment
			# Terms Template (which would reject a longer due date): one due date.
			"ignore_default_payment_terms_template": 1,
			"bill_no": (h["SuppDONo"] or "").strip() or None,
			"bill_date": posting_date,
			"custom_invoice_type": "Cash" if is_cash else "Credit",
			"set_warehouse": warehouse,
			"update_stock": 1,
			"ignore_pricing_rule": 1,
			"disable_rounded_total": 1,
			"remarks": (h["RecDOrNt"] or "").strip() or None,
			"custom_legacy_no": legacy_doc["legacy_no"],
			"custom_legacy_created_by": legacy_doc["created_by"],
			"custom_legacy_updated_at": legacy_doc["updated_at"],
		}
	)

	for line in lines:
		qty = flt(line["Quantity"])
		pi.append(
			"items",
			{
				"item_code": line["ItemCode"].strip(),
				"qty": qty,
				"uom": ctx.uom(line["UnitMeas"]),
				"conversion_factor": flt(line["Packing"]) or 1,
				"warehouse": warehouse,
				"price_list_rate": flt(line["Price"]),
				"discount_percentage": flt(line["DiscPerc"]),
				# Explicit rate: ERP keeps a rate that is already set instead of
				# re-deriving it from price_list_rate, so the old system's net
				# (including an amount-only discount) is what gets posted.
				"rate": legacy_line_net(line) / qty,
			},
		)

	return pi
