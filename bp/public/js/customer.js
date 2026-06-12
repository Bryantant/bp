frappe.ui.form.on("Customer", {
	refresh: function (frm) {
		frm.set_query("bp_sales_person", function () {
			return { filters: { is_group: 0 } };
		});
		bp.customer.sync_from_table(frm);
	},

	bp_sales_person: function (frm) {
		bp.customer.push_to_table(frm);
	},
});

frappe.provide("bp.customer");

bp.customer = {
	sync_from_table: function (frm) {
		var first = frm.doc.sales_team && frm.doc.sales_team[0];
		if (first && first.sales_person && frm.doc.bp_sales_person !== first.sales_person) {
			frm.set_value("bp_sales_person", first.sales_person);
		}
	},

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
};
