"""Two-tier cascading discount math shared by Sales Invoice Item and Sales
Order Item.

Discount 1 (supplier-side/claimable) is applied to price_list_rate; Discount 2
(internal company-policy) compounds on top of the *post-Discount-1* rate, not
price_list_rate directly -- 10% + 5% is 14.5%, not 15%. This is the standard
"harga list -> disc1 -> disc2 -> net" cascading-discount convention.

A pure function (no frappe.get_doc / doc mutation) so it's directly unit
testable and shared between bp.overrides.sales_invoice and
bp.overrides.sales_order, which are the server-side authority for these
values (see their docstrings) -- the client-side bp.discounts namespace in
public/js/discount_utils.bundle.js mirrors this same math for live UX.
"""

from frappe.utils import flt


def calculate_cascading_discount(
	price_list_rate,
	discount1_percentage=0,
	discount1_amount=0,
	discount2_percentage=0,
	discount2_amount=0,
	rate_precision=2,
	pct_precision=2,
	amt_precision=2,
):
	"""Return the cascaded rate plus the reconciled %/Amount pair for each tier.

	Whichever of a tier's percentage/amount was actually supplied drives that
	tier: percentage is preferred, amount is only used to back-derive
	percentage when percentage is 0 but amount isn't (robust to a data import
	or API call that only populated one side of the pair).
	"""
	price_list_rate = flt(price_list_rate)

	result = {
		"discount1_percentage": 0,
		"discount1_amount": 0,
		"discount2_percentage": 0,
		"discount2_amount": 0,
		"rate": 0,
		"discount_percentage": 0,
		"discount_amount": 0,
	}

	if price_list_rate <= 0:
		return result

	d1_pct = flt(discount1_percentage)
	if not d1_pct and discount1_amount:
		d1_pct = flt(flt(discount1_amount) / price_list_rate * 100, pct_precision)

	after_disc1 = flt(price_list_rate * (1 - d1_pct / 100), rate_precision)
	result["discount1_percentage"] = d1_pct
	result["discount1_amount"] = flt(price_list_rate - after_disc1, amt_precision)

	if after_disc1 <= 0:
		final_rate = 0
	else:
		d2_pct = flt(discount2_percentage)
		if not d2_pct and discount2_amount:
			d2_pct = flt(flt(discount2_amount) / after_disc1 * 100, pct_precision)

		final_rate = flt(after_disc1 * (1 - d2_pct / 100), rate_precision)
		result["discount2_percentage"] = d2_pct
		result["discount2_amount"] = flt(after_disc1 - final_rate, amt_precision)

	result["rate"] = final_rate
	result["discount_percentage"] = flt((1 - final_rate / price_list_rate) * 100, pct_precision)
	result["discount_amount"] = flt(price_list_rate - final_rate, amt_precision)
	return result
