// Hide 'Help', 'About' and 'Frappe Support' from the desk dropdown / avatar menu.
// Frappe v16 renders these as `.frappe-menu .dropdown-menu-item` with a
// `.menu-item-title` span. The Help submenu (About, Frappe Support, ...) renders
// as a second `.frappe-menu` that appears on hover, so we match by title text
// across every menu rather than by position.
(function hideMenuItems() {
	var HIDDEN_LABELS = ["Help", "About", "Frappe Support"];

	function removeItems() {
		document.querySelectorAll(".frappe-menu .dropdown-menu-item").forEach(function (item) {
			var title = item.querySelector(".menu-item-title");
			if (title && HIDDEN_LABELS.indexOf(title.textContent.trim()) !== -1) {
				item.style.display = "none";
			}
		});
	}

	// The dropdown/avatar menu is rendered lazily when opened, so watch the DOM
	// rather than running once. (frappe.ready is portal-only — unavailable in desk.)
	removeItems();
	var observer = new MutationObserver(removeItems);
	observer.observe(document.body, { childList: true, subtree: true });
})();

// Query report PDF fails ("Cannot read properties of undefined (reading 'toString')")
// when a filter is hidden: get_filter_values() returns f.value for hidden filters, and
// for a MultiSelectList that is undefined. Hidden happens when the user cannot read the
// filter's doctype (Cost Center, Project) or a filter is toggled off (Supplier Group in
// Accounts Payable). pdf_report() then calls .toString() on it. Drop undefined values;
// JSON.stringify already drops them when the report runs, so results do not change.
// report.bundle.js loads lazily and assigns frappe.views.QueryReport, so patch on assignment.
(function patchQueryReportFilterValues() {
	frappe.provide("frappe.views");

	function patch(cls) {
		if (!cls || cls.prototype.__bp_filter_patch) return;
		var original = cls.prototype.get_filter_values;
		cls.prototype.get_filter_values = function () {
			var values = original.apply(this, arguments);
			Object.keys(values || {}).forEach(function (key) {
				if (values[key] === undefined) delete values[key];
			});
			return values;
		};
		cls.prototype.__bp_filter_patch = true;
	}

	var current = frappe.views.QueryReport;
	patch(current);
	Object.defineProperty(frappe.views, "QueryReport", {
		configurable: true,
		enumerable: true,
		get: function () {
			return current;
		},
		set: function (cls) {
			current = cls;
			patch(cls);
		},
	});
})();
