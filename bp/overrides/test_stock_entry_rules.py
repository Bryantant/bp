from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from bp.overrides import stock_entry

ROLES = "bp.overrides.stock_entry.frappe.get_roles"


def _entry(purpose):
	return frappe._dict(doctype="Stock Entry", purpose=purpose)


class TestStockEntryTypeByRole(IntegrationTestCase):
	def test_sales_only_user_may_only_relocate(self):
		with patch(ROLES, return_value=["Sales User", "Employee"]):
			stock_entry.validate(_entry("Material Transfer"))
			for purpose in ("Material Issue", "Material Receipt", "Repack"):
				with self.assertRaises(frappe.ValidationError):
					stock_entry.validate(_entry(purpose))

	def test_accounting_and_stock_roles_use_every_type(self):
		for roles in (["Accounts User"], ["Accounts Manager"], ["Sales User", "Stock User"]):
			with patch(ROLES, return_value=roles):
				for purpose in ("Material Issue", "Material Receipt", "Repack", "Material Transfer"):
					stock_entry.validate(_entry(purpose))

	def test_sales_entry_type_is_relocation(self):
		entry_type = stock_entry.get_sales_entry_type()
		self.assertEqual(frappe.db.get_value("Stock Entry Type", entry_type, "purpose"), "Material Transfer")
