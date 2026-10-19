// Invoice Kembali (HT-42): a USB scanner types the barcode into Scan Invoice and
// presses Enter; the camera button of the Barcode field sets the value the same
// way. Each scan adds one row, then the field is cleared for the next scan.
// Pattern from erpnext/public/js/utils/barcode_scanner.js (clear, call, alert,
// sound), not subclassed: that class only adds item rows.
frappe.ui.form.on("Invoice Kembali", {
	setup(frm) {
		frm.set_query("sales_invoice", "invoices", () => ({
			filters: { docstatus: 1, is_return: 0, bp_invoice_kembali: 0, company: frm.doc.company },
		}));
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			setTimeout(() => frm.fields_dict.scan_invoice?.$input?.focus(), 300);
		}
	},

	scan_invoice(frm) {
		const value = (frm.doc.scan_invoice || "").trim();
		if (!value) return;
		frm.set_value("scan_invoice", "");

		frappe
			.call({
				method: "bp.bp.doctype.invoice_kembali.invoice_kembali.resolve_invoice",
				args: { value, company: frm.doc.company, current: frm.is_new() ? null : frm.doc.name },
			})
			.then((r) => {
				const data = r.message || {};
				if (data.error) return fail(data.error);
				if ((frm.doc.invoices || []).some((row) => row.sales_invoice === data.sales_invoice)) {
					return fail(__("{0} is already in this list.", [data.sales_invoice]));
				}
				const row = frm.add_child("invoices", data);
				frm.refresh_field("invoices");
				frm.set_value("total_invoices", frm.doc.invoices.length);
				frappe.show_alert({ message: __("{0} added", [row.sales_invoice]), indicator: "green" }, 3);
				frappe.utils.play_sound("submit");
			})
			.always(() => frm.fields_dict.scan_invoice?.$input?.focus());

		function fail(message) {
			frappe.show_alert({ message, indicator: "red" }, 6);
			frappe.utils.play_sound("error");
		}
	},
});

frappe.ui.form.on("Invoice Kembali Item", {
	invoices_remove(frm) {
		frm.set_value("total_invoices", (frm.doc.invoices || []).length);
	},
});
