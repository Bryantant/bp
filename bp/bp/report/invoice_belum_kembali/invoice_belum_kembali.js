// Invoice Belum Kembali (HT-42). From Date starts at BP Settings > Invoice
// Kembali Start Date when that is set.
frappe.query_reports["Invoice Belum Kembali"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today() },
		{ fieldname: "sales_person", label: __("Salesman"), fieldtype: "Link", options: "Sales Person" },
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "Belum kembali\nSudah kembali\nSemua",
			default: "Belum kembali",
		},
	],

	onload(report) {
		if (report.get_filter_value("from_date")) return;
		frappe
			.call("bp.bp.report.invoice_belum_kembali.invoice_belum_kembali.default_from_date")
			.then((r) => r.message && report.set_filter_value("from_date", r.message));
	},
};
