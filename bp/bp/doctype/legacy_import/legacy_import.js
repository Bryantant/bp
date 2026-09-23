// Copyright (c) 2026, Hicom System and contributors
// For license information, please see license.txt

const LEGACY_IMPORT_METHOD = "bp.bp.doctype.legacy_import.legacy_import.";

frappe.ui.form.on("Legacy Import", {
	setup(frm) {
		frappe.realtime.on("legacy_import_progress", (data) => {
			if (data.finished) {
				frm.dashboard.hide_progress();
				frm.reload_doc();
				return;
			}
			frm.dashboard.show_progress(
				__("Working"),
				(data.done / data.total) * 100,
				__("{0} of {1} ({2})", [data.done, data.total, data.legacy_no])
			);
		});
	},

	refresh(frm) {
		if (frm.is_new()) return;
		const busy = ["Queued", "Running"].includes(frm.doc.status);

		if (busy) {
			frm.dashboard.set_headline(
				__("Import is {0}. This page updates by itself when it finishes.", [
					frm.doc.status.toLowerCase(),
				])
			);
		} else {
			frm.add_custom_button(__("Preview"), () =>
				frappe.call({
					method: LEGACY_IMPORT_METHOD + "preview",
					args: { name: frm.doc.name },
					freeze: true,
					freeze_message: __("Reading the old system..."),
					callback: () => frm.reload_doc(),
				})
			);
			const label = frm.doc.error_count ? __("Run Again (retry errors)") : __("Run Import");
			frm.add_custom_button(label, () =>
				frappe.confirm(
					__(
						"Create and submit ERP documents for every confirmed old-system document from {0} to {1} that is not in ERP yet?",
						[frappe.format(frm.doc.from_date, { fieldtype: "Date" }), frappe.format(frm.doc.to_date, { fieldtype: "Date" })]
					),
					() =>
						frappe.call({
							method: LEGACY_IMPORT_METHOD + "run_import",
							args: { name: frm.doc.name },
							freeze: true,
							callback: () => frm.reload_doc(),
						})
				)
			).addClass("btn-primary");
		}

		if (!busy && frm.doc.created_count) {
			frm.add_custom_button(__("Revert Batch"), () =>
				frappe.warn(
					__("Cancel {0} document(s) created by this batch?", [frm.doc.created_count]),
					__(
						"Every Sales Invoice and Purchase Invoice this batch created is cancelled in ERP, which reverses its stock and ledger entries. Documents that cannot be cancelled (already paid, stock already used) are left as they are, with the reason on their log row.<br><br>The documents in the old system are not touched, so running this batch again would import them once more."
					),
					() =>
						frappe.call({
							method: LEGACY_IMPORT_METHOD + "revert_import",
							args: { name: frm.doc.name },
							freeze: true,
							callback: () => frm.reload_doc(),
						}),
					__("Cancel Them"),
					true
				)
			);
		}

		const view_log = (status) =
			frappe.set_route("List", "Legacy Import Log", status ? { legacy_import: frm.doc.name, status } : { legacy_import: frm.doc.name });
		frm.add_custom_button(__("All"), () => view_log(), __("View Log"));
		frm.add_custom_button(__("Errors"), () => view_log("Error"), __("View Log"));
		frm.add_custom_button(__("Changed in Old System"), () => view_log("Changed in Legacy"), __("View Log"));
		frm.add_custom_button(__("Cancelled in Old System"), () => view_log("Cancelled in Legacy"), __("View Log"));
	},
});
