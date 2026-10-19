// Update Stock can only be set while the invoice is new: the name is given on the
// first save from this flag (bp/overrides/update_stock_lock.py enforces it on the
// server). Core sales_invoice.js resets the read_only flag on refresh, and this
// file loads after the core form script, so refresh here runs last.
frappe.provide("bp");

bp.update_stock_lock = function (frm) {
	if (!frm.fields_dict.update_stock) return;
	frm.set_df_property("update_stock", "read_only", frm.is_new() ? 0 : 1);
};

["Sales Invoice", "Purchase Invoice", "POS Invoice"].forEach((doctype) => {
	frappe.ui.form.on(doctype, {
		refresh: bp.update_stock_lock,
		after_save: bp.update_stock_lock,
	});
});
