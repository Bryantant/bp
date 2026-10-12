"""Put a "Stock Mutation" link (Stock Entry) in the Selling and Invoicing sidebars.

Task HT-8: sales admins (Relokasi Barang only) and the accounting team now
use Stock Entry, but its only links sit in the Stock and BP Setup sidebars,
which those users do not open. Same approach as inquiry_sidebar.py: ERPNext's
sidebars are not copied, the row is written straight into the child table
after every migrate (hooks.after_migrate). Idempotent.
"""

import frappe

ITEM_DOCTYPE = "Workspace Sidebar Item"
LABEL = "Stock Mutation"
LINK_TO = "Stock Entry"

# sidebar -> insert after this link
SIDEBARS = {
	"Selling": "inquiry",
	"Invoicing": "Journal Entry",
}


def add_stock_mutation_links():
	changed = False
	for sidebar, after_link in SIDEBARS.items():
		if frappe.db.exists("Workspace Sidebar", sidebar):
			changed = add_stock_mutation_link(sidebar, after_link) or changed
	if changed:
		frappe.clear_cache()


def add_stock_mutation_link(sidebar, after_link):
	rows = frappe.get_all(
		ITEM_DOCTYPE,
		filters={"parent": sidebar, "parenttype": "Workspace Sidebar", "parentfield": "items"},
		fields=["name", "idx", "type", "link_type", "link_to", "label"],
		order_by="idx asc",
	)
	if any(r.link_type == "DocType" and r.link_to == LINK_TO and r.label == LABEL for r in rows):
		return False

	after = next((r for r in rows if r.type == "Link" and r.link_to == after_link), None)
	position = after.idx + 1 if after else (rows[-1].idx + 1 if rows else 1)

	for r in reversed(rows):
		if r.idx >= position:
			frappe.db.set_value(ITEM_DOCTYPE, r.name, "idx", r.idx + 1, update_modified=False)

	frappe.get_doc(
		{
			"doctype": ITEM_DOCTYPE,
			"parent": sidebar,
			"parenttype": "Workspace Sidebar",
			"parentfield": "items",
			"idx": position,
			"type": "Link",
			"label": LABEL,
			"link_type": "DocType",
			"link_to": LINK_TO,
		}
	).db_insert()
	return True
