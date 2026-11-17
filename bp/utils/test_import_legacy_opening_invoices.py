from datetime import date, datetime
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from bp.overrides.sales_invoice import enforced
from bp.utils.import_legacy_opening_invoices import (
	SOURCES,
	_check_rows,
	_ensure_fiscal_years,
	_upload_value,
	_write_upload_csv,
)


def legacy_row(**kw):
	row = {
		"InvoicNo": "IF25030183",
		"InvDate": datetime(2025, 3, 17),
		"party": "A0088",
		"CredTerm": 30,
		"AmtInv": 10_000_000,
		# What the invoice had already been paid BEFORE the cutoff date; the
		# fetch computes this per invoice (payments after the cutoff do not
		# reduce the balance being carried over).
		"paid_before": 0,
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

	def test_carries_the_balance_owed_on_the_cutoff_date(self):
		usable, _ = self._check([legacy_row(AmtInv=10_000_000, paid_before=4_000_000)])
		self.assertEqual(usable[0]["outstanding"], 6_000_000)

	def test_an_invoice_paid_after_the_cutoff_is_still_carried_in_full(self):
		"""Its payment is imported as a document later and needs this invoice
		to settle against -- carrying it at today's zero balance would leave
		that payment with no target."""
		usable, _ = self._check([legacy_row(AmtInv=10_000_000, paid_before=0, InvStatu=5)])
		self.assertEqual(usable[0]["outstanding"], 10_000_000)

	def test_due_date_follows_the_legacy_credit_term(self):
		usable, _ = self._check([legacy_row(InvDate=datetime(2025, 3, 17), CredTerm=30)])
		self.assertEqual(usable[0]["date"], date(2025, 3, 17))
		self.assertEqual(usable[0]["due_date"], date(2025, 4, 16))

	def test_rows_already_settled_before_the_cutoff_are_left_out(self):
		usable, skipped = self._check([legacy_row(AmtInv=1_000_000, paid_before=1_000_000)])
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

	# -- export for the tool's Upload button ---------------------------------

	def test_upload_values_match_what_the_grid_parses(self):
		"""The grid Upload converts dates with the user's date format and
		amounts with flt(), so write dates that way and amounts ungrouped."""
		meta = frappe.get_meta("Opening Invoice Creation Tool Item")
		date_df = meta.get_field("posting_date")
		amount_df = meta.get_field("outstanding_amount")
		with patch("bp.utils.import_legacy_opening_invoices.formatdate", return_value="31-08-2018"):
			self.assertEqual(_upload_value(date_df, date(2018, 8, 31)), "31-08-2018")
		self.assertEqual(_upload_value(amount_df, 16286082021.34), "16286082021.34")
		self.assertEqual(_upload_value(amount_df, None), "")

	def test_upload_file_has_the_bulk_edit_layout(self):
		"""Row 2 holds the fieldnames the Upload maps by; data starts on row 7."""
		import csv
		import os
		import tempfile

		meta = frappe.get_meta("Opening Invoice Creation Tool Item")
		fields = [meta.get_field("invoice_number"), meta.get_field("outstanding_amount")]
		with tempfile.TemporaryDirectory() as tmp:
			path = os.path.join(tmp, "t.csv")
			_write_upload_csv(path, fields, [{"invoice_number": "IF25030183", "outstanding_amount": 5}], "dd-mm-yyyy")
			with open(path, newline="", encoding="utf-8") as f:
				data = list(csv.reader(f))
		self.assertEqual(data[0], ["Bulk Edit Invoices"])
		self.assertEqual(data[2], ["invoice_number", "outstanding_amount"])
		self.assertEqual(data[6], ["------"])
		self.assertEqual(data[7], ["IF25030183", "5.00"])

	# -- invoice controls -----------------------------------------------------

	def test_controls_are_enforced_unless_switched_off(self):
		"""An unset switch must not silently disable a financial control.

		enforced() reads the raw tabSingles row (b90e8af): get_single_value()
		casts a never-saved Check to 0, which would switch a new control off.
		"""
		raw = "bp.overrides.sales_invoice.frappe.db.sql"
		with patch(raw, return_value=()):
			self.assertTrue(enforced("enforce_credit_limit"))
		with patch(raw, return_value=((None,),)):
			self.assertTrue(enforced("enforce_credit_limit"))
		with patch(raw, return_value=(("0",),)):
			self.assertFalse(enforced("enforce_credit_limit"))
		with patch(raw, return_value=(("1",),)):
			self.assertTrue(enforced("enforce_active_invoice_limit"))
