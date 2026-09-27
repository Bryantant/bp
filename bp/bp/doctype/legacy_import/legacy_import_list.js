// Copyright (c) 2026, Hicom System and contributors
// For license information, please see license.txt

frappe.listview_settings["Legacy Import"] = {
	get_indicator(doc) {
		const colors = {
			Draft: "gray",
			Previewed: "blue",
			Queued: "orange",
			Running: "orange",
			Completed: "green",
			"Completed with Errors": "red",
			Reverted: "gray",
			"Reverted with Errors": "red",
			Failed: "red",
		};
		return [__(doc.status), colors[doc.status] || "gray", "status,=," + doc.status];
	},
};
