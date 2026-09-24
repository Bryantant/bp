frappe.ui.form.on("Sales Invoice", {
	refresh: function (frm) {
		frm.set_query("bp_sales_person", function () {
			return { filters: { is_group: 0 } };
		});
		bp.sales_invoice.sync_from_table(frm);
		bp.sales_invoice.render_print_controls(frm);
	},

	bp_sales_person: function (frm) {
		bp.sales_invoice.push_to_table(frm);
	},
});

// Two-tier cascading discount (Discount 1 = supplier/claimable, Discount 2 =
// internal policy). Discount 2 compounds on the price *after* Discount 1, not
// on price_list_rate directly. See bp.overrides.sales_invoice.
// recalculate_cascading_discount for the authoritative server-side recompute
// that runs on every save regardless of what happens here.
frappe.ui.form.on("Sales Invoice Item", {
	price_list_rate: function (frm, cdt, cdn) {
		bp.sales_invoice.recalculate_from_base(frm, cdt, cdn);
	},
	custom_discount1_percentage: function (frm, cdt, cdn) {
		var item = frappe.get_doc(cdt, cdn);
		var r1 = bp.discounts.fromDiscount1Percentage(
			item.price_list_rate,
			item.custom_discount1_percentage,
			item,
		);
		item.custom_discount1_amount = r1.d1_amount;
		bp.sales_invoice.apply_discount2(frm, cdt, cdn, r1.after_disc1);
	},
	custom_discount1_amount: function (frm, cdt, cdn) {
		var item = frappe.get_doc(cdt, cdn);
		var r1 = bp.discounts.fromDiscount1Amount(
			item.price_list_rate,
			item.custom_discount1_amount,
			item,
		);
		item.custom_discount1_percentage = r1.d1_percentage;
		bp.sales_invoice.apply_discount2(frm, cdt, cdn, r1.after_disc1);
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
		bp.sales_invoice.set_final_rate(frm, cdt, cdn, r2.final_rate);
	},
	custom_discount2_amount: function (frm, cdt, cdn) {
		var item = frappe.get_doc(cdt, cdn);
		var after_disc1 = flt(item.price_list_rate) - flt(item.custom_discount1_amount);
		var r2 = bp.discounts.fromDiscount2Amount(after_disc1, item.custom_discount2_amount, item);
		item.custom_discount2_percentage = r2.d2_percentage;
		bp.sales_invoice.set_final_rate(frm, cdt, cdn, r2.final_rate);
	},
});

frappe.provide("bp.sales_invoice");

bp.sales_invoice = {
	// On load: read the first row of sales_team → populate the dropdown.
	// Handles saved/amended docs so the dropdown always reflects stored data.
	sync_from_table: function (frm) {
		var first = frm.doc.sales_team && frm.doc.sales_team[0];
		if (first && first.sales_person && frm.doc.bp_sales_person !== first.sales_person) {
			frm.set_value("bp_sales_person", first.sales_person);
		}
	},

	// When the dropdown changes: replace sales_team with a single row at 100%.
	push_to_table: function (frm) {
		var person = frm.doc.bp_sales_person;
		frm.clear_table("sales_team");
		if (person) {
			var row = frm.add_child("sales_team");
			row.sales_person = person;
			row.allocated_percentage = 100;
		}
		frm.refresh_field("sales_team");
	},

	// Print-once control: status indicator, Print Log link, manager-only reset.
	render_print_controls: function (frm) {
		if (frm.doc.__islocal || frm.doc.docstatus !== 1) return;

		if (frm.doc.bp_print_status === "Printed") {
			frm.dashboard.add_indicator(
				__("Printed by {0}", [frm.doc.bp_last_printed_by || "-"]),
				"green"
			);
		} else {
			frm.dashboard.add_indicator(__("Not Printed"), "orange");
		}

		frm.add_custom_button(
			__("Print Log"),
			function () {
				frappe.set_route("List", "BP Invoice Print Log", { sales_invoice: frm.doc.name });
			},
			__("Print")
		);

		// Reset button visibility is driven by BP Settings → Enforce Print Once and
		// Print Lock Reset Roles. Ask the server (it's the source of truth and
		// enforces on the call too). With the lock switched off there is nothing to reset.
		if (frm.doc.bp_print_status === "Printed") {
			frappe.xcall("bp.overrides.sales_invoice.print_lock_state").then(function (state) {
				if (state.enforced && state.can_reset) {
					bp.sales_invoice.add_reset_button(frm);
				}
			});
		}
	},

	add_reset_button: function (frm) {
		frm.add_custom_button(
			__("Reset Print Lock"),
			function () {
				frappe.prompt(
					[
						{
							fieldname: "reason",
							fieldtype: "Small Text",
							label: __("Reason"),
							reqd: 1,
						},
					],
					function (values) {
						frappe.call({
							method: "bp.overrides.sales_invoice.reset_print_lock",
							args: { sales_invoice: frm.doc.name, reason: values.reason },
							freeze: true,
							freeze_message: __("Resetting print lock..."),
							callback: function (r) {
								if (!r.exc) {
									frappe.show_alert({
										message: __("Print lock reset. Invoice can be printed once more."),
										indicator: "orange",
									});
									frm.reload_doc();
								}
							},
						});
					},
					__("Reset Print Lock"),
					__("Reset")
				);
			},
			__("Print")
		);
	},

	// -- Cascading discount helpers (see the Sales Invoice Item handlers above) --

	apply_discount2: function (frm, cdt, cdn, after_disc1) {
		var item = frappe.get_doc(cdt, cdn);
		var r2 = bp.discounts.fromDiscount2Percentage(
			after_disc1,
			item.custom_discount2_percentage,
			item,
		);
		item.custom_discount2_amount = r2.d2_amount;
		bp.sales_invoice.set_final_rate(frm, cdt, cdn, r2.final_rate);
	},

	recalculate_from_base: function (frm, cdt, cdn) {
		var item = frappe.get_doc(cdt, cdn);
		var r = bp.discounts.recalculateFromBase(item.price_list_rate, item);
		item.custom_discount1_amount = r.d1_amount;
		item.custom_discount2_amount = r.d2_amount;
		bp.sales_invoice.set_final_rate(frm, cdt, cdn, r.final_rate);
	},

	set_final_rate: function (frm, cdt, cdn, final_rate) {
		frappe.model.set_value(cdt, cdn, "rate", final_rate);
		frm.refresh_field("items");
	},
};
