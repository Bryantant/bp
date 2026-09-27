"""Shared builder for legacy AR receipts and AP payments -> Journal Entry.

A legacy receipt (arrecnot/arpaymen) or payment (appaynot/appaymen) is a list
of lines, each pairing ONE invoice with ONE method:

	InvoDNNo  the invoice being settled      InDNAmon  what it takes off it
	MethodBy  methodtabldt.MetDesc          AmonPaid  the money side
	DocNo     cheque/giro no., or the return number for "Retur Penjualan"

The old GL posted each line as method account against the AR/AP control
account. A Journal Entry takes the same shape -- rows of account, party,
reference and amount -- so one JE per receipt/payment reproduces it for every
combination found in the data: one method, several methods, or no money at
all (a receipt that only offsets returns). A Payment Entry could not: it has
one cash account and must move money.

Sides (AR shown; AP swaps debit and credit):
	credit  Receivable, party = customer, reference = the invoice   (InDNAmon)
	debit   the method's account                                    (AmonPaid)
	  or, for a "Retur Penjualan" line whose DocNo is a return imported
	  into ERP:
	debit   Receivable, party = customer, reference = that return  (AmonPaid)
	  -- the same two-row shape ERPNext's own reconcile_dr_cr_note uses to set
	  a credit note against an invoice, so the return's credit is applied
	  instead of being counted a second time. A return line that points at a
	  return from before the cutoff (never imported), at nothing
	  recognisable, at another customer's return, or at a return without
	  enough credit left (DocNo is free text in the old system and is
	  sometimes wrong) falls back to the method's own account, 42200 Retur
	  Penjualan, exactly as the old GL booked it.

Amounts are rounded to ERP's currency precision per line: the old system
stores 4 decimals (13879999.9976), and rounding only the aggregated method
row would leave the JE a few cents out of balance.
"""

from dataclasses import dataclass

import frappe
from frappe.utils import flt, getdate

from bp.utils.legacy_import import LegacyImportError
from bp.utils.legacy_import.context import PENDING, is_nd_invoice_no


@dataclass(frozen=True)
class Side:
	invoice_doctype: str
	invoice_kind: str  # kind of the documents imported into invoice_doctype
	party_type: str
	party_field: str  # header column
	date_field: str  # header column
	invoice_column: str  # "credit_in_account_currency" for AR, "debit_..." for AP
	counter_column: str
	offsets_returns: bool  # AR only: "Retur Penjualan" lines


def expected_amount(legacy_doc):
	return sum(flt(line["InDNAmon"]) for line in legacy_doc["lines"])


def check_total(doc, expected, tolerance):
	difference = flt(doc.total_debit) - flt(expected)
	if abs(difference) > flt(tolerance):
		raise LegacyImportError(
			f"ERP total {flt(doc.total_debit):,.2f} differs from old system total {flt(expected):,.2f} "
			f"by {difference:,.2f} (tolerance {flt(tolerance):,.2f})"
		)


def usable_return(ctx, credit_note, party, amount, used):
	"""May this receipt line apply `amount` of an imported return's credit?"""
	if credit_note == PENDING:  # Preview: created later in this batch, nothing to check yet
		return True
	customer, credit = ctx.return_credit(credit_note)
	return customer == party and used.get(credit_note, 0) + amount <= credit + 0.005


