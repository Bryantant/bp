# Copyright (c) 2026, Hicom System and contributors
# For license information, please see license.txt

"""Two-tier cascading discount recompute for Sales Order Item.

Discount 1 (supplier-side/claimable) is applied to price_list_rate; Discount 2
(internal company-policy) compounds on top of the *post-Discount-1* rate, not
price_list_rate directly -- 10% + 5% is 14.5%, not 15%. public/js/sales_order.js
keeps this in sync live in the browser, but this server-side recompute is the
authority: it re-derives rate/discount_percentage/discount_amount from
custom_discount1_percentage/custom_discount1_amount/custom_discount2_percentage/
custom_discount2_amount unconditionally on every save, so REST/data-importer
saves that skip the browser still end up with a correct rate.

Wired via "before_validate" (not "validate") in hooks.py so this runs before
ERPNext's own SalesOrder.validate() -> calculate_taxes_and_totals(), which
must see the final rate to compute amount/net_amount/totals correctly.
"""

from bp.utils.cascading_discount import calculate_cascading_discount


def recalculate_cascading_discount(doc, method=None):
	for item in doc.get("items", []):
		if not item.get("price_list_rate"):
			# No list price to cascade from (item has no Item Price / no price list
			# match) -- leave whatever rate was entered untouched instead of
			# zeroing it out.
			continue
		result = calculate_cascading_discount(
			price_list_rate=item.get("price_list_rate"),
			discount1_percentage=item.get("custom_discount1_percentage"),
			discount1_amount=item.get("custom_discount1_amount"),
			discount2_percentage=item.get("custom_discount2_percentage"),
			discount2_amount=item.get("custom_discount2_amount"),
			rate_precision=item.precision("rate"),
			pct_precision=item.precision("custom_discount1_percentage"),
			amt_precision=item.precision("custom_discount1_amount"),
		)
		item.custom_discount1_percentage = result["discount1_percentage"]
		item.custom_discount1_amount = result["discount1_amount"]
		item.custom_discount2_percentage = result["discount2_percentage"]
		item.custom_discount2_amount = result["discount2_amount"]
		item.rate = result["rate"]
		item.discount_percentage = result["discount_percentage"]
		item.discount_amount = result["discount_amount"]
