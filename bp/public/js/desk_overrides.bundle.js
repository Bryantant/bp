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
