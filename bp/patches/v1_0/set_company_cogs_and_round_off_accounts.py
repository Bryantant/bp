"""Give Company BP a real COGS account and its own round-off account.

Found on bp.localhost (2026-09-22):
- Default Cost of Goods Sold pointed at 51000 Pembelian IDR. The legacy GL
  expensed purchases there (periodic method), but with perpetual inventory
  every Sales Invoice now posts its cost of sales to this account, so the
  P&L would show COGS under "Pembelian". 59000 HPP Persediaan is a group
  account and cannot be used as a default.
- Round Off Account pointed at 41100 Penjualan IDR, so rounding differences
  were booked as sales revenue. The legacy COA has no rounding account.

Bry's decision (2026-09-22): create 59010 HPP Barang Dagang under 59000 and
61301 Selisih Pembulatan under 60000 Biaya, and use them as the defaults.

Idempotent: accounts are only created when missing, and the Company fields
are only changed while they still hold the old values, so a later manual
change on the site is not overwritten.
"""

import frappe

COMPANY = "PT. Bestindo Persada"

ACCOUNTS = [
	# (account_number, account_name, parent account_number, account_type, company field, old value)
	("59010", "HPP Barang Dagang", "59000", "Cost of Goods Sold", "default_expense_account", "51000"),
	("61301", "Selisih Pembulatan", "60000", "Round Off", "round_off_account", "41100"),
]


def execute():
	if not frappe.db.exists("Company", COMPANY):
		return

	for number, name, parent_number, account_type, field, old_number in ACCOUNTS:
		account = _ensure_account(number, name, parent_number, account_type)
		if not account:
			continue

		current = frappe.db.get_value("Company", COMPANY, field)
		current_number = frappe.db.get_value("Account", current, "account_number") if current else None
		if not current or current_number == old_number:
			frappe.db.set_value("Company", COMPANY, field, account)

	frappe.clear_cache()


def _ensure_account(number, name, parent_number, account_type):
	existing = frappe.db.get_value("Account", {"company": COMPANY, "account_number": number})
	if existing:
		return existing

	parent = frappe.db.get_value(
		"Account", {"company": COMPANY, "account_number": parent_number, "is_group": 1}
	)
	if not parent:
		return None

	doc = frappe.get_doc(
		{
			"doctype": "Account",
			"company": COMPANY,
			"account_name": name,
			"account_number": number,
			"parent_account": parent,
			"account_type": account_type,
			"is_group": 0,
			"account_currency": frappe.db.get_value("Company", COMPANY, "default_currency"),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name
