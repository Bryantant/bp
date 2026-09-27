"""Legacy sales return (saleretu + saredeta) -> Sales Invoice return.

In the old system a return is a pure stock document: Confirm only adds the
goods back to ItemBalance at the header BranchCode. It is not linked to the
delivery order it came from (DONumber is never filled; the DO-copy code in
Form_FmSaleRetu is commented out), prices are typed in, and there is no
credit note or GL posting -- the receivable is reduced later, when a receipt
line with method "Retur Penjualan" offsets it against an invoice.

In ERP it becomes a standalone credit note (is_return, no return_against,
because the source has no link) that updates stock. That reduces the
customer's receivable immediately; the offsetting receipt line is then
imported as an allocation of this credit note to the invoice rather than as
money (see ar_receipt.py), so nothing is counted twice.

The warehouse follows the operator's BranchCode, not the Rusak flag: Rusak
drives no posting logic in the old system, damaged returns land in GS only
because staff pick it.

Line net = Quantity * Price - DiscAmnt (one discount tier).

Valuation: ERP values a standalone return at the item's rate in the return
warehouse and rejects it when that warehouse never held the item (GS and BR
only ever receive returns). Those lines get the item's company-wide ERP
valuation instead -- see ImportContext.missing_valuation_rate.
"""

import frappe
from frappe.utils import flt, getdate

from bp.utils.legacy_import import LegacyImportError
from bp.utils.legacy_import.sales_invoice import posting_time_from


def legacy_line_net(line):
	return flt(line["Quantity"]) * flt(line["Price"]) - flt(line["DiscAmnt"])


def expected_amount(legacy_doc):
	"""Negative, like the ERP return's grand_total."""
	return -sum(legacy_line_net(line) for line in legacy_doc["lines"] if flt(line["Quantity"]) > 0)


def build_sales_return(legacy_doc, ctx):
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

	posting_date = getdate(h["SalRetDt"])
	incoming_rates = {}
	if warehouse:
		for line in lines:
			code = line["ItemCode"].strip()
			rate = ctx.missing_valuation_rate(code, warehouse, posting_date)
			if rate == 0 and not ctx.pending:
				problems.append(f"item {code} has no stock valuation in ERP yet, so the return cannot be valued")
			incoming_rates[code] = rate

	if problems:
		raise LegacyImportError("; ".join(problems))

	si = frappe.new_doc("Sales Invoice")
	si.update(
		{
			"company": ctx.company,
			"customer": h["CustCode"].strip(),
			"is_return": 1,
			"posting_date": posting_date,
			"posting_time": posting_time_from(h["CreaDate"], posting_date),
			"set_posting_time": 1,
			"due_date": posting_date,
			"ignore_default_payment_terms_template": 1,
			"set_warehouse": warehouse,
			"update_stock": 1,
			"ignore_pricing_rule": 1,
			"disable_rounded_total": 1,
			"bp_sales_person": sales_person,
			"remarks": (h["SalRetNt"] or "").strip() or None,
			"custom_legacy_type": legacy_doc["kind"],
			"custom_legacy_no": legacy_doc["legacy_no"],
			"custom_legacy_created_by": legacy_doc["created_by"],
			"custom_legacy_updated_at": legacy_doc["updated_at"],
		}
	)

	for line in lines:
		qty = flt(line["Quantity"])
		si.append(
			"items",
			{
				"item_code": line["ItemCode"].strip(),
				"qty": -qty,
				"uom": ctx.uom(line["UnitMeas"]),
				"conversion_factor": flt(line["Packing"]) or 1,
				"warehouse": warehouse,
				"price_list_rate": flt(line["Price"]),
				# One discount tier on a return; the cascading-discount hook
				# (bp.overrides.sales_invoice) turns it into the rate.
				"custom_discount1_percentage": flt(line["DiscPerc"]),
				"custom_discount1_amount": flt(line["DiscAmnt"]) / qty,
			},
		)
		rate = incoming_rates.get(line["ItemCode"].strip())
		if rate:
			# Kept by ERP for a standalone return (selling_controller.set_incoming_rate).
			si.items[-1].incoming_rate = rate

	return si
