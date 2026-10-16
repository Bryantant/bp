frappe.listview_settings["BP Warehouse Print"] = {
	add_fields: ["status"],
	filters: [["status", "=", "Pending"]],
	hide_name_column: false,

	get_indicator: function (doc) {
		return doc.status === "Printed"
			? [__("Printed"), "green", "status,=,Printed"]
			: [__("Pending"), "orange", "status,=,Pending"];
	},

	button: {
		show: function (doc) {
			return (
				doc.status === "Pending" &&
				frappe.user.has_role(["BP Admin Gudang", "System Manager"])
			);
		},
		get_label: function () {
			return __("Print");
		},
		get_description: function (doc) {
			return __("Print {0} ({1})", [doc.sales_invoice, doc.print_format]);
		},
		action: function (doc) {
			frappe.require("/assets/bp/js/warehouse_print.js", function () {
				bp.warehouse_print.print(doc.name, function () {
					cur_list && cur_list.refresh();
				});
			});
		},
	},
};
