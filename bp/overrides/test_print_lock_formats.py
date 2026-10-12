from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from bp.overrides import sales_invoice as si

MODULE = "bp.overrides.sales_invoice"


def _printed_invoice():
	return frappe._dict(name="SINV-TEST-PRINT-LOCK", docstatus=1, bp_print_status="Printed", bp_print_count=1)


class TestPrintLockFormats(IntegrationTestCase):
	def setUp(self):
		frappe.flags.bp_print_done = None
		frappe.form_dict.pop("trigger_print", None)
		frappe.form_dict.pop("cmd", None)

	def tearDown(self):
		frappe.flags.bp_print_done = None
		frappe.form_dict.pop("trigger_print", None)

	@patch(f"{MODULE}._force_commit")
	@patch(f"{MODULE}._log")
	@patch(f"{MODULE}.enforced", return_value=True)
	@patch(f"{MODULE}._locked_formats", return_value={"Sales Invoice"})
	def test_listed_format_blocks_a_reprint(self, *_):
		with self.assertRaises(frappe.ValidationError):
			si._gate(_printed_invoice(), "Sales Invoice")

	@patch(f"{MODULE}._force_commit")
	@patch(f"{MODULE}._log")
	@patch(f"{MODULE}.enforced", return_value=True)
	@patch(f"{MODULE}._locked_formats", return_value={"Sales Invoice"})
	def test_unlisted_format_prints_freely(self, _formats, _enforced, log, _commit):
		si._gate(_printed_invoice(), "Debit Note")
		log.assert_not_called()

	@patch(f"{MODULE}.frappe.db.set_value")
	@patch(f"{MODULE}._log")
	@patch(f"{MODULE}._locked_formats", return_value={"Sales Invoice"})
	def test_unlisted_format_does_not_use_up_the_allowance(self, _formats, log, set_value):
		frappe.form_dict.trigger_print = 1
		doc = frappe._dict(name="SINV-TEST-PRINT-LOCK", docstatus=1, bp_print_status="", bp_print_count=0)
		si._gate(doc, "Debit Note")
		set_value.assert_not_called()
		log.assert_not_called()

	@patch(f"{MODULE}._force_commit")
	@patch(f"{MODULE}._log")
	@patch(f"{MODULE}.enforced", return_value=True)
	@patch(f"{MODULE}._locked_formats", return_value=set())
	def test_empty_list_locks_nothing(self, *_):
		si._gate(_printed_invoice(), "Sales Invoice")

	@patch(f"{MODULE}._force_commit")
	@patch(f"{MODULE}._log")
	@patch(f"{MODULE}.enforced", return_value=True)
	def test_no_format_asked_falls_back_to_the_default(self, *_):
		default = frappe.get_meta("Sales Invoice").default_print_format or "Standard"
		with patch(f"{MODULE}._locked_formats", return_value={default}):
			with self.assertRaises(frappe.ValidationError):
				si._gate(_printed_invoice(), None)

	def test_settings_reject_a_non_invoice_format(self):
		other = frappe.db.get_value("Print Format", {"doc_type": ["!=", "Sales Invoice"]}, "name")
		if not other:
			self.skipTest("no non-invoice print format on this site")
		settings = frappe.get_single("BP Settings")
		settings.append("print_lock_formats", {"print_format": other})
		with self.assertRaises(frappe.ValidationError):
			settings.validate_print_lock_formats()
