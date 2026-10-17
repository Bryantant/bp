frappe.ui.form.on("Sales Invoice", {
	refresh: function (frm) {
		frm.set_query("bp_sales_person", function () {
			return { filters: { is_group: 0 } };
		});
		bp.sales_invoice.sync_from_table(frm);
		bp.sales_invoice.render_print_controls(frm);
		bp.sales_invoice.add_send_to_warehouse(frm);
	},

	bp_sales_person: function (frm) {
		bp.sales_invoice.push_to_table(frm);
	},
});

// Four-step cascading discount (Discount 1 %, Discount 1 Amount, Discount 2 %,
// Discount 2 Amount), see bp.discounts in discount_utils.bundle.js. The
// authoritative recompute runs on every save in
// bp.overrides.sales_invoice.recalculate_cascading_discount.
bp.discounts.bindItemGrid("Sales Invoice Item");

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

	// Print status indicator and Print Log link. Printing from the invoice is free;
	// print-once lives in the warehouse queue (Send to Warehouse below).
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
	},

	// HT-171: queue the invoice for the warehouse admin, who may print each send
	// once (bp.warehouse_print). AR picks the format; every send is logged.
	add_send_to_warehouse: function (frm) {
		// BP Warehouse Print is "User Cannot Create" (rows only come from this
		// button), so Frappe lists it under in_create instead of can_create.
		var user = frappe.boot.user;
		var can_send =
			user.can_create.includes("BP Warehouse Print") ||
			user.in_create.includes("BP Warehouse Print");
		if (frm.doc.docstatus !== 1 || !can_send) return;

		frm.add_custom_button(
			__("Send to Warehouse"),
			function () {
				frappe
					.xcall("bp.warehouse_print.send_history", { sales_invoice: frm.doc.name })
					.then(function (r) {
						bp.sales_invoice.send_to_warehouse_dialog(frm, r);
					});
			},
			__("Print")
		);
	},

	send_to_warehouse_dialog: function (frm, r) {
		if (!r.formats.length) {
			frappe.msgprint(__("No Warehouse Print Formats set in BP Settings."));
			return;
		}
		var describe = function (format) {
			var h = r.history[format] || {};
			if (!h.sent) return '<p class="text-muted small">' + __("Not sent yet") + "</p>";
			var text = __("Sent {0} time(s), printed {1} time(s)", [h.sent, h.printed]);
			if (h.pending) text += ", " + __("{0} waiting to be printed", [h.pending]);
			if (h.last_printed_by) text += ", " + __("last printed by {0}", [h.last_printed_by]);
			return '<p class="text-muted small">' + frappe.utils.escape_html(text) + "</p>";
		};
		var d = new frappe.ui.Dialog({
			title: __("Send to Warehouse"),
			fields: [
				{
					fieldname: "print_format",
					fieldtype: "Select",
					label: __("Print Format"),
					options: r.formats,
					default: r.formats[0],
					reqd: 1,
					onchange: function () {
						d.fields_dict.history.$wrapper.html(describe(d.get_value("print_format")));
					},
				},
				{ fieldname: "history", fieldtype: "HTML", options: describe(r.formats[0]) },
			],
			primary_action_label: __("Send"),
			primary_action: function (values) {
				frappe
					.xcall("bp.warehouse_print.send_to_warehouse", {
						sales_invoice: frm.doc.name,
						print_format: values.print_format,
					})
					.then(function (name) {
						d.hide();
						frappe.show_alert({
							message: __("Sent to warehouse as {0} ({1})", [
								name,
								values.print_format,
							]),
							indicator: "green",
						});
					});
			},
		});
		d.show();
	},
};
