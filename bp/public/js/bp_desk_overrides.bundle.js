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

// Role permission dialog (User form, click a role name): the server (bp.overrides.user.get_perm_info) sorts the
// rows (most rights first) and has three views, chosen with the buttons above the table: without Select-only
// rows, the standard list, and only the rows that can write (default). Frappe builds the dialog from a fixed
// call, so the view is passed by wrapping frappe.xcall for the length of that one call.
(function permissionViewsInRoleDialog() {
	if (!frappe.RoleEditor || frappe.RoleEditor.prototype.__bp_views_patched) return;
	frappe.RoleEditor.prototype.__bp_views_patched = true;
	var VIEWS = [
		[
			"no_select",
			__("Without Select-only"),
			__("DocTypes where the role only has Select are hidden"),
		],
		[
			"standard",
			__("Standard"),
			__("Standard list, including DocTypes where the role only has Select"),
		],
		[
			"write",
			__("Write / Create"),
			__("Only DocTypes the role can change (Write, Create, Delete, Submit, Cancel, Amend)"),
		],
	];
	var original = frappe.RoleEditor.prototype.show_permissions;
	frappe.RoleEditor.prototype.show_permissions = function (role) {
		var editor = this;
		var view = editor.__bp_view || "write";
		var xcall = frappe.xcall;
		frappe.xcall = function (method, args) {
			if (typeof method === "string" && method.endsWith("user.get_perm_info")) {
				args = Object.assign({}, args, { view: view });
			}
			return xcall.apply(
				frappe,
				[method, args].concat(Array.prototype.slice.call(arguments, 2))
			);
		};
		var done;
		try {
			done = original.call(this, role);
		} finally {
			frappe.xcall = xcall;
		}
		return Promise.resolve(done).then(function () {
			var $body = $(editor.perm_dialog.body);
			$body.find(".bp-perm-views").remove();
			var $bar = $(
				'<div class="bp-perm-views" style="display: flex; align-items: center; gap: var(--margin-md); margin-bottom: var(--margin-md)"></div>'
			);
			var $group = $('<div class="btn-group"></div>');
			VIEWS.forEach(function (v) {
				var $btn = $('<button type="button" class="btn btn-xs"></button>')
					.addClass(v[0] === view ? "btn-primary" : "btn-default")
					.text(v[1]);
				$btn.on("click", function () {
					editor.__bp_view = v[0];
					editor.show_permissions(role);
				});
				$group.append($btn);
			});
			var hint = VIEWS.filter(function (v) {
				return v[0] === view;
			})[0][2];
			$bar.append($group).append($('<span class="text-muted small"></span>').text(hint));
			$body.prepend($bar);
		});
	};
})();

// Cmd/Ctrl+P on the Print page (desk/printing/print/<doctype>/<name>) presses its Print button.
// Without this Chrome prints the whole Desk page (sidebar, settings, small preview) to the default
// printer. Desk has no shortcut for the Print button there (Ctrl+S only reaches forms), so bind one.
// Capture phase, so Chrome's own print dialog never opens. Focus must be outside the preview iframe.
(function printPageShortcut() {
	document.addEventListener(
		"keydown",
		function (e) {
			if (!(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey || e.key.toLowerCase() !== "p") return;
			if (!window.frappe || !frappe.get_route || frappe.get_route()[0] !== "print") return;
			var btn = $(".page-actions .primary-action:visible").first();
			if (!btn.length) return;
			e.preventDefault();
			e.stopPropagation();
			btn.trigger("click");
		},
		true
	);
})();
