frappe.provide("bp.discounts");

// Four-step cascading discount shared by the Sales Invoice Item and Sales
// Order Item grids (public/js/sales_invoice.js, public/js/sales_order.js).
// Mirrors bp.utils.cascading_discount.calculate_cascading_discount on the
// server, which is the authoritative recompute on save -- this is for live
// UX only.
//
//   Price List Rate -> Discount 1 % -> Discount 1 Amount
//                   -> Discount 2 % -> Discount 2 Amount = Rate
//
// Each field is its own step on the price left by the step before it. A
// percentage and the amount next to it are not two ways of typing the same
// discount, so neither is ever derived from the other.
//
// A dedicated bundle (not desk_overrides.bundle.js) because this is business
// calculation logic, not desk-chrome cosmetics -- keeping bundles single-
// purpose. Loaded globally via app_include_js, so it's available before any
// doctype_js (which loads per-route) runs.
bp.discounts = {
	FIELDS: [
		"custom_discount1_percentage",
		"custom_discount1_amount",
		"custom_discount2_percentage",
		"custom_discount2_amount",
	],

	// The rate left after the four steps; never below 0.
	cascade: function (item) {
		var rp = precision("rate", item);
		var price = flt(item.price_list_rate);
		if (price <= 0) return 0;
		price = flt(price * (1 - flt(item.custom_discount1_percentage) / 100), rp);
		price = Math.max(flt(price - flt(item.custom_discount1_amount), rp), 0);
		price = flt(price * (1 - flt(item.custom_discount2_percentage) / 100), rp);
		price = Math.max(flt(price - flt(item.custom_discount2_amount), rp), 0);
		return price;
	},

	hasCascade: function (item) {
		return bp.discounts.FIELDS.some(function (f) {
			return !!flt(item[f]);
		});
	},

	apply: function (frm, cdt, cdn) {
		var item = frappe.get_doc(cdt, cdn);
		if (!flt(item.price_list_rate)) return;
		frappe.model.set_value(cdt, cdn, "rate", bp.discounts.cascade(item));
		frm.refresh_field("items");
	},

	// The user typed Rate, Discount (%) or Discount Amount by hand on a row that
	// also has Discount 1/2. The last thing typed wins: clear Discount 1/2 so the
	// save (which recomputes from them) doesn't put the old rate back. Deferred
	// because ERPNext's own handlers set the new rate after this trigger fires.
	// Our own cascade writes exactly cascade(item), so it never clears itself.
	releaseIfOverridden: function (frm, cdt, cdn) {
		setTimeout(function () {
			var item = locals[cdt] && locals[cdt][cdn];
			if (!item || !flt(item.price_list_rate) || !bp.discounts.hasCascade(item)) return;
			if (Math.abs(flt(item.rate) - bp.discounts.cascade(item)) < 0.01) return;
			bp.discounts.FIELDS.forEach(function (f) {
				item[f] = 0;
			});
			frm.refresh_field("items");
		}, 0);
	},

	// Wire the grid handlers for one item doctype.
	bindItemGrid: function (item_doctype) {
		var handlers = {
			price_list_rate: function (frm, cdt, cdn) {
				// Without Discount 1/2 the row runs on ERPNext's own Discount (%); let
				// core recompute the rate from it instead of resetting it to the list price.
				if (!bp.discounts.hasCascade(frappe.get_doc(cdt, cdn))) return;
				// Deferred: ERPNext's price_list_rate handler runs after this one and
				// writes its own rate; ours has to land last.
				setTimeout(function () {
					bp.discounts.apply(frm, cdt, cdn);
				}, 0);
			},
		};
		["rate", "discount_percentage", "discount_amount"].forEach(function (f) {
			handlers[f] = function (frm, cdt, cdn) {
				bp.discounts.releaseIfOverridden(frm, cdt, cdn);
			};
		});
		bp.discounts.FIELDS.forEach(function (f) {
			handlers[f] = function (frm, cdt, cdn) {
				bp.discounts.apply(frm, cdt, cdn);
			};
		});
		frappe.ui.form.on(item_doctype, handlers);
	},
};
