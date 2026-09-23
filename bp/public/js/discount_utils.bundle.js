frappe.provide("bp.discounts");

// Pure cascading-discount math shared by the Sales Invoice Item and Sales
// Order Item grid handlers (public/js/sales_invoice.js, public/js/sales_order.js).
// Mirrors bp.utils.cascading_discount.calculate_cascading_discount on the
// server (bp/overrides/sales_invoice.py, bp/overrides/sales_order.py), which
// is the authoritative recompute on save -- this is for live UX only.
//
// A dedicated bundle (not desk_overrides.bundle.js) because this is business
// calculation logic, not desk-chrome cosmetics -- keeping bundles single-
// purpose. Loaded globally via app_include_js, so it's available before any
// doctype_js (which loads per-route) runs.
//
// Unlike the server-side function (which infers "which field drives" via a
// percentage-preferred/amount-fallback heuristic, since it can't know which
// field the user last touched), each function here is direction-specific:
// the grid handler that calls it already knows exactly which field the user
// just edited, so it always derives the *other* side of that same pair.
bp.discounts = {
	// price_list_rate, d1_pct -> { d1_percentage, d1_amount, after_disc1 }
	fromDiscount1Percentage: function (price_list_rate, d1_pct, item) {
		price_list_rate = flt(price_list_rate);
		if (price_list_rate <= 0) {
			return { d1_percentage: 0, d1_amount: 0, after_disc1: 0 };
		}
		var after_disc1 = flt(price_list_rate * (1 - flt(d1_pct) / 100), precision("rate", item));
		var d1_amount = flt(
			price_list_rate - after_disc1,
			precision("custom_discount1_amount", item),
		);
		return { d1_percentage: flt(d1_pct), d1_amount: d1_amount, after_disc1: after_disc1 };
	},

	// price_list_rate, d1_amount -> { d1_percentage, d1_amount, after_disc1 }
	fromDiscount1Amount: function (price_list_rate, d1_amount, item) {
		price_list_rate = flt(price_list_rate);
		if (price_list_rate <= 0) {
			return { d1_percentage: 0, d1_amount: 0, after_disc1: 0 };
		}
		var d1_pct = flt(
			(flt(d1_amount) / price_list_rate) * 100,
			precision("custom_discount1_percentage", item),
		);
		var after_disc1 = flt(price_list_rate - flt(d1_amount), precision("rate", item));
		return { d1_percentage: d1_pct, d1_amount: flt(d1_amount), after_disc1: after_disc1 };
	},

	// after_disc1, d2_pct -> { d2_percentage, d2_amount, final_rate }
	fromDiscount2Percentage: function (after_disc1, d2_pct, item) {
		after_disc1 = flt(after_disc1);
		if (after_disc1 <= 0) {
			return { d2_percentage: 0, d2_amount: 0, final_rate: 0 };
		}
		var final_rate = flt(after_disc1 * (1 - flt(d2_pct) / 100), precision("rate", item));
		var d2_amount = flt(after_disc1 - final_rate, precision("custom_discount2_amount", item));
		return { d2_percentage: flt(d2_pct), d2_amount: d2_amount, final_rate: final_rate };
	},

	// after_disc1, d2_amount -> { d2_percentage, d2_amount, final_rate }
	fromDiscount2Amount: function (after_disc1, d2_amount, item) {
		after_disc1 = flt(after_disc1);
		if (after_disc1 <= 0) {
			return { d2_percentage: 0, d2_amount: 0, final_rate: 0 };
		}
		var d2_pct = flt(
			(flt(d2_amount) / after_disc1) * 100,
			precision("custom_discount2_percentage", item),
		);
		var final_rate = flt(after_disc1 - flt(d2_amount), precision("rate", item));
		return { d2_percentage: d2_pct, d2_amount: flt(d2_amount), final_rate: final_rate };
	},

	// Used when price_list_rate itself changes: percentage is master on a base
	// change (matches core's own treatment of discount_percentage when
	// price_list_rate changes), both tiers' amounts get recomputed from it.
	recalculateFromBase: function (price_list_rate, item) {
		var r1 = bp.discounts.fromDiscount1Percentage(
			price_list_rate,
			item.custom_discount1_percentage,
			item,
		);
		var r2 = bp.discounts.fromDiscount2Percentage(
			r1.after_disc1,
			item.custom_discount2_percentage,
			item,
		);
		return { d1_amount: r1.d1_amount, d2_amount: r2.d2_amount, final_rate: r2.final_rate };
	},
};
