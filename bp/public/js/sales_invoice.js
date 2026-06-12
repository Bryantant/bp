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

		// Reset button visibility is driven by BP Settings → Print Lock Reset Roles.
		// Ask the server (it's the source of truth and enforces on the call too).
		if (frm.doc.bp_print_status === "Printed") {
			frappe.xcall("bp.overrides.sales_invoice.can_reset_print_lock").then(function (can_reset) {
				if (can_reset) {
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
};
