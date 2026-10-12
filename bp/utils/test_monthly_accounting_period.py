from unittest.mock import patch

import frappe
from erpnext.accounts.doctype.accounting_period.accounting_period import (
	ClosedAccountingPeriod,
	validate_accounting_period_on_doc_save,
)
from frappe.tests import IntegrationTestCase

from bp.patches.v1_0 import set_company_fx_accounts_and_monthly_periods as patch_module

COMPANY = patch_module.COMPANY
ROLES = "erpnext.accounts.doctype.accounting_period.accounting_period.frappe.get_roles"


def _invoice_on(posting_date):
	return frappe._dict(doctype="Sales Invoice", company=COMPANY, posting_date=posting_date)


class TestMonthlyAccountingPeriod(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		patch_module.execute()
		cls.period = frappe.db.get_value(
			"Accounting Period", {"company": COMPANY, "start_date": "2026-01-01", "end_date": "2026-01-31"}
		)

	def test_company_accounts_are_set(self):
		self.assertTrue(frappe.db.get_value("Company", COMPANY, "exchange_gain_loss_account").startswith("81010"))
		for number, currency in (("11430", "USD"), ("11440", "MYR")):
			self.assertEqual(
				frappe.db.get_value("Account", {"company": COMPANY, "account_number": number}, "account_currency"),
				currency,
			)

	def test_disabled_period_does_not_lock(self):
		frappe.db.set_value("Accounting Period", self.period, "disabled", 1)
		with patch(ROLES, return_value=["Accounts User"]):
			validate_accounting_period_on_doc_save(_invoice_on("2026-01-15"))

	def test_closed_month_blocks_staff_but_not_accounts_manager(self):
		frappe.db.set_value("Accounting Period", self.period, "disabled", 0)
		try:
			with patch(ROLES, return_value=["Accounts User", "Sales User"]):
				with self.assertRaises(ClosedAccountingPeriod):
					validate_accounting_period_on_doc_save(_invoice_on("2026-01-15"))
			with patch(ROLES, return_value=["Accounts Manager"]):
				validate_accounting_period_on_doc_save(_invoice_on("2026-01-15"))
			with patch(ROLES, return_value=["Accounts User"]):
				validate_accounting_period_on_doc_save(_invoice_on("2026-02-01"))
		finally:
			frappe.db.set_value("Accounting Period", self.period, "disabled", 1)

	def test_accounts_user_cannot_edit_periods(self):
		perm = frappe.db.get_value(
			"Custom DocPerm",
			{"parent": "Accounting Period", "role": "Accounts User", "permlevel": 0},
			["read", "write", "create", "delete"],
			as_dict=True,
		)
		self.assertEqual((perm.read, perm.write, perm.create, perm.delete), (1, 0, 0, 0))
