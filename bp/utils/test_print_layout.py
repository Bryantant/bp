import unittest

from bp.utils.print_layout import bp_item_line, bp_paginate, description_lines


def _rows(*descriptions):
	return [{"description": d} for d in descriptions]


def _numbers(pages):
	return [[i for i, _ in page] for page in pages]


class TestPrintLayout(unittest.TestCase):
	def test_description_lines(self):
		self.assertEqual(description_lines("ONE LINE", 40), 1)
		self.assertEqual(description_lines("NAME\nBRAND", 40), 2)
		self.assertEqual(description_lines("<div><p>KIN DEZZERT</p><p>==== 411292</p></div>", 40), 2)
		self.assertEqual(description_lines("A" * 81, 40), 3)  # wraps twice
		self.assertEqual(description_lines("", 40), 1)

	def test_short_invoice_is_one_page(self):
		pages = bp_paginate(_rows("A\nB", "C\nD", "E\nF"), page_px=285, last_page_px=130)
		self.assertEqual(_numbers(pages), [[1, 2, 3]])

	def test_full_pages_then_last_page_with_room_for_totals(self):
		# two-line rows are 5 + 2 x 14.3 = 33.6 px: 8 per full page, 3 with the totals
		pages = bp_paginate(_rows(*["A\nB"] * 20), page_px=285, last_page_px=130)
		self.assertEqual([len(p) for p in pages], [8, 8, 1, 3])
		self.assertEqual(_numbers(pages)[0][0], 1)
		self.assertEqual(_numbers(pages)[-1][-1], 20)

	def test_last_page_that_fits_is_kept(self):
		pages = bp_paginate(_rows(*["A\nB"] * 11), page_px=285, last_page_px=130)
		self.assertEqual([len(p) for p in pages], [8, 3])

	def test_line_taller_than_the_totals_space_gets_totals_their_own_page(self):
		pages = bp_paginate(_rows("X" * 400), page_px=285, last_page_px=130)
		self.assertEqual([len(p) for p in pages], [1, 0])

	def test_no_items(self):
		self.assertEqual(bp_paginate([]), [[]])

	def test_item_line_joins_parts_without_placeholders(self):
		self.assertEqual(bp_item_line("NOMI OSHI ROTI GULUNG SRIKAYA60 GR\n==== A-06"), "NOMI OSHI ROTI GULUNG SRIKAYA60 GR A-06")
		self.assertEqual(bp_item_line("STERNO GEL REFILL 14 KG -\nNB - -"), "STERNO GEL REFILL 14 KG NB")
		self.assertEqual(bp_item_line("<div><p>KIN DEZZERT</p><p>==== 411292</p></div>"), "KIN DEZZERT 411292")
		self.assertEqual(bp_item_line("MOP 30-40 CM"), "MOP 30-40 CM")  # a dash inside a word stays
		self.assertEqual(bp_item_line(None), "")

	def test_one_line_rows(self):
		# one-line rows are 5 + 14.3 = 19.3 px: 14 per full page, 6 with the totals
		pages = bp_paginate(_rows(*["A\nB"] * 31), page_px=285, last_page_px=130, one_line=True)
		self.assertEqual([len(p) for p in pages], [14, 14, 3])
