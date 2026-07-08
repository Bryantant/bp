"""Server-side helper for resolving Google Maps short links.

Customer.custom_titik_koordinat accepts a raw "lat,lng" pair, a full Google
Maps URL, or a short share link (e.g. https://maps.app.goo.gl/xxxx). Raw
coordinates and full URLs (which already contain the coordinates in their
path, e.g. "@-6.2088,106.8456,17z" or "!3d-6.2088!4d106.8456") are parsed
entirely client-side in public/js/customer.js. Short links are opaque tokens
that only reveal coordinates once Google's redirect is followed, which
browser JS cannot do across origins (no CORS access to the redirect target) --
this whitelisted method does that resolution server-side instead.

Restricted to Google's own short-link hosts so this can't be used as a
general-purpose URL-fetching proxy (SSRF).
"""

import re
from urllib.parse import urlparse

import frappe
from frappe import _

ALLOWED_SHORT_LINK_HOSTS = {"maps.app.goo.gl", "goo.gl", "g.co"}

# Prefer the precise pin coordinate Google embeds for a specific place
# (!3d{lat}!4d{lng}); fall back to the map viewport center (@{lat},{lng},{zoom}z).
PIN_PATTERN = re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)")
CENTER_PATTERN = re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+),")


@frappe.whitelist()
def resolve_maps_link(url):
	"""Follow a Google Maps short link's redirect and return its coordinates."""
	import requests

	host = (urlparse(url).hostname or "").lower()
	if host not in ALLOWED_SHORT_LINK_HOSTS:
		frappe.throw(_("Only Google Maps short links can be resolved."))

	try:
		response = requests.head(url, allow_redirects=True, timeout=5)
		final_url = response.url
	except requests.RequestException:
		frappe.throw(_("Could not reach Google Maps to resolve this link."))

	match = PIN_PATTERN.search(final_url) or CENTER_PATTERN.search(final_url)
	if not match:
		frappe.throw(_("Could not find coordinates in the resolved Google Maps link."))

	return {"lat": float(match.group(1)), "lng": float(match.group(2))}
