from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from bp.overrides import sales_invoice as si

MODULE = "bp.overrides.sales_invoice"


def _printed_invoice():
	return frappe._dict(name="SINV-TEST-PRINT-LOCK", docstatus=1, bp_print_status="Printed", bp_print_count=1)


class TestPrintLockFormats(UnitTestCase):
	"""Printing from the Sales Invoice is always free (HT-171): the gate only logs
	and counts real prints of the listed formats. UnitTestCase so no ERPNext test
	records are built (erpnext-dev-lessons #58/#67)."""

	def setUp(self):
		frappe.flags.bp_print_done = None
		frappe.form_dict.pop("trigger_print", None)
		frappe.form_dict.pop("cmd", None)

	def tearDown(self):
		frappe.flags.bp_print_done = None
		frappe.form_dict.pop("trigger_print", None)

	@patch(f"{MODULE}.frappe.db.set_value")
	@patch(f"{MODULE}._log")
	@patch(f"{MODULE}._locked_formats", return_value={"Invoice"})
	def test_reprint_of_a_listed_format_is_logged_not_blocked(self, _formats, log, set_value):
		frappe.form_dict.trigger_print = 1
		si._gate(_printed_invoice(), "Invoice")
		log.assert_called_once()
		self.assertEqual(set_value.call_args[0][2]["bp_print_count"], 2)

	@patch(f"{MODULE}.frappe.db.set_value")
	@patch(f"{MODULE}._log")
	@patch(f"{MODULE}._locked_formats", return_value={"Invoice"})
	def test_preview_is_not_counted(self, _formats, log, set_value):
		si._gate(_printed_invoice(), "Invoice")
		log.assert_not_called()
		set_value.assert_not_called()

	@patch(f"{MODULE}.frappe.db.set_value")
	@patch(f"{MODULE}._log")
	@patch(f"{MODULE}._locked_formats", return_value={"Invoice"})
	def test_unlisted_format_leaves_no_trail(self, _formats, log, set_value):
		frappe.form_dict.trigger_print = 1
		si._gate(_printed_invoice(), "Debit Note")
		set_value.assert_not_called()
		log.assert_not_called()

	@patch(f"{MODULE}.frappe.db.set_value")
	@patch(f"{MODULE}._log")
	def test_no_format_asked_falls_back_to_the_default(self, log, _set_value):
		frappe.form_dict.trigger_print = 1
		default = frappe.get_meta("Sales Invoice").default_print_format or "Standard"
		with patch(f"{MODULE}._locked_formats", return_value={default}):
			si._gate(_printed_invoice(), None)
		self.assertEqual(log.call_args[0][2], default)

	def test_settings_reject_a_non_invoice_format(self):
		other = frappe.db.get_value("Print Format", {"doc_type": ["!=", "Sales Invoice"]}, "name")
		if not other:
			self.skipTest("no non-invoice print format on this site")
		settings = frappe.get_single("BP Settings")
		settings.append("print_lock_formats", {"print_format": other})
		with self.assertRaises(frappe.ValidationError):
			settings.validate_print_lock_formats()
