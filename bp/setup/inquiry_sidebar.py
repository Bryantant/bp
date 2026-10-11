"""Put an Inquiry link in the standard Selling and Buying sidebars.

Stock already carries one (bp/workspace_sidebar/stock.json is a full copy of
that sidebar). Selling and Buying are not copied: they stay ERPNext's own, so
ERPNext updates still reach them, and the link is inserted again after every
migrate (hooks.after_migrate) in case syncing ERPNext's sidebar JSON dropped it.

The row is written straight into the child table instead of saving the
sidebar: Workspace Sidebar.before_save exports standard sidebars back to their
app's JSON in developer mode, which would rewrite ERPNext's own files.

Each link opens the Inquiry page on the matching tab through route_options,
read in inquiry.js (on_page_show). Idempotent: an existing Inquiry link is
updated in place, never duplicated.
"""

import json

import frappe

INQUIRY_PAGE = "inquiry"
ITEM_DOCTYPE = "Workspace Sidebar Item"

# sidebar -> (tab to open, insert after this transaction link)
SIDEBARS = {
	"Selling": ("sales", "Sales Invoice"),
	"Buying": ("purchase", "Purchase Invoice"),
}


def add_inquiry_links():
	changed = False
	for sidebar, (tab, after_link) in SIDEBARS.items():
		if frappe.db.exists("Workspace Sidebar", sidebar):
			changed = add_inquiry_link(sidebar, tab, after_link) or changed
	if changed:
		frappe.clear_cache()


def add_inquiry_link(sidebar, tab, after_link):
	route_options = json.dumps({"tab": tab})
	rows = frappe.get_all(
		ITEM_DOCTYPE,
		filters={"parent": sidebar, "parenttype": "Workspace Sidebar", "parentfield": "items"},
		fields=["name", "idx", "type", "link_type", "link_to", "label", "route_options"],
		order_by="idx asc",
	)

	existing = next((r for r in rows if r.link_type == "Page" and r.link_to == INQUIRY_PAGE), None)
	if existing:
		if existing.label == "Inquiry" and existing.route_options == route_options:
			return False
		frappe.db.set_value(
			ITEM_DOCTYPE, existing.name, {"label": "Inquiry", "route_options": route_options}, update_modified=False
		)
		return True

	after = next((r for r in rows if r.type == "Link" and r.link_to == after_link), None)
	position = after.idx + 1 if after else (rows[-1].idx + 1 if rows else 1)

	# Make room: shift every row at or after the insert position down by one.
	for r in reversed(rows):
		if r.idx >= position:
			frappe.db.set_value(ITEM_DOCTYPE, r.name, "idx", r.idx + 1, update_modified=False)

	item = frappe.get_doc(
		{
			"doctype": ITEM_DOCTYPE,
			"parent": sidebar,
			"parenttype": "Workspace Sidebar",
			"parentfield": "items",
			"idx": position,
			"type": "Link",
			"label": "Inquiry",
			"link_type": "Page",
			"link_to": INQUIRY_PAGE,
			"route_options": route_options,
		}
	)
	item.db_insert()
	return True
