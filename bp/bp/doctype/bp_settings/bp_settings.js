// Copyright (c) 2026, Hicom System and contributors
// For license information, please see license.txt

frappe.ui.form.on("BP Settings", {
	test_legacy_connection(frm) {
		if (frm.is_dirty()) {
			frappe.msgprint(__("Save the settings first, then test the connection."));
			return;
		}
		frappe.call({
			method: "bp.utils.legacy_db.test_legacy_connection",
			freeze: true,
			freeze_message: __("Connecting to the old system..."),
			callback(r) {
				if (!r.message) return;
				const m = r.message;
				frappe.msgprint({
					title: __("Connection OK"),
					indicator: "green",
					message: __(
						"Server version {0}. Latest delivery order date: {1}. Latest receiving date: {2}.",
						[m.version, m.last_do_date || "-", m.last_receiving_date || "-"]
					),
				});
			},
		});
	},
});
