from unittest.mock import patch

from frappe.tests import IntegrationTestCase

from bp.overrides import user

STANDARD = "bp.overrides.user.standard_get_perm_info"


class TestRolePermissionDialog(IntegrationTestCase):
	def test_rows_with_only_select_are_hidden(self):
		rows = [
			{"parent": "Batch", "permlevel": 0, "select": 1, "read": 0},
			{"parent": "Sales Invoice", "permlevel": 0, "select": 1, "read": 1},
			{"parent": "Item", "permlevel": 0, "select": 0, "read": 0, "report": 1},
		]
		with (
			patch(STANDARD, return_value=rows),
			patch("bp.overrides.user.get_doctype_ptype_map", return_value={}),
		):
			self.assertEqual(
				[r["parent"] for r in user.get_perm_info("X", view="no_select")], ["Item", "Sales Invoice"]
			)

	def test_custom_permission_type_counts_as_a_right(self):
		rows = [{"parent": "Sales Invoice", "permlevel": 0, "select": 1, "approve": 1}]
		with (
			patch(STANDARD, return_value=rows),
			patch("bp.overrides.user.get_doctype_ptype_map", return_value={"Sales Invoice": ["approve"]}),
		):
			self.assertEqual(len(user.get_perm_info("X", view="no_select")), 1)

	def test_role_without_any_row_gives_empty_list(self):
		with (
			patch(STANDARD, return_value=[]),
			patch("bp.overrides.user.get_doctype_ptype_map", return_value={}),
		):
			self.assertEqual(user.get_perm_info("X", view="no_select"), [])

	def test_toggle_gives_the_standard_list(self):
		rows = [
			{"parent": "Batch", "permlevel": 0, "select": 1},
			{"parent": "Item", "permlevel": 0, "read": 1},
		]
		with (
			patch(STANDARD, return_value=rows),
			patch("bp.overrides.user.get_doctype_ptype_map", return_value={}),
		):
			self.assertEqual(len(user.get_perm_info("X", view="standard")), 2)
			self.assertEqual(len(user.get_perm_info("X", view="standard")), 2)
			self.assertEqual(len(user.get_perm_info("X", view="no_select")), 1)
			self.assertEqual(len(user.get_perm_info("X", view="no_select")), 1)

	def test_most_rights_first_then_alphabetical(self):
		rows = [
			{"parent": "Warehouse", "permlevel": 0, "read": 1},
			{"parent": "Batch", "permlevel": 0, "select": 1},
			{"parent": "Sales Invoice", "permlevel": 0, "read": 1, "write": 1, "create": 1, "submit": 1},
			{"parent": "Item", "permlevel": 0, "read": 1},
			{"parent": "Customer", "permlevel": 0, "read": 1, "report": 1},
		]
		with (
			patch(STANDARD, return_value=rows),
			patch("bp.overrides.user.get_doctype_ptype_map", return_value={}),
		):
			self.assertEqual(
				[r["parent"] for r in user.get_perm_info("X", view="no_select")],
				["Sales Invoice", "Customer", "Item", "Warehouse"],
			)
			self.assertEqual(user.get_perm_info("X", view="standard")[-1]["parent"], "Batch")

	def test_write_view_keeps_only_rows_that_change_documents(self):
		rows = [
			{"parent": "Item", "permlevel": 0, "read": 1, "report": 1},
			{"parent": "Batch", "permlevel": 0, "select": 1},
			{"parent": "Customer", "permlevel": 0, "read": 1, "write": 1},
			{"parent": "Sales Invoice", "permlevel": 0, "read": 1, "submit": 1},
			{"parent": "Contact", "permlevel": 0, "read": 1, "create": 1},
		]
		with (
			patch(STANDARD, return_value=rows),
			patch("bp.overrides.user.get_doctype_ptype_map", return_value={}),
		):
			self.assertEqual(
				[r["parent"] for r in user.get_perm_info("X", view="write")],
				["Contact", "Customer", "Sales Invoice"],
			)
			self.assertEqual(
				len(user.get_perm_info("X", view="nonsense")), 3
			)  # unknown view = default (write)

	def test_default_view_is_write(self):
		rows = [
			{"parent": "Item", "permlevel": 0, "read": 1},
			{"parent": "Customer", "permlevel": 0, "read": 1, "write": 1},
		]
		with (
			patch(STANDARD, return_value=rows),
			patch("bp.overrides.user.get_doctype_ptype_map", return_value={}),
		):
			self.assertEqual([r["parent"] for r in user.get_perm_info("X")], ["Customer"])
