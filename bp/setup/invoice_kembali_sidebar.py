"""Put "Invoice Kembali" (form) and "Invoice Belum Kembali" (report) links in
the Invoicing and Selling sidebars (HT-42).

Same approach as stock_mutation_sidebar.py: ERPNext's sidebars are not copied,
the rows are written straight into the child table after every migrate
(hooks.after_migrate). Idempotent.
"""

import frappe

ITEM_DOCTYPE = "Workspace Sidebar Item"

# (label, link_type, link_to)
LINKS = [
	("Invoice Kembali", "DocType", "Invoice Kembali"),
	("Invoice Belum Kembali", "Report", "Invoice Belum Kembali"),
]

# sidebar -> insert after this link
SIDEBARS = {
	"Invoicing": "Accounts Receivable",
	"Selling": "Sales Invoice",
}


def add_invoice_kembali_links():
	changed = False
	for sidebar, after_link in SIDEBARS.items():
		if frappe.db.exists("Workspace Sidebar", sidebar):
			for link in reversed(LINKS):
				changed = add_link(sidebar, after_link, *link) or changed
	if changed:
		frappe.clear_cache()


def add_link(sidebar, after_link, label, link_type, link_to):
	rows = frappe.get_all(
		ITEM_DOCTYPE,
		filters={"parent": sidebar, "parenttype": "Workspace Sidebar", "parentfield": "items"},
		fields=["name", "idx", "type", "link_type", "link_to", "label"],
		order_by="idx asc",
	)
	if any(r.link_type == link_type and r.link_to == link_to for r in rows):
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
			"label": label,
			"link_type": link_type,
			"link_to": link_to,
		}
	).db_insert()
	return True
