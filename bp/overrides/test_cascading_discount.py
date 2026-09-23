from frappe.tests import IntegrationTestCase

from bp.utils.cascading_discount import calculate_cascading_discount


class IntegrationTestCascadingDiscount(IntegrationTestCase):
	"""Unit tests for the pure cascading-discount function shared by
	bp.overrides.sales_invoice and bp.overrides.sales_order. No doc/DB
	fixtures needed -- calculate_cascading_discount() is doc-agnostic."""

	def test_normal_cascading_case(self):
		# price_list_rate=1000, disc1=10%, disc2=5% -> after_disc1=900, final=855
		result = calculate_cascading_discount(
			price_list_rate=1000, discount1_percentage=10, discount2_percentage=5
		)
		self.assertEqual(result["rate"], 855)
		self.assertEqual(result["discount1_amount"], 100)
		self.assertEqual(result["discount2_amount"], 45)
		self.assertEqual(result["discount_percentage"], 14.5)  # 1 - 0.9*0.95 = 0.145
		self.assertEqual(result["discount_amount"], 145)

	def test_zero_price_list_rate_zeroes_everything(self):
		result = calculate_cascading_discount(
			price_list_rate=0, discount1_percentage=10, discount2_percentage=5
		)
		self.assertEqual(result["rate"], 0)
		self.assertEqual(result["discount1_amount"], 0)
		self.assertEqual(result["discount2_amount"], 0)

	def test_negative_price_list_rate_zeroes_everything(self):
		result = calculate_cascading_discount(
			price_list_rate=-100, discount1_percentage=10, discount2_percentage=5
		)
		self.assertEqual(result["rate"], 0)

	def test_amount_driven_input_derives_percentage(self):
		# price_list_rate=1000, discount1_amount=100 (no pct given) -> pct should back-derive to 10
		result = calculate_cascading_discount(
			price_list_rate=1000, discount1_amount=100, discount2_percentage=5
		)
		self.assertEqual(result["discount1_percentage"], 10)
		self.assertEqual(result["rate"], 855)

	def test_full_discount1_zeroes_discount2(self):
		# discount1=100% -> after_disc1=0 -> discount2 forced to 0, no ZeroDivisionError
		result = calculate_cascading_discount(
			price_list_rate=1000, discount1_percentage=100, discount2_percentage=50
		)
		self.assertEqual(result["rate"], 0)
		self.assertEqual(result["discount2_percentage"], 0)
