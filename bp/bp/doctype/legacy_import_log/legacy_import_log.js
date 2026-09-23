// Copyright (c) 2026, Hicom System and contributors
// For license information, please see license.txt

frappe.ui.form.on("Legacy Import Log", {
	refresh(frm) {
		const base = "bp.bp.doctype.legacy_import_log.legacy_import_log.";
		const act = (method, confirm_msg) => {
			frappe.confirm(confirm_msg, () =>
				frappe.call({
					method: base + method,
					args: { name: frm.doc.name },
					freeze: true,
					callback: () => frm.reload_doc(),
				})
			);
		};

		if (frm.doc.status === "Changed in Legacy") {
			frm.add_custom_button(__("Re-sync from Old System"), () =>
				act(
					"resync",
					__("Cancel {0} and re-create it from the old system's current data?", [
						frm.doc.erp_name,
					])
				)
			);
		}
		if (["Changed in Legacy", "Cancelled in Legacy"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Cancel in ERP"), () =>
				act("cancel_in_erp", __("Cancel {0} in ERP?", [frm.doc.erp_name]))
			);
			frm.add_custom_button(__("Ignore"), () =>
				act("ignore", __("Keep {0} as it is and stop flagging it?", [frm.doc.erp_name]))
			);
		}
	},
});
