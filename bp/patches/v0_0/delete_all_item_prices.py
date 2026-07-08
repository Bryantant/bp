import frappe


def execute():
	count = frappe.db.count("Item Price")
	print(f"Deleting {count} Item Price rows...")
	frappe.db.sql("DELETE FROM `tabItem Price`")
	frappe.db.commit()
	remaining = frappe.db.count("Item Price")
	print(f"Done. Remaining rows: {remaining}")
