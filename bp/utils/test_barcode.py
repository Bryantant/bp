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
