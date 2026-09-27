from frappe.tests import IntegrationTestCase

from bp.utils.cascading_discount import calculate_cascading_discount


class IntegrationTestCascadingDiscount(IntegrationTestCase):
	"""Unit tests for the pure four-step cascading-discount function shared by
	bp.overrides.sales_invoice and bp.overrides.sales_order. No doc/DB
	fixtures needed -- calculate_cascading_discount() is doc-agnostic."""

	def test_two_percentages_compound(self):
		# 1000 -> 10% = 900 -> 5% = 855
		result = calculate_cascading_discount(
			price_list_rate=1000, discount1_percentage=10, discount2_percentage=5
		)
		self.assertEqual(result["rate"], 855)
		self.assertEqual(result["discount_percentage"], 14.5)  # 1 - 0.9*0.95
		self.assertEqual(result["discount_amount"], 145)

	def test_four_steps_apply_in_order(self):
		# 1000 -> 10% = 900 -> -50 = 850 -> 5% = 807.50 -> -7.50 = 800
		result = calculate_cascading_discount(
			price_list_rate=1000,
			discount1_percentage=10,
			discount1_amount=50,
			discount2_percentage=5,
			discount2_amount=7.5,
		)
		self.assertEqual(result["rate"], 800)
		self.assertEqual(result["discount_percentage"], 20)
		self.assertEqual(result["discount_amount"], 200)

	def test_percentage_and_amount_of_one_tier_both_count(self):
		# Not one discount typed two ways: 10% and 100 are both taken.
		result = calculate_cascading_discount(
			price_list_rate=1000, discount1_percentage=10, discount1_amount=100
		)
		self.assertEqual(result["rate"], 800)

	def test_amount_alone(self):
		result = calculate_cascading_discount(price_list_rate=5161.42, discount1_amount=500)
		self.assertEqual(result["rate"], 4661.42)

	def test_discount2_percentage_is_on_price_after_discount1_amount(self):
		# 1000 -> -200 = 800 -> 10% = 720
		result = calculate_cascading_discount(
			price_list_rate=1000, discount1_amount=200, discount2_percentage=10
		)
		self.assertEqual(result["rate"], 720)

	def test_zero_price_list_rate_zeroes_everything(self):
		result = calculate_cascading_discount(
			price_list_rate=0, discount1_percentage=10, discount2_percentage=5
		)
		self.assertEqual(result["rate"], 0)
		self.assertEqual(result["discount_amount"], 0)

	def test_negative_price_list_rate_zeroes_everything(self):
		result = calculate_cascading_discount(
			price_list_rate=-100, discount1_percentage=10, discount2_percentage=5
		)
		self.assertEqual(result["rate"], 0)

	def test_rate_never_goes_below_zero(self):
		result = calculate_cascading_discount(
			price_list_rate=1000, discount1_percentage=50, discount1_amount=600, discount2_amount=10
		)
		self.assertEqual(result["rate"], 0)
		self.assertEqual(result["discount_percentage"], 100)

	def test_full_discount1_leaves_nothing_for_discount2(self):
		result = calculate_cascading_discount(
			price_list_rate=1000, discount1_percentage=100, discount2_percentage=50
		)
		self.assertEqual(result["rate"], 0)