def plan_lines(legacy_doc, ctx, side):
	"""Resolve every legacy line to (invoice, counterpart); collect all problems.

	Returns (party, lines) where each line is
	{"seq", "amount", "invoice", "counter": ("account", name) | ("return", name)}.
	Raises LegacyImportError listing everything that is wrong at once.
	"""
	h = legacy_doc["header"]
	party = (h[side.party_field] or "").strip()
	problems = []

	has_party = ctx.has_customer if side.party_type == "Customer" else ctx.has_supplier
	if not has_party(party):
		problems.append(f"{side.party_type.lower()} {party} not found or disabled")

	precision = frappe.get_precision("Journal Entry Account", side.invoice_column) or 2
	planned = []
	used = {}  # return -> credit this receipt already applies from it
	for line in legacy_doc["lines"]:
		seq = line["SeqNo"]
		amount = flt(line["InDNAmon"], precision)
		if not amount:
			continue

		currency_in = (line["CurrInDN"] or "").strip() or ctx.company_currency
		currency_paid = (line["CurrPaid"] or "").strip() or ctx.company_currency
		if currency_in != ctx.company_currency or currency_paid != ctx.company_currency:
			problems.append(
				f"line {seq}: currency {currency_in}/{currency_paid} is not supported (only {ctx.company_currency})"
			)
			continue
		if abs(flt(line["AmonPaid"]) - flt(line["InDNAmon"])) > 0.001:
			problems.append(f"line {seq}: paid {line['AmonPaid']} differs from applied {amount}")
			continue

		invoice_no = (line["InvoDNNo"] or "").strip()
		invoice = ctx.invoice_for(side.invoice_doctype, invoice_no, side.invoice_kind)
		if not invoice:
			hint = (
				" (ND System invoice -- bring it in with Import ND Invoice first)"
				if side.invoice_doctype == "Sales Invoice" and is_nd_invoice_no(invoice_no)
				else ""
			)
			problems.append(f"line {seq}: invoice {invoice_no} is not in ERP{hint}")

		method = (line["MethodBy"] or "").strip()
		counter = None
		if side.offsets_returns and ctx.is_return_method(method, currency_paid):
			credit_note = ctx.sales_return_for(line["DocNo"])
			if credit_note and usable_return(ctx, credit_note, party, amount, used):
				counter = ("return", credit_note)
				used[credit_note] = used.get(credit_note, 0) + amount
		if not counter:
			account = ctx.method_account(method, currency_paid)
			if not account:
				problems.append(
					f"line {seq}: payment method '{method}' has no ERP account -- add it to "
					"BP Settings > Payment Method Map, or create the account with the legacy number"
				)
			elif frappe.get_cached_value("Account", account, "account_type") in ("Receivable", "Payable"):
				problems.append(
					f"line {seq}: payment method '{method}' maps to {account}, a receivable/payable account; "
					"map it explicitly in BP Settings > Payment Method Map"
				)
			else:
				counter = ("account", account)

		planned.append({"seq": seq, "amount": amount, "invoice": invoice, "counter": counter})

	if not planned and not problems:
		problems.append("no lines with an amount")
	if problems:
		raise LegacyImportError("; ".join(problems))
	return party, planned


def build_payment(legacy_doc, ctx, side):
	party, planned = plan_lines(legacy_doc, ctx, side)
	h = legacy_doc["header"]
	posting_date = getdate(h[side.date_field])
	default_party_account = frappe.get_cached_value(
		"Company",
		ctx.company,
		"default_receivable_account" if side.party_type == "Customer" else "default_payable_account",
	)

	def party_account(doctype, name):
		if name == PENDING:  # Preview only: the target is created later in this batch
			return default_party_account
		return ctx.party_account(doctype, name) or default_party_account

	je = frappe.new_doc("Journal Entry")
	je.update(
		{
			"company": ctx.company,
			"voucher_type": "Journal Entry",
			"posting_date": posting_date,
			"cheque_no": legacy_doc["legacy_no"],
			"cheque_date": posting_date,
			"user_remark": (h["PaymNote"] or "").strip() or None,
			"custom_legacy_type": legacy_doc["kind"],
			"custom_legacy_no": legacy_doc["legacy_no"],
			"custom_legacy_created_by": legacy_doc["created_by"],
			"custom_legacy_updated_at": legacy_doc["updated_at"],
		}
	)

	by_account = {}
	for line in planned:
		je.append(
			"accounts",
			{
				"account": party_account(side.invoice_doctype, line["invoice"]),
				"party_type": side.party_type,
				"party": party,
				side.invoice_column: line["amount"],
				"reference_type": side.invoice_doctype,
				"reference_name": line["invoice"],
			},
		)
		kind, target = line["counter"]
		if kind == "return":
			je.append(
				"accounts",
				{
					"account": party_account("Sales Invoice", target),
					"party_type": side.party_type,
					"party": party,
					side.counter_column: line["amount"],
					"reference_type": "Sales Invoice",
					"reference_name": target,
				},
			)
		else:
			by_account[target] = by_account.get(target, 0) + line["amount"]

	# One row per method account: the legacy lines paid by the same method in
	# one receipt are one deposit, which is what a bank statement shows.
	for account, amount in by_account.items():
		je.append(
			"accounts",
			{"account": account, side.counter_column: amount, "cost_center": ctx.cost_center},
		)
	return je
