from datetime import date, datetime
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from bp.overrides.sales_invoice import enforced
from bp.utils.import_legacy_opening_invoices import SOURCES, _check_rows, _ensure_fiscal_years


def legacy_row(**kw):
	row = {
		"InvoicNo": "IF25030183",
		"InvDate": datetime(2025, 3, 17),
		"party": "A0088",
		"CredTerm": 30,
		"AmtInv": 10_000_000,
		"AmtPaid": 0,
		"InvStatu": 1,
	}
	row.update(kw)
	return row


class IntegrationTestOpeningInvoices(IntegrationTestCase):
	def setUp(self):
		self.source = SOURCES["Sales"]

	def _check(self, rows, party_exists=True, invoice_exists=False):
		with patch(
			"bp.utils.import_legacy_opening_invoices.frappe.db.exists",
			side_effect=lambda doctype, name=None: party_exists
			if doctype == "Customer"
			else invoice_exists,
		):
			return _check_rows(rows, self.source)

	def test_carries_the_remaining_balance_not_the_invoice_total(self):
		usable, _ = self._check([legacy_row(AmtInv=10_000_000, AmtPaid=4_000_000)])
		self.assertEqual(usable[0]["outstanding"], 6_000_000)

	def test_due_date_follows_the_legacy_credit_term(self):
		usable, _ = self._check([legacy_row(InvDate=datetime(2025, 3, 17), CredTerm=30)])
		self.assertEqual(usable[0]["date"], date(2025, 3, 17))
		self.assertEqual(usable[0]["due_date"], date(2025, 4, 16))

	def test_fully_settled_rows_are_left_out(self):
		usable, skipped = self._check([legacy_row(AmtInv=1_000_000, AmtPaid=1_000_000)])
		self.assertEqual(usable, [])
		self.assertEqual(len(skipped["zero_amount"]), 1)

	def test_missing_party_is_reported_not_created(self):
		usable, skipped = self._check([legacy_row()], party_exists=False)
		self.assertEqual(usable, [])
		self.assertIn("IF25030183 (A0088)", skipped["party_missing"])

	def test_balance_already_carried_over_is_skipped(self):
		"""The tool names each invoice after the legacy number, so that name
		existing means this balance is already in ERP."""
		usable, skipped = self._check([legacy_row()], invoice_exists=True)
		self.assertEqual(usable, [])
		self.assertEqual(skipped["already_in_erp"], ["IF25030183"])

	def test_dry_run_lists_fiscal_years_without_creating_them(self):
		before = frappe.db.count("Fiscal Year")
		missing = _ensure_fiscal_years([{"date": date(2019, 11, 23)}], dry_run=True)
		self.assertEqual(frappe.db.count("Fiscal Year"), before)
		self.assertIsInstance(missing, list)

	# -- invoice controls -----------------------------------------------------

	def test_controls_are_enforced_unless_switched_off(self):
		"""An unset switch must not silently disable a financial control."""
		with patch(
			"bp.overrides.sales_invoice.frappe.db.get_single_value", return_value=None
		):
			self.assertTrue(enforced("enforce_credit_limit"))
		with patch("bp.overrides.sales_invoice.frappe.db.get_single_value", return_value=0):
			self.assertFalse(enforced("enforce_credit_limit"))
		with patch("bp.overrides.sales_invoice.frappe.db.get_single_value", return_value=1):
			self.assertTrue(enforced("enforce_active_invoice_limit"))
