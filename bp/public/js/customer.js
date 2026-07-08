frappe.ui.form.on("Customer", {
	refresh: function (frm) {
		frm.set_query("bp_sales_person", function () {
			return { filters: { is_group: 0 } };
		});
		bp.customer.sync_from_table(frm);
		bp.customer.render_location_preview(frm);
	},

	bp_sales_person: function (frm) {
		bp.customer.push_to_table(frm);
	},

	custom_titik_koordinat: function (frm) {
		bp.customer.render_location_preview(frm);
	},
});

frappe.provide("bp.customer");

bp.customer = {
	// Matches "latitude,longitude" e.g. "-6.2088,106.8456"; tolerant of a
	// space after the comma (how it looks if a human retypes it).
	COORDINATE_REGEX: /^(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)$/,

	// Coordinates embedded in a full Google Maps URL: prefer the precise pin
	// Google embeds for a specific place, fall back to the map viewport center.
	URL_PIN_REGEX: /!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)/,
	URL_CENTER_REGEX: /@(-?\d+\.\d+),(-?\d+\.\d+)/,

	// Google's own short-link hosts -- these are opaque tokens that need a
	// server-side redirect resolution (see bp.overrides.customer.resolve_maps_link).
	SHORT_LINK_HOSTS: ["maps.app.goo.gl", "goo.gl", "g.co"],

	sync_from_table: function (frm) {
		var first = frm.doc.sales_team && frm.doc.sales_team[0];
		if (first && first.sales_person && frm.doc.bp_sales_person !== first.sales_person) {
			frm.set_value("bp_sales_person", first.sales_person);
		}
	},

	push_to_table: function (frm) {
		var person = frm.doc.bp_sales_person;
		frm.clear_table("sales_team");
		if (person) {
			var row = frm.add_child("sales_team");
			row.sales_person = person;
			row.allocated_percentage = 100;
		}
		frm.refresh_field("sales_team");
	},

	is_valid_latlng: function (lat, lng) {
		return lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
	},

	parse_coordinates: function (value) {
		var match = bp.customer.COORDINATE_REGEX.exec(value.trim());
		if (!match) return null;
		var lat = parseFloat(match[1]);
		var lng = parseFloat(match[2]);
		return bp.customer.is_valid_latlng(lat, lng) ? { lat: lat, lng: lng } : null;
	},

	parse_coordinates_from_url: function (value) {
		var match = bp.customer.URL_PIN_REGEX.exec(value) || bp.customer.URL_CENTER_REGEX.exec(value);
		if (!match) return null;
		var lat = parseFloat(match[1]);
		var lng = parseFloat(match[2]);
		return bp.customer.is_valid_latlng(lat, lng) ? { lat: lat, lng: lng } : null;
	},

	get_url_host: function (value) {
		try {
			return new URL(value).hostname.toLowerCase();
		} catch (e) {
			return null;
		}
	},

	build_search_url: function (coords) {
		return (
			"https://www.google.com/maps/search/?api=1&query=" +
			encodeURIComponent(coords.lat + "," + coords.lng)
		);
	},

	render_location_preview: function (frm) {
		var field = frm.fields_dict.custom_peta_lokasi;
		if (!field) return;
		var wrapper = field.$wrapper;

		var raw = (frm.doc.custom_titik_koordinat || "").trim();
		if (!raw) {
			wrapper.empty();
			return;
		}

		if (!/^https?:\/\//i.test(raw)) {
			var coords = bp.customer.parse_coordinates(raw);
			if (!coords) {
				bp.customer.render_error(wrapper);
				return;
			}
			bp.customer.render_map(wrapper, coords, bp.customer.build_search_url(coords));
			return;
		}

		// URL input: a full Google Maps URL already has coordinates in its
		// path (parse client-side); a short share link needs the server to
		// follow its redirect first.
		var url_coords = bp.customer.parse_coordinates_from_url(raw);
		if (url_coords) {
			bp.customer.render_map(wrapper, url_coords, raw);
			return;
		}

		var host = bp.customer.get_url_host(raw);
		if (host && bp.customer.SHORT_LINK_HOSTS.indexOf(host) !== -1) {
			bp.customer.render_loading(wrapper);
			frappe.call({
				method: "bp.overrides.customer.resolve_maps_link",
				args: { url: raw },
				callback: function (r) {
					// The field may have changed while this call was in flight.
					if ((frm.doc.custom_titik_koordinat || "").trim() !== raw) return;
					if (r.message && r.message.lat != null) {
						bp.customer.render_map(wrapper, r.message, raw);
					} else {
						bp.customer.render_link_only(wrapper, raw);
					}
				},
				error: function () {
					if ((frm.doc.custom_titik_koordinat || "").trim() !== raw) return;
					bp.customer.render_link_only(wrapper, raw);
				},
			});
			return;
		}

		bp.customer.render_error(wrapper);
	},

	render_loading: function (wrapper) {
		wrapper.html('<div class="text-muted small" style="padding: 6px 0;">' + __("Resolving link…") + "</div>");
	},

	render_error: function (wrapper) {
		wrapper.html(
			'<div class="text-muted small" style="padding: 6px 0;">' +
				__(
					'Coordinate format looks wrong. Paste "latitude,longitude" or a Google Maps link, e.g. -6.2088,106.8456.'
				) +
				"</div>"
		);
	},

	render_link_only: function (wrapper, url) {
		wrapper.html(
			'<div class="bp-location-preview">' +
				'<div class="text-muted small" style="padding-bottom: 6px;">' +
					__("Could not load a preview for this link.") +
				"</div>" +
				'<a href="' + url + '" target="_blank" rel="noopener" class="btn btn-sm btn-default">' +
					'<i class="fa fa-map-marker-alt"></i> ' + __("Open in Google Maps") +
				"</a>" +
			"</div>"
		);
	},

	render_map: function (wrapper, coords, open_url) {
		var query = coords.lat + "," + coords.lng;
		var embed_src = "https://maps.google.com/maps?q=" + encodeURIComponent(query) + "&z=15&output=embed";

		wrapper.html(
			'<div class="bp-location-preview">' +
				'<iframe src="' + embed_src + '" width="100%" height="220" ' +
					'style="border:0; border-radius: 4px;" loading="lazy" ' +
					'referrerpolicy="no-referrer-when-downgrade"></iframe>' +
				'<a href="' + open_url + '" target="_blank" rel="noopener" ' +
					'class="btn btn-sm btn-default" style="margin-top: 8px;">' +
					'<i class="fa fa-map-marker-alt"></i> ' + __("Open in Google Maps") +
				"</a>" +
			"</div>"
		);
	},
};
