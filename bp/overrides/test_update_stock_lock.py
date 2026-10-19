from unittest.mock import MagicMock

import frappe
from frappe.tests import UnitTestCase

from bp.overrides.update_stock_lock import validate


def invoice(update_stock, before_update_stock=None, is_new=False):
	doc = MagicMock()
	doc.is_new.return_value = is_new
	doc.meta.has_field.return_value = True
	doc.get.side_effect = lambda field: {"update_stock": update_stock}.get(field)
	if before_update_stock is None:
		doc.get_doc_before_save.return_value = None
	else:
		doc.get_doc_before_save.return_value = frappe._dict(update_stock=before_update_stock)
	return doc


class TestUpdateStockLock(UnitTestCase):
	def test_new_invoice_may_set_update_stock(self):
		validate(invoice(update_stock=1, is_new=True))

	def test_saved_draft_keeps_update_stock(self):
		validate(invoice(update_stock=1, before_update_stock=1))

	def test_saved_draft_cannot_turn_update_stock_on(self):
		self.assertRaises(frappe.ValidationError, validate, invoice(update_stock=1, before_update_stock=0))

	def test_saved_draft_cannot_turn_update_stock_off(self):
		self.assertRaises(frappe.ValidationError, validate, invoice(update_stock=0, before_update_stock=1))
