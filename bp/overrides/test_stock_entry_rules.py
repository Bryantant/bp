from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from bp.overrides import stock_entry
from bp.patches.v1_0 import grant_stock_entry_to_sales_and_accounts as grant
from bp.setup.stock_mutation_sidebar import ITEM_DOCTYPE, LABEL, add_stock_mutation_link

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

	def test_sales_and_accounts_can_create_but_not_delete(self):
		grant.execute()
		for role in grant.ROLES:
			perm = frappe.db.get_value(
				"Custom DocPerm",
				{"parent": "Stock Entry", "role": role, "permlevel": 0},
				["read", "create", "submit", "cancel", "delete"],
				as_dict=True,
			)
			self.assertEqual((perm.read, perm.create, perm.submit, perm.cancel, perm.delete), (1, 1, 1, 1, 0))
		self.assertTrue(
			frappe.db.exists("Custom DocPerm", {"parent": "Stock Entry", "role": "Stock User", "submit": 1})
		)


class TestStockMutationSidebar(IntegrationTestCase):
	def test_link_inserted_once_after_inquiry(self):
		add_stock_mutation_link("Selling", "inquiry")
		add_stock_mutation_link("Selling", "inquiry")
		rows = frappe.get_all(
			ITEM_DOCTYPE,
			filters={"parent": "Selling", "parenttype": "Workspace Sidebar"},
			fields=["idx", "label", "link_to"],
			order_by="idx asc",
		)
		labels = [r.label for r in rows]
		self.assertEqual(labels.count(LABEL), 1)
		self.assertEqual(rows[labels.index(LABEL) - 1].link_to, "inquiry")
		self.assertEqual([r.idx for r in rows], list(range(1, len(rows) + 1)))
