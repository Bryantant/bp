# Copyright (c) 2026, Hicom System and contributors
# For license information, please see license.txt

"""Mobile app-shell for the storefront: a fixed header and a bottom tab bar.

Injected into every website page through the ``update_website_context`` hook,
which appends our markup to ``context.body_include``. That slot renders last in
``<body>`` (frappe ``templates/base.html``) and -- unlike ``head_include`` -- is
not overridden by any template in frappe/erpnext/webshop, so the shell reaches
every page. It also survives ``/me``, which blanks the ``navbar`` block outright.

Both bars are ``position: fixed``, so being last in the DOM does not affect where
they paint. Desktop is untouched: the shell is ``display: none`` by default and
only switched on inside a max-width media query (``public/css/storefront.css``).

CACHE SAFETY -- read before editing
-----------------------------------
Website pages are cached by path + language only, never by user
(``frappe/website/utils.py`` -> ``website_page::<path>``), and that cache is live
whenever developer_mode is off. Everything rendered here is therefore shared by
every visitor. Do NOT read ``frappe.session``, roles, the cart, or anything else
user-specific in this module -- it would be baked into the shared cache and
served to the wrong user. Per-user behaviour (the cart badge, and the guest vs.
logged-in profile link) is applied client-side from cookies in
``public/js/storefront.js``.
"""

import frappe

HOME = "home"
PRODUCT = "product"
CART = "cart"
TRANSACTION = "transaction"
PROFILE = "profile"

# First path segment -> the tab that lights up.
ROUTE_TABS = {
	"": HOME,
	"home": HOME,
	"all-products": PRODUCT,
	"shop-by-category": PRODUCT,
	"cart": CART,
	"checkout": CART,
	"orders": TRANSACTION,
	"order": TRANSACTION,
	"invoices": TRANSACTION,
	"shipments": TRANSACTION,
	"me": PROFILE,
	"addresses": PROFILE,
	"update-profile": PROFILE,
	"wishlist": PROFILE,
}

# Secondary pages get a back-arrow + page-title header instead of the brand bar.
# Keyed by first path segment so it stays path-derived (and therefore cache-safe).
ROUTE_TITLES = {
	"cart": "Cart",
	"checkout": "Checkout",
	"orders": "Transaction",
	"order": "Order",
	"invoices": "Invoices",
	"shipments": "Shipments",
	"me": "Profile",
	"addresses": "Addresses",
	"update-profile": "Edit Profile",
	"wishlist": "Wishlist",
}

# Auth flows, print views and the desk must never get the shell.
SKIP_ROUTES = {
	"login",
	"signup",
	"update-password",
	"reset-password",
	"verify-email",
	"printview",
	"print",
	"app",
	"website_script.js",
}

MARKER = "bp-appshell"
TEMPLATE = "bp/templates/includes/app_shell.html"


def update_website_context(context):
	"""``update_website_context`` hook -- append the app shell to body_include."""
	if not _should_render(context):
		return

	segment = _route_segment()
	active_tab = ROUTE_TABS.get(segment, "")
	page_title = ROUTE_TITLES.get(segment)

	html = frappe.render_template(
		TEMPLATE,
		{
			"active_tab": active_tab,
			"brand_logo": context.get("banner_image") or "",
			# "titled" = back arrow + page name; "brand" = logo/greeting + icons.
			"variant": "titled" if page_title else "brand",
			"page_title": page_title,
			# Greeting is Home-only. The name itself is filled in client-side --
			# rendering it here would cache one user's name for everyone.
			"show_greeting": active_tab == HOME,
		},
	)

	# Append, never clobber: nothing in core sets body_include today, but a Web
	# Page's own get_context could.
	return {"body_include": (context.get("body_include") or "") + html}


def _should_render(context):
	# Keep this idempotent in case the hook ever runs twice on one context.
	if MARKER in (context.get("body_include") or ""):
		return False

	# Web Forms bypass the navbar/footer blocks but still render body_include,
	# so they would otherwise pick up the shell.
	if context.get("web_form_doc"):
		return False

	# NB: deliberately does NOT check `no_header`. Despite the name, that flag is
	# about a page hiding its own H1 title block -- Web Page sets it whenever
	# show_title is off (web_page.py) -- not about site chrome. Treating it as
	# "no chrome" silently stripped the shell from every Page Builder homepage.
	# `hide_navbar` is the real chrome flag, and only Web Forms set it.
	if context.get("hide_navbar"):
		return False

	return _route_segment() not in SKIP_ROUTES


def _route_segment():
	"""First segment of the *requested* URL.

	Deliberately reads ``frappe.local.request.path`` rather than the obvious
	alternatives, both of which are wrong here:

	* ``context.path`` is not populated yet -- ``base_template_page.py`` calls
	  this hook before ``set_missing_values()``, which is what assigns it.
	* ``frappe.local.path`` has already been rewritten by the router, so "/"
	  becomes the configured home page's route. Home and that route would then
	  be indistinguishable, and the wrong tab would light up on "/".
	"""
	request = getattr(frappe.local, "request", None)
	path = getattr(request, "path", None) or "/"
	return path.strip("/").split("/")[0]


def _active_tab():
	return ROUTE_TABS.get(_route_segment(), "")
