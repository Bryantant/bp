# Copyright (c) 2026, BP and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from bp.bp.page.inquiry.inquiry import _clean_remarks, _item_conditions, _item_hpp


class TestInquiryDescriptionFilter(UnitTestCase):
	def test_every_word_must_match_item_name(self):
		conds, params = _item_conditions({"description": "  milk   choco "}, "sii")
		self.assertEqual(conds, "sii.item_name like %(desc_0)s and sii.item_name like %(desc_1)s")
		self.assertEqual(params, {"desc_0": "%milk%", "desc_1": "%choco%"})

	def test_like_wildcards_are_literal(self):
		_conds, params = _item_conditions({"description": "50%_off"}, "it")
		self.assertEqual(params["desc_0"], "%50\\%\\_off%")

	def test_empty_description_adds_nothing(self):
		self.assertEqual(_item_conditions({"description": "   "}, "it"), ("", {}))


class TestInquiryItemFilter(UnitTestCase):
	def test_several_items(self):
		conds, params = _item_conditions({"item": ["A-1", "", "B-2"]}, "it")
		self.assertEqual(conds, "it.item_code in %(items)s")
		self.assertEqual(params, {"items": ("A-1", "B-2")})

	def test_single_item_still_accepted(self):
		_conds, params = _item_conditions({"item": "A-1"}, "it")
		self.assertEqual(params, {"items": ("A-1",)})


class TestInquiryRemarks(UnitTestCase):
	def test_placeholder_is_blanked(self):
		rows = _clean_remarks([{"remarks": "No Remarks"}, {"remarks": "DI JEMPUT PULAU MAS"}, {"remarks": None}])
		self.assertEqual([r["remarks"] for r in rows], [None, "DI JEMPUT PULAU MAS", None])


class TestInquiryHpp(IntegrationTestCase):
	"""HPP is read from Bin: stock transactions never update Item.valuation_rate."""

	def setUp(self):
		self.whs = frappe.get_all("Warehouse", filters={"is_group": 0}, pluck="name", limit=2)
		self.assertEqual(len(self.whs), 2, "needs two leaf warehouses")

	def _item(self, code, valuation_rate=0):
		return frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": code,
				"item_group": frappe.get_all("Item Group", filters={"is_group": 0}, pluck="name", limit=1)[0],
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"valuation_rate": valuation_rate,
			}
		).insert(ignore_permissions=True)

	def _bin(self, item_code, warehouse, qty, rate):
		frappe.get_doc(
			{
				"doctype": "Bin",
				"item_code": item_code,
				"warehouse": warehouse,
				"actual_qty": qty,
				"valuation_rate": rate,
				"stock_value": qty * rate,
			}
		).insert(ignore_permissions=True)

	def test_weighted_average_over_bins_when_item_rate_is_zero(self):
		self._item("_T-HPP-1")
		self._bin("_T-HPP-1", self.whs[0], 10, 100)
		self._bin("_T-HPP-1", self.whs[1], 30, 200)
		# (10 * 100 + 30 * 200) / 40
		self.assertAlmostEqual(_item_hpp(["_T-HPP-1"])["_T-HPP-1"], 175.0)

	def test_empty_bin_does_not_dilute_the_average(self):
		self._item("_T-HPP-2")
		self._bin("_T-HPP-2", self.whs[0], 10, 100)
		self._bin("_T-HPP-2", self.whs[1], 0, 900)
		self.assertAlmostEqual(_item_hpp(["_T-HPP-2"])["_T-HPP-2"], 100.0)

	def test_no_stock_falls_back_to_bin_rate_then_item_rate(self):
		self._item("_T-HPP-3")
		self._bin("_T-HPP-3", self.whs[0], 0, 100)
		self._bin("_T-HPP-3", self.whs[1], 0, 300)
		self._item("_T-HPP-4", valuation_rate=55)
		self._item("_T-HPP-5")
		hpp = _item_hpp(["_T-HPP-3", "_T-HPP-4", "_T-HPP-5"])
		self.assertAlmostEqual(hpp["_T-HPP-3"], 200.0)
		self.assertAlmostEqual(hpp["_T-HPP-4"], 55.0)
		self.assertEqual(hpp["_T-HPP-5"], 0)

	def test_no_items_no_query(self):
		self.assertEqual(_item_hpp([]), {})
