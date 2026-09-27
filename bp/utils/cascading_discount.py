"""Four-step cascading discount math shared by Sales Invoice Item and Sales
Order Item.

Each of the four fields is its own step, applied in this order to the price
left by the step before it:

	Price List Rate
	  -> Discount 1 %       (percentage of the price list rate)
	  -> Discount 1 Amount  (amount per unit off what is left)
	  -> Discount 2 %       (percentage of what is left)
	  -> Discount 2 Amount  (amount per unit off what is left)
	  = Rate

A percentage and the amount next to it are not two ways of typing the same
discount: both can be filled at once and both are taken. 10% then 5% is
14.5%, not 15%.

A pure function (no frappe.get_doc / doc mutation) so it's directly unit
testable. The client-side bp.discounts namespace in
public/js/discount_utils.bundle.js mirrors this same math for live UX.
"""

from frappe.utils import flt

DISCOUNT_FIELDS = (
	"custom_discount1_percentage",
	"custom_discount1_amount",
	"custom_discount2_percentage",
	"custom_discount2_amount",
)


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
	"""Return the rate left after the four steps, plus the combined discount.

	The price never goes below 0: a step that would take it there stops at 0
	and the steps after it have nothing left to discount.
	"""
	price_list_rate = flt(price_list_rate)
	result = {"rate": 0, "discount_percentage": 0, "discount_amount": 0}
	if price_list_rate <= 0:
		return result

	price = flt(price_list_rate * (1 - flt(discount1_percentage) / 100), rate_precision)
	price = max(flt(price - flt(discount1_amount), rate_precision), 0)
	price = flt(price * (1 - flt(discount2_percentage) / 100), rate_precision)
	price = max(flt(price - flt(discount2_amount), rate_precision), 0)

	result["rate"] = price
	result["discount_percentage"] = flt((1 - price / price_list_rate) * 100, pct_precision)
	result["discount_amount"] = flt(price_list_rate - price, amt_precision)
	return result


def has_cascading_discount(item):
	return any(flt(item.get(f)) for f in DISCOUNT_FIELDS)


def recalculate_cascading_discount(doc, method=None):
	"""Server-side recompute for Sales Invoice and Sales Order items.

	Runs on every save (before_validate, see hooks.py) so saves that skip the
	browser (REST, Data Import) still get the cascaded rate. The four discount
	fields are what the user typed and are never rewritten; only rate and the
	combined Discount (%) / Discount Amount follow from them.

	A row without any of the four is left alone: its rate, Discount (%) and
	Discount Amount were set by the user or by ERPNext and are already
	consistent, and recomputing them from empty steps would reset the discount
	to 0.
	"""
	for item in doc.get("items", []):
		if not item.get("price_list_rate") or not has_cascading_discount(item):
			continue
		result = calculate_cascading_discount(
			price_list_rate=item.get("price_list_rate"),
			discount1_percentage=item.get("custom_discount1_percentage"),
			discount1_amount=item.get("custom_discount1_amount"),
			discount2_percentage=item.get("custom_discount2_percentage"),
			discount2_amount=item.get("custom_discount2_amount"),
			rate_precision=item.precision("rate"),
			pct_precision=item.precision("discount_percentage"),
			amt_precision=item.precision("discount_amount"),
		)
		item.rate = result["rate"]
		item.discount_percentage = result["discount_percentage"]
		item.discount_amount = result["discount_amount"]
