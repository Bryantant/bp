"""Finish Company BP's accounting setup: exchange gain/loss, foreign purchase deposits, monthly lock.

Task HT-5 (accounting interview, confirmed by Bry 2026-10-12):
- Exchange Gain/Loss = 81010 Selisih Kurs. The field was empty, so a Payment
  Entry settling a foreign-currency invoice had nowhere to post the difference.
- Purchase deposits per currency: 11410 IDR and 11420 SGD exist; 11430 USD and
  11440 MYR are created next to them under 11200.
- Books are locked per month and only Accounts Manager may still post into a
  locked month. Bry chose Accounting Period (not the single frozen date).
  v16 Accounting Period has `exempted_role`, so each month gets one period
  with every closing doctype marked closed and Accounts Manager exempted.
  The periods start **disabled**: closing a month = untick Disabled on that
  month's period. Only months of fiscal years that exist are created.
- Accounting Period itself becomes editable by Accounts Manager only;
  Accounts User keeps read access, so staff cannot reopen a month.

The advance received/paid defaults (24000 / 11410) are NOT set here: in v16
they only take effect with "Book Advance Payments in Separate Party Account"
on, and that also requires changing 24000 to type Receivable and 11410 to
Payable. That is an accounting design choice left to Bry.

Idempotent: accounts and periods are only created when missing, the Company
field is only filled while empty, permissions are (re)set on every run.
"""

import calendar
from datetime import date

import frappe
from frappe.permissions import add_permission, update_permission_property

COMPANY = "PT. Bestindo Persada"
PERIOD_YEARS = (2026,)
EXEMPTED_ROLE = "Accounts Manager"

DEPOSIT_ACCOUNTS = [
	# (account_number, account_name, currency); placed next to 11410/11420
	("11430", "Deposit Pembelian - USD", "USD"),
	("11440", "Deposit Pembelian - MYR", "MYR"),
]


def execute():
	if not frappe.db.exists("Company", COMPANY):
		return

	_set_exchange_gain_loss_account()
	for number, name, currency in DEPOSIT_ACCOUNTS:
		_ensure_deposit_account(number, name, currency)
	for year in PERIOD_YEARS:
		_ensure_monthly_periods(year)
	_restrict_accounting_period_edit()

	frappe.clear_cache()


def _set_exchange_gain_loss_account():
	if frappe.db.get_value("Company", COMPANY, "exchange_gain_loss_account"):
		return
	account = frappe.db.get_value("Account", {"company": COMPANY, "account_number": "81010", "is_group": 0})
	if account:
		frappe.db.set_value("Company", COMPANY, "exchange_gain_loss_account", account)


def _ensure_deposit_account(number, name, currency):
	if frappe.db.exists("Account", {"company": COMPANY, "account_number": number}):
		return
	sibling = frappe.db.get_value(
		"Account", {"company": COMPANY, "account_number": "11410"}, ["parent_account"], as_dict=True
	)
	if not sibling or not frappe.db.exists("Currency", currency):
		return
	if not frappe.db.get_value("Currency", currency, "enabled"):
		frappe.db.set_value("Currency", currency, "enabled", 1)

	frappe.get_doc(
		{
			"doctype": "Account",
			"company": COMPANY,
			"account_name": name,
			"account_number": number,
			"parent_account": sibling.parent_account,
			"root_type": "Asset",
			"is_group": 0,
			"account_currency": currency,
		}
	).insert(ignore_permissions=True)


def _ensure_monthly_periods(year):
	if not frappe.db.exists("Fiscal Year", {"year_start_date": ("<=", date(year, 1, 1))}):
		return
	abbr = frappe.db.get_value("Company", COMPANY, "abbr")
	closing_doctypes = frappe.get_hooks("period_closing_doctypes")

	for month in range(1, 13):
		period_name = f"{year}-{month:02d}"
		if frappe.db.exists("Accounting Period", f"{period_name} - {abbr}"):
			continue
		last_day = calendar.monthrange(year, month)[1]
		doc = frappe.get_doc(
			{
				"doctype": "Accounting Period",
				"period_name": period_name,
				"company": COMPANY,
				"start_date": date(year, month, 1),
				"end_date": date(year, month, last_day),
				"disabled": 1,
				"exempted_role": EXEMPTED_ROLE,
				"closed_documents": [{"document_type": dt, "closed": 1} for dt in closing_doctypes],
			}
		)
		doc.insert(ignore_permissions=True)


def _restrict_accounting_period_edit():
	doctype = "Accounting Period"
	if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": "Accounts User", "permlevel": 0}):
		add_permission(doctype, "Accounts User", 0)
	for right in ("write", "create", "delete"):
		update_permission_property(doctype, "Accounts User", 0, right, 0, validate=False)
	update_permission_property(doctype, "Accounts User", 0, "read", 1, validate=False)
	frappe.clear_cache(doctype=doctype)
