// Copyright (c) 2026, Hicom System and contributors
// For license information, please see license.txt

frappe.listview_settings["Legacy Import Log"] = {
	get_indicator(doc) {
		const colors = {
			Ready: "blue",
			Created: "green",
			"Already Imported": "gray",
			"Changed in Legacy": "orange",
			"Cancelled in Legacy": "orange",
			Skipped: "gray",
			Error: "red",
			"Re-synced": "green",
			"Cancelled in ERP": "darkgrey",
			Ignored: "gray",
		};
		return [__(doc.status), colors[doc.status] || "gray", "status,=," + doc.status];
	},
};
