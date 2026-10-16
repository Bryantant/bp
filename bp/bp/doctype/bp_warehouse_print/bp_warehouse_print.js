frappe.ui.form.on("BP Warehouse Print", {
	refresh: function (frm) {
		frm.disable_save();
		var reload = function () {
			frm.reload_doc();
		};

		if (
			frm.doc.status === "Pending" &&
			frappe.user.has_role(["BP Admin Gudang", "System Manager"])
		) {
			frm.add_custom_button(__("Print"), function () {
				frappe.require("/assets/bp/js/warehouse_print.js", function () {
					bp.warehouse_print.print(frm.doc.name, reload);
				});
			}).addClass("btn-primary");
		}

		if (frm.doc.status === "Printed") {
			frappe
				.xcall("bp.overrides.sales_invoice.can_reset_print_lock")
				.then(function (allowed) {
					if (!allowed) return;
					frm.add_custom_button(__("Reset Print"), function () {
						frappe.require("/assets/bp/js/warehouse_print.js", function () {
							bp.warehouse_print.reset(frm.doc.name, reload);
						});
					});
				});
		}
	},
});
