frappe.ui.form.on("Stock Entry", {
	onload: function (frm) {
		bp.stock_entry.lock_type_for_sales(frm);
	},
	refresh: function (frm) {
		bp.stock_entry.inject_warehouse_col_css();
		bp.stock_entry.apply_warehouse_column_visibility(frm, frm.doc.purpose);
		frm.toggle_enable("stock_entry_type", !bp.stock_entry.is_sales_only());
	},
	stock_entry_type: function (frm) {
		if (!frm.doc.stock_entry_type) {
			bp.stock_entry.apply_warehouse_column_visibility(frm, null);
			return;
		}
		frappe.db.get_value("Stock Entry Type", frm.doc.stock_entry_type, "purpose", function (r) {
			bp.stock_entry.apply_warehouse_column_visibility(frm, r && r.purpose);
		});
	},
});

frappe.provide("bp.stock_entry");

bp.stock_entry = {
	// Mirrors bp/overrides/stock_entry.py: sales admins may only relocate stock (HT-8).
	SALES_ROLES: ["Sales User", "BP Sales User"],

	FULL_ACCESS_ROLES: [
		"Stock User",
		"Stock Manager",
		"Manufacturing User",
		"Manufacturing Manager",
		"Accounts User",
		"Accounts Manager",
		"System Manager",
	],

	is_sales_only: function () {
		return (
			bp.stock_entry.SALES_ROLES.some((role) => frappe.user.has_role(role)) &&
			!bp.stock_entry.FULL_ACCESS_ROLES.some((role) => frappe.user.has_role(role))
		);
	},

	lock_type_for_sales: function (frm) {
		if (!frm.is_new() || !bp.stock_entry.is_sales_only()) return;
		frappe
			.xcall("bp.overrides.stock_entry.get_sales_entry_type")
			.then((entry_type) => entry_type && frm.set_value("stock_entry_type", entry_type));
	},

	inject_warehouse_col_css: function () {
		if (document.getElementById("bp-warehouse-col-style")) return;
		$('<style id="bp-warehouse-col-style">')
			.text(
				'.bp-hide-s-warehouse [data-fieldname="s_warehouse"] { display: none !important; } ' +
					'.bp-hide-t-warehouse [data-fieldname="t_warehouse"] { display: none !important; }'
			)
			.appendTo("head");
	},

	apply_warehouse_column_visibility: function (frm, purpose) {
		var $wrapper = $(frm.fields_dict.items.grid.wrapper);
		$wrapper.toggleClass("bp-hide-s-warehouse", purpose === "Material Receipt");
		$wrapper.toggleClass("bp-hide-t-warehouse", purpose === "Material Issue");
	},
};
