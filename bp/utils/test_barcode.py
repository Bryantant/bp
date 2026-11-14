import base64
import unittest

from bp.utils import barcode


class TestCode128(unittest.TestCase):
	def test_table_is_complete_and_well_formed(self):
		self.assertEqual(len(barcode.PATTERNS), 107)
		self.assertEqual(len(set(barcode.PATTERNS)), 107)
		for value, pattern in enumerate(barcode.PATTERNS[:106]):
			self.assertEqual(sum(map(int, pattern)), 11, value)
		self.assertEqual(sum(map(int, barcode.PATTERNS[barcode.STOP])), 13)

	def test_checksum(self):
		# start B 104 + 1*33 ("A") + 2*34 ("B") = 205, 205 % 103 = 102
		self.assertEqual(barcode.code128_values("AB"), [104, 33, 34, 102, 106])

	def test_digit_runs_use_set_c(self):
		# "SINV-A" in set B, then CODE C (99) and 26 10 00 01; checksum 2
		self.assertEqual(
			barcode.code128_values("SINV-A26100001"),
			[104, 51, 41, 46, 54, 13, 33, 99, 26, 10, 0, 1, 2, 106],
		)
		# all digits: start C
		self.assertEqual(barcode.code128_values("26100001")[:5], [105, 26, 10, 0, 1])
		# odd run: first digit stays in set B
		self.assertEqual(barcode._segments("12345"), [["B", "1"], ["C", "2345"]])
		# short run in the middle stays in set B
		self.assertEqual(barcode._segments("A1234B"), [["B", "A1234B"]])

	def test_module_count(self):
		for value in ("C26090244", "SINV-A26100001", "ACC-SINV-2026-00012"):
			values = barcode.code128_values(value)
			self.assertEqual(sum(barcode.code128_modules(value)), 11 * len(values) + 2, value)

	def test_rejects_what_set_b_cannot_encode(self):
		for value in ("", None, "Tab\there", "Rp 100", "é"):
			with self.assertRaises(ValueError, msg=repr(value)):
				barcode.code128_values(value)

	def test_svg_data_uri(self):
		uri = barcode.code128_svg("C26090244")
		self.assertTrue(uri.startswith("data:image/svg+xml;base64,"))
		svg = base64.b64decode(uri.split(",", 1)[1]).decode()
		# widths alternate bar/space starting and ending with a bar: one <rect x=...> per bar
		widths = barcode.code128_modules("C26090244")
		self.assertEqual(svg.count("<rect x="), (len(widths) + 1) // 2)


class TestQr(unittest.TestCase):
	def _svg(self, value):
		uri = barcode.qr_svg(value)
		self.assertTrue(uri.startswith("data:image/svg+xml;base64,"))
		return base64.b64decode(uri.split(",", 1)[1]).decode()

	def _modules(self, svg):
		"""Rebuild the dark modules from the path, to compare with the matrix."""
		import re

		dark = set()
		quiet = 2
		for x, y, w in re.findall(r"M(\d+) (\d+)h(\d+)v1h-\d+z", svg):
			for i in range(int(w)):
				dark.add((int(x) - quiet + i, int(y) - quiet))
		return dark

	def test_invoice_name_is_version_2_and_about_25_mm(self):
		matrix = barcode.qr_matrix("INV-B26110116")
		self.assertEqual(len(matrix), 25)
		svg = self._svg("INV-B26110116")
		self.assertIn('width="24.55mm"', svg)  # (25 + 2 x 2) x 0.8467
		self.assertIn('viewBox="0 0 29 29"', svg)

	def test_short_name_is_version_1(self):
		self.assertEqual(len(barcode.qr_matrix("A26100002")), 21)

	def test_path_is_the_matrix(self):
		for value in ("INV-B26110116", "SR-A26110137", "A26100002", "ND-26100001", "I261100375"):
			matrix = barcode.qr_matrix(value)
			expected = {(x, y) for y, row in enumerate(matrix) for x, v in enumerate(row) if v}
			self.assertEqual(self._modules(self._svg(value)), expected, value)

	def test_finder_patterns_in_three_corners(self):
		matrix = barcode.qr_matrix("INV-B26110116")
		n = len(matrix)
		for ox, oy in ((0, 0), (n - 7, 0), (0, n - 7)):
			self.assertTrue(all(matrix[oy][ox + i] for i in range(7)))  # top bar of the finder
			self.assertTrue(all(matrix[oy + 6][ox + i] for i in range(7)))  # bottom bar
			self.assertEqual(matrix[oy + 3][ox + 3], 1)  # centre

	def test_rejects_empty_or_non_text(self):
		for value in ("", None, 12, "x" * 101):
			with self.assertRaises(ValueError, msg=repr(value)):
				barcode.qr_matrix(value)
