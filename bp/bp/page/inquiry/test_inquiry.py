# Copyright (c) 2026, BP and contributors
# For license information, please see license.txt

from frappe.tests import UnitTestCase

from bp.bp.page.inquiry.inquiry import _item_conditions


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
