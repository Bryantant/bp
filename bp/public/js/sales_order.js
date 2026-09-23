// Two-tier cascading discount (Discount 1 = supplier/claimable, Discount 2 =
// internal policy). Discount 2 compounds on the price *after* Discount 1, not
// on price_list_rate directly. See bp.overrides.sales_order.
// recalculate_cascading_discount for the authoritative server-side recompute
// that runs on every save regardless of what happens here.
frappe.ui.form.on("Sales Order Item", {
	price_list_rate: function (frm, cdt, cdn) {
		bp.sales_order.recalculate_from_base(frm, cdt, cdn);
	},
	custom_discount1_percentage: function (frm, cdt, cdn) {
		var item = frappe.get_doc(cdt, cdn);
		var r1 = bp.discounts.fromDiscount1Percentage(
			item.price_list_rate,
			item.custom_discount1_percentage,
			item,
		);
		item.custom_discount1_amount = r1.d1_amount;
		bp.sales_order.apply_discount2(frm, cdt, cdn, r1.after_disc1);
	},
	custom_discount1_amount: function (frm, cdt, cdn) {
		var item = frappe.get_doc(cdt, cdn);
		var r1 = bp.discounts.fromDiscount1Amount(
			item.price_list_rate,
			item.custom_discount1_amount,
			item,
		);
		item.custom_discount1_percentage = r1.d1_percentage;
		bp.sales_order.apply_discount2(frm, cdt, cdn, r1.after_disc1);
	},
	custom_discount2_percentage: function (frm, cdt, cdn) {
		var item = frappe.get_doc(cdt, cdn);
		var after_disc1 = flt(item.price_list_rate) - flt(item.custom_discount1_amount);
		var r2 = bp.discounts.fromDiscount2Percentage(
			after_disc1,
			item.custom_discount2_percentage,
			item,
		);
		item.custom_discount2_amount = r2.d2_amount;
		bp.sales_order.set_final_rate(frm, cdt, cdn, r2.final_rate);
	},
	custom_discount2_amount: function (frm, cdt, cdn) {
		var item = frappe.get_doc(cdt, cdn);
		var after_disc1 = flt(item.price_list_rate) - flt(item.custom_discount1_amount);
		var r2 = bp.discounts.fromDiscount2Amount(after_disc1, item.custom_discount2_amount, item);
		item.custom_discount2_percentage = r2.d2_percentage;
		bp.sales_order.set_final_rate(frm, cdt, cdn, r2.final_rate);
	},
});

frappe.provide("bp.sales_order");

bp.sales_order = {
	apply_discount2: function (frm, cdt, cdn, after_disc1) {
		var item = frappe.get_doc(cdt, cdn);
		var r2 = bp.discounts.fromDiscount2Percentage(
			after_disc1,
			item.custom_discount2_percentage,
			item,
		);
		item.custom_discount2_amount = r2.d2_amount;
		bp.sales_order.set_final_rate(frm, cdt, cdn, r2.final_rate);
	},

	recalculate_from_base: function (frm, cdt, cdn) {
		var item = frappe.get_doc(cdt, cdn);
		var r = bp.discounts.recalculateFromBase(item.price_list_rate, item);
		item.custom_discount1_amount = r.d1_amount;
		item.custom_discount2_amount = r.d2_amount;
		bp.sales_order.set_final_rate(frm, cdt, cdn, r.final_rate);
	},

	set_final_rate: function (frm, cdt, cdn, final_rate) {
		frappe.model.set_value(cdt, cdn, "rate", final_rate);
		frm.refresh_field("items");
	},
};
