frappe.ui.form.on("Import ND Invoice", {
	refresh(frm) {
		frm.set_df_property("paste_button", "hidden", frm.doc.docstatus !== 0);
	},

	// Rows come from Excel by copy-paste (Bry 2026-10-23): read the clipboard
	// directly; when the browser refuses (no permission, older Safari/Firefox),
	// open a box where the user pastes with Ctrl/Cmd+V.
	paste_button(frm) {
		bp.import_sales_invoice.read_clipboard(frm);
	},

	// Changing the header default overwrites it on every existing row, not just
	// blank ones (same as Source Warehouse on Sales Invoice).
	default_salesman(frm) {
		bp.import_sales_invoice.autofill_rows(frm, "salesman", frm.doc.default_salesman);
	},
});

frappe.ui.form.on("Import ND Invoice Item", {
	// Fires when a row is added via the grid's own "Add Row" button (not for
	// frm.add_child calls from our own code, e.g. load_rows below --
	// that path applies defaults itself before adding the row). Frappe scopes
	// "<fieldname>_add" handlers by the CHILD doctype, not the parent, since
	// script_manager.trigger() is called with the child row's own doctype.
	rows_add(frm, cdt, cdn) {
		bp.import_sales_invoice.apply_defaults_to_row(frm, locals[cdt][cdn]);
	},
});

frappe.provide("bp.import_sales_invoice");

bp.import_sales_invoice = {
	autofill_rows: function (frm, fieldname, value) {
		if (!value || !frm.doc.rows || !frm.doc.rows.length) return;
		frm.doc.rows.forEach((row) =>
			frappe.model.set_value(row.doctype, row.name, fieldname, value)
		);
	},

	apply_defaults_to_row: function (frm, row) {
		if (frm.doc.default_salesman && !row.salesman) {
			frappe.model.set_value(row.doctype, row.name, "salesman", frm.doc.default_salesman);
		}
	},

	read_clipboard: function (frm) {
		const fallback = () => bp.import_sales_invoice.paste_dialog(frm);
		if (!navigator.clipboard || !navigator.clipboard.readText) return fallback();
		navigator.clipboard
			.readText()
			.then(
				(text) =>
					text && text.trim()
						? bp.import_sales_invoice.load_rows(frm, text)
						: fallback(),
				fallback
			);
	},

	paste_dialog: function (frm) {
		const d = new frappe.ui.Dialog({
			title: __("Paste dari Excel"),
			fields: [
				{
					fieldname: "pasted",
					fieldtype: "Long Text",
					label: __("Data"),
					description: __(
						"Copy rows in Excel including the header row (Invoice Number, Invoice Date, CustomerID, Net Amount), then paste here with Ctrl+V or Cmd+V."
					),
				},
			],
			primary_action_label: __("Add to Table"),
			primary_action(values) {
				if (!values.pasted || !values.pasted.trim()) return;
				d.hide();
				bp.import_sales_invoice.load_rows(frm, values.pasted);
			},
		});
		d.show();
		setTimeout(
			() => d.fields_dict.pasted.$input && d.fields_dict.pasted.$input.trigger("focus"),
			200
		);
	},

	// Parse the pasted text server-side and add its rows to the grid, skipping
	// ND numbers already there.
	load_rows: function (frm, text) {
		frappe.call({
			method: "bp.bp.doctype.import_nd_invoice.import_nd_invoice.parse_pasted",
			args: { text: text },
			freeze: true,
			freeze_message: __("Reading rows..."),
			callback: function (r) {
				if (r.exc) return;
				var msg = r.message || {};

				// Drop the blank placeholder row Frappe auto-adds to a new/empty
				// mandatory Table field -- otherwise it sits mixed in with real
				// data and blocks Save/Submit with "ND Invoice No is mandatory".
				frm.doc.rows = (frm.doc.rows || []).filter(
					(row) =>
						row.nd_invoice_no || row.cust_code_nd || row.invoice_date || row.amount
				);

				var existing = new Set(frm.doc.rows.map((row) => row.nd_invoice_no));
				var added = 0;
				(msg.rows || []).forEach(function (row) {
					if (existing.has(row.nd_invoice_no)) return;
					if (frm.doc.default_salesman) row.salesman = frm.doc.default_salesman;
					frm.add_child("rows", row);
					existing.add(row.nd_invoice_no);
					added++;
				});
				frm.refresh_field("rows");
				frm.dirty();
				frappe.show_alert({
					message: __("Added {0} row(s). Skipped {1} duplicate(s).", [
						added,
						(msg.rows || []).length - added,
					]),
					indicator: added ? "green" : "orange",
				});
				if ((msg.errors || []).length) {
					frappe.msgprint({
						title: __("Rows not added"),
						indicator: "orange",
						message: msg.errors.map((e) => frappe.utils.escape_html(e)).join("<br>"),
					});
				}
			},
		});
	},
};
