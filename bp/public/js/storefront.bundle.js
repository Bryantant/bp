/**
 * Mobile app-shell behaviour: cart/wishlist badges and the guest profile link.
 *
 * Everything here is deliberately CLIENT-side. Website pages are cached by path
 * only (frappe/website/utils.py -> `website_page::<path>`), so rendering any of
 * this on the server would bake one user's state into the HTML that every other
 * visitor receives. Cookies are per-request and immune to that cache.
 *
 * Plain .js on purpose -- not a *.bundle.js. It has no imports, and bp/public is
 * already symlinked into sites/assets, so this needs no `bench build`.
 */
(function () {
	"use strict";

	var CART_SELECTOR = ".bp-cart-count";
	var CART_HEAD_SELECTOR = ".bp-cart-count-head";
	var WISH_SELECTOR = ".bp-wish-count";

	function getCookie(name) {
		if (window.frappe && typeof frappe.get_cookie === "function") {
			return frappe.get_cookie(name);
		}
		var match = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
		return match ? decodeURIComponent(match.pop()) : null;
	}

	function isGuest() {
		var user = getCookie("user_id");
		return !user || user === "Guest";
	}

	function paint(selector, rawCount) {
		var el = document.querySelector(selector);
		if (!el) {
			return;
		}
		var count = parseInt(rawCount, 10) || 0;
		el.textContent = count > 99 ? "99+" : String(count);
		// Toggle, never remove. webshop's set_cart_count does $badge.remove() on
		// its own badge; we must stay in the DOM so later updates can find us.
		el.hidden = !count;
	}

	function refreshBadges() {
		// Read the cookies straight, WITHOUT webshop's guest gate. webshop's own
		// set_cart_count forces 0 for guests, yet its /cart page happily renders a
		// guest's items -- so that gate would hide a real, working cart. The
		// cookies are set server-side per session (guest sessions included), so
		// they are already the correct per-visitor source of truth.
		var cart = getCookie("cart_count");
		paint(CART_SELECTOR, cart);
		paint(CART_HEAD_SELECTOR, cart);
		paint(WISH_SELECTOR, getCookie("wish_count"));
	}

	/**
	 * Home-only greeting. Written here rather than server-side because website
	 * pages are cached per path, so a rendered name would be shown to everyone.
	 */
	function paintGreeting() {
		var el = document.querySelector("[data-bp-greet]");
		if (!el) {
			return;
		}
		var name = getCookie("full_name");
		if (isGuest() || !name) {
			el.textContent = __("Welcome");
			return;
		}
		// Cookies arrive URL-encoded and use "+" for spaces.
		el.textContent = __("Hi") + ", " + decodeURIComponent(name).replace(/\+/g, " ");
	}

	/** Back arrow: use real history when we have it, else fall back to the href. */
	function wireBackButton() {
		var back = document.querySelector("[data-bp-back]");
		if (!back) {
			return;
		}
		back.addEventListener("click", function (event) {
			if (window.history.length > 1) {
				event.preventDefault();
				window.history.back();
			}
		});
	}

	function pointProfileAtLogin() {
		if (!isGuest()) {
			return;
		}
		var tab = document.querySelector('.bp-tab[data-tab="profile"]');
		if (tab) {
			// /me throws a "Not Permitted" wall for guests rather than redirecting.
			tab.setAttribute("href", "/login?redirect-to=%2Fme");
		}
	}

	/**
	 * Keep our badge in step with webshop's cart updates by wrapping its
	 * set_cart_count, which fires on ready, after every update_cart callback,
	 * and from shopping_cart_update.
	 */
	function followWebshopCart() {
		var cart =
			window.webshop && webshop.webshop && webshop.webshop.shopping_cart;
		if (!cart || typeof cart.set_cart_count !== "function") {
			return; // webshop not installed / not on this page -- badges stay static
		}
		var original = cart.set_cart_count;
		cart.set_cart_count = function () {
			var result = original.apply(this, arguments);
			refreshBadges();
			return result;
		};
	}

	function init() {
		refreshBadges();
		paintGreeting();
		pointProfileAtLogin();
		wireBackButton();
		followWebshopCart();
	}

	// frappe.ready defers until the full body is parsed. Required: the shell is
	// injected at the end of <body>, after this script tag executes.
	if (window.frappe && typeof frappe.ready === "function") {
		frappe.ready(init);
	} else {
		document.addEventListener("DOMContentLoaded", init);
	}

	// bfcache restores fire neither frappe.ready nor webshop's callbacks.
	window.addEventListener("pageshow", function (event) {
		if (event.persisted) {
			refreshBadges();
			paintGreeting();
			pointProfileAtLogin();
		}
	});
})();
