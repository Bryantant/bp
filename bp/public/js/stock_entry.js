frappe.ui.form.on("Stock Entry", {
	refresh: function (frm) {
		bp.stock_entry.inject_warehouse_col_css();
		bp.stock_entry.apply_warehouse_column_visibility(frm, frm.doc.purpose);
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
