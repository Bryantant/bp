# Copyright (c) 2026, Hicom System and contributors
# For license information, please see license.txt

"""Four-step cascading discount recompute for Sales Order Item.

Discount 1 %, Discount 1 Amount, Discount 2 % and Discount 2 Amount are four
separate steps, each applied to the price left by the one before it (see
bp.utils.cascading_discount). public/js/sales_order.js keeps this in sync live
in the browser, but this server-side recompute is the authority: it re-derives
rate/discount_percentage/discount_amount from the four fields on every save
(rows without any of them are left alone), so REST/data-importer saves that
skip the browser still end up with a correct rate.

Wired via "before_validate" (not "validate") in hooks.py so this runs before
ERPNext's own SalesOrder.validate() -> calculate_taxes_and_totals(), which
must see the final rate to compute amount/net_amount/totals correctly.
"""

from bp.utils.cascading_discount import recalculate_cascading_discount as _recalculate_cascading_discount


def recalculate_cascading_discount(doc, method=None):
	_recalculate_cascading_discount(doc)
