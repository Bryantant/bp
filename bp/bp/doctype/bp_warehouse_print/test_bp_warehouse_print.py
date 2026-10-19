from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from bp import warehouse_print as wp

MODULE = "bp.warehouse_print"
FAKE_PDF = b"%PDF-1.4 test"


def _events(name):
	return frappe.get_all(
		"BP Invoice Print Log", filters={"warehouse_print": name}, pluck="event_type", order_by="creation asc"
	)


@patch(f"{MODULE}._force_commit")  # never commit test data from the Blocked path
@patch(f"{MODULE}.frappe.get_print", return_value=FAKE_PDF)
@patch(f"{MODULE}._locked_formats", return_value={"Invoice", "Delivery Order"})
class TestBPWarehousePrint(UnitTestCase):
	"""Runs against the site's real data inside one transaction that is rolled
	back at the end. UnitTestCase, not IntegrationTestCase: the latter builds
	ERPNext test records for every linked doctype, which pollutes a real site
	(erpnext-dev-lessons #58/#67). Run it with the stdlib unittest runner inside
	bench execute, as testing-strategy.md describes."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.addClassCleanup(frappe.db.rollback)
		cls.invoice = frappe.db.get_value("Sales Invoice", {"docstatus": 1, "is_return": 0}, "name")
		if not cls.invoice:
			raise cls.skipTest(cls, "no submitted Sales Invoice on this site")

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.local.response = frappe._dict()
		self._formats = patch(
			"bp.overrides.sales_invoice._locked_formats", return_value={"Invoice", "Delivery Order"}
		)
		self._formats.start()

	def tearDown(self):
		self._formats.stop()
		frappe.set_user("Administrator")

	def _send(self, print_format="Delivery Order"):
		return wp.send_to_warehouse(self.invoice, print_format)

	def test_send_queues_a_pending_row_and_logs_it(self, *_):
		name = self._send()
		row = frappe.get_doc("BP Warehouse Print", name)
		self.assertEqual(row.status, "Pending")
		self.assertEqual(row.sent_by, "Administrator")
		self.assertEqual(row.customer, frappe.db.get_value("Sales Invoice", self.invoice, "customer"))
		self.assertEqual(_events(name), ["Sent"])

	def test_format_outside_the_list_is_rejected(self, *_):
		with self.assertRaises(frappe.ValidationError):
			self._send("Debit Note")

	def test_draft_invoice_is_rejected(self, *_):
		draft = frappe.db.get_value("Sales Invoice", {"docstatus": 0}, "name")
		if not draft:
			self.skipTest("no draft Sales Invoice on this site")
		with self.assertRaises(frappe.ValidationError):
			wp.send_to_warehouse(draft, "Delivery Order")

	def test_first_print_uses_up_the_row(self, _formats, get_print, _commit):
		name = self._send()
		wp.print_pdf(name)
		row = frappe.get_doc("BP Warehouse Print", name)
		self.assertEqual(row.status, "Printed")
		self.assertEqual(row.print_count, 1)
		self.assertEqual(row.printed_by, "Administrator")
		self.assertEqual(frappe.local.response.filecontent, FAKE_PDF)
		self.assertEqual(frappe.local.response.type, "pdf")
		get_print.assert_called_once_with("Sales Invoice", self.invoice, "Delivery Order", as_pdf=True)
		# the printed-by stamp on the copy comes from these invoice fields
		self.assertEqual(
			frappe.db.get_value("Sales Invoice", self.invoice, "bp_last_printed_by"), "Administrator"
		)
		self.assertEqual(_events(name), ["Sent", "Printed"])

	def test_second_print_is_blocked_and_logged(self, _formats, get_print, force_commit):
		name = self._send()
		wp.print_pdf(name)
		with self.assertRaises(frappe.ValidationError):
			wp.check_print(name)
		with self.assertRaises(frappe.ValidationError):
			wp.print_pdf(name)
		self.assertEqual(get_print.call_count, 1)
		self.assertEqual(_events(name), ["Sent", "Printed", "Blocked", "Blocked"])
		self.assertTrue(force_commit.called)

	def test_reset_allows_one_more_print(self, *_):
		name = self._send()
		wp.print_pdf(name)
		wp.reset(name, "Kertas macet")
		self.assertEqual(frappe.db.get_value("BP Warehouse Print", name, "status"), "Pending")
		wp.print_pdf(name)
		self.assertEqual(frappe.db.get_value("BP Warehouse Print", name, "print_count"), 2)
		self.assertEqual(_events(name), ["Sent", "Printed", "Reset", "Printed"])

	def test_reset_needs_a_reason(self, *_):
		name = self._send()
		wp.print_pdf(name)
		with self.assertRaises(frappe.ValidationError):
			wp.reset(name, " ")

	def test_resend_creates_a_new_printable_row(self, *_):
		first = self._send()
		wp.print_pdf(first)
		second = self._send()
		self.assertNotEqual(first, second)
		self.assertEqual(frappe.db.get_value("BP Warehouse Print", second, "status"), "Pending")
		history = wp.send_history(self.invoice)["history"]["Delivery Order"]
		self.assertGreaterEqual(history["sent"], 2)
		self.assertGreaterEqual(history["pending"], 1)

	def test_cancelled_invoice_cannot_be_printed(self, *_):
		name = self._send()
		frappe.db.set_value("Sales Invoice", self.invoice, "docstatus", 2, update_modified=False)
		try:
			with self.assertRaises(frappe.ValidationError):
				wp.print_pdf(name)
		finally:
			frappe.db.set_value("Sales Invoice", self.invoice, "docstatus", 1, update_modified=False)

	def test_print_and_reset_need_the_right_role(self, *_):
		name = self._send()
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			wp.print_pdf(name)
		with self.assertRaises(frappe.PermissionError):
			wp.reset(name, "no role")

	def test_queue_render_is_not_counted_twice(self, _formats, get_print, _commit):
		# The before_print gate runs inside get_print; it must not log or count the
		# queue's own render a second time.
		from bp.overrides import sales_invoice as si

		def render(doctype, invoice, print_format, as_pdf):
			si._gate(frappe._dict(name=invoice, docstatus=1, bp_print_status="Printed"), print_format)
			return FAKE_PDF

		get_print.side_effect = render
		name = self._send()
		direct = {"sales_invoice": self.invoice, "warehouse_print": ("is", "not set")}
		before = frappe.db.count("BP Invoice Print Log", direct)
		frappe.form_dict.trigger_print = 1
		try:
			wp.print_pdf(name)
		finally:
			frappe.form_dict.pop("trigger_print", None)
		self.assertEqual(frappe.db.get_value("BP Warehouse Print", name, "status"), "Printed")
		self.assertEqual(_events(name), ["Sent", "Printed"])
		self.assertEqual(frappe.db.count("BP Invoice Print Log", direct), before)
		self.assertFalse(frappe.flags.bp_print_done)
