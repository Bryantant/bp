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

// Role permission dialog (User form > Roles, click a role name): Frappe lists only DocType
// permissions. Add the reports the role can open below it, from bp.utils.role_reports
// (own report roles, or the Custom Role that replaces them). "Bisa dibuka" also needs
// Report permission on the report's source DocType; without it the report stays closed.
(function addReportsToRolePermissions() {
	if (!frappe.RoleEditor || frappe.RoleEditor.prototype.__bp_reports_patched) return;
	frappe.RoleEditor.prototype.__bp_reports_patched = true;
	var original = frappe.RoleEditor.prototype.show_permissions;
	frappe.RoleEditor.prototype.show_permissions = function (role) {
		var editor = this;
		return Promise.resolve(original.call(this, role)).then(function () {
			return frappe
				.xcall("bp.utils.role_reports.get_role_reports", { role: role })
				.then(function (reports) {
					var $body = $(editor.perm_dialog.body);
					$body.find(".bp-role-reports").remove();
					var is_dark = document.documentElement.getAttribute("data-theme") === "dark";
					var head = is_dark ? "bg-dark text-white" : "bg-light";
					var $box = $(
						'<div class="bp-role-reports" style="margin-top: var(--margin-lg)"></div>'
					);
					$box.append(
						'<h6 class="text-muted" style="margin-bottom: var(--margin-sm)">' +
							__("Report") +
							"</h6>"
					);
					if (!reports.length) {
						$box.append(
							'<div class="text-muted">' +
								__("{0} role is not listed on any report", [__(role)]) +
								"</div>"
						);
					} else {
						var rows = reports
							.map(function (r) {
								var esc = frappe.utils.escape_html;
								var open = r.can_open
									? frappe.utils.icon("check", "xs")
									: '<span class="text-danger">' +
									  __("Needs Report permission on {0}", [
											esc(__(r.ref_doctype || "")),
									  ]) +
									  "</span>";
								return (
									"<tr><td>" +
									esc(__(r.report)) +
									"</td><td>" +
									esc(__(r.module || "")) +
									"</td><td>" +
									esc(__(r.ref_doctype || "")) +
									'</td><td class="text-muted bold">' +
									open +
									"</td></tr>"
								);
							})
							.join("");
						$box.append(
							'<div style="max-height: calc(50vh); overflow-y: auto;"><table class="user-perm"><thead><tr>' +
								'<th class="sticky-top ' +
								head +
								'">' +
								__("Report") +
								"</th>" +
								'<th class="sticky-top ' +
								head +
								'">' +
								__("Module") +
								"</th>" +
								'<th class="sticky-top ' +
								head +
								'">' +
								__("Source Document Type") +
								"</th>" +
								'<th class="sticky-top ' +
								head +
								'">' +
								__("Can Open") +
								"</th>" +
								"</tr></thead><tbody>" +
								rows +
								"</tbody></table></div>"
						);
					}
					$body.append($box);
				})
				.catch(function () {
					// no access to the list (not a User Manager): keep the standard dialog
				});
		});
	};
})();
