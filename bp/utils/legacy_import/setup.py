"""One-off site setup Legacy Import needs beyond BP Settings.

The old system keeps three stock locations besides the four selling ones:
GS (scrap -- where staff put damaged returns), BR (barang retur, goods
returned and waiting) and KS (consignment stock at customers). Returns and
stock mutations move goods through all three, so each becomes its own ERP
warehouse -- keeping damaged and consignment stock out of sellable stock, as
the old system did -- and is mapped in BP Settings.

This is master data per site, so it is a script to run once per site rather
than a patch:

    bench --site bp.localhost execute bp.utils.legacy_import.setup.ensure_legacy_warehouses
    bench --site bp.localhost execute bp.utils.legacy_import.setup.ensure_legacy_warehouses \\
        --kwargs "{'dry_run': False}"

Idempotent: an existing warehouse or mapping row is left as it is.
"""

import frappe

# Old-system branch code -> what it holds. The code doubles as the ERP
# warehouse_name, which the Sales Invoice naming series uses (GS26090001).
LEGACY_WAREHOUSES = {
	"GS": "Scrap / barang rusak",
	"BR": "Barang retur",
	"KS": "Konsinyasi",
}


def ensure_legacy_warehouses(dry_run=True, company=None):
	company = company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	abbr = frappe.get_cached_value("Company", company, "abbr")
	# Put them next to the existing selling warehouses, whatever the site's
	# tree looks like (on bp.localhost A-D sit at the top level, no group).
	sibling = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0}, "parent_warehouse")
	parent = sibling or None
	where = parent or "the top level, next to the existing warehouses"

	settings = frappe.get_single("BP Settings")
	mapped = {(row.branch_code or "").strip().upper() for row in settings.legacy_warehouse_map}

	actions = []
	for code, description in LEGACY_WAREHOUSES.items():
		name = f"{code} - {abbr}"
		if not frappe.db.exists("Warehouse", name):
			actions.append(f"create warehouse {name} ({description}) at {where}")
			if not dry_run:
				frappe.get_doc(
					{
						"doctype": "Warehouse",
						"warehouse_name": code,
						# Site-level mandatory custom field ("Nama Warehouse"); A-D
						# predate it and are empty, new ones get the description.
						"custom_nama_warehouse": description,
						"parent_warehouse": parent,
						"company": company,
					}
				).insert(ignore_permissions=True)
		if code not in mapped:
			actions.append(f"map old-system branch {code} -> {name}")
			if not dry_run:
				settings.append("legacy_warehouse_map", {"branch_code": code, "warehouse": name})

	if not dry_run and actions:
		settings.save(ignore_permissions=True)
		frappe.db.commit()

	mode = "DRY RUN, nothing written" if dry_run else "COMMITTED"
	print(f"--- legacy warehouses ({mode}) ---")
	for action in actions or ["nothing to do"]:
		print(f"  {action}")
	print("Current mapping:")
	for row in frappe.get_single("BP Settings").legacy_warehouse_map:
		print(f"  {row.branch_code} -> {row.warehouse}")
	return actions


# Purpose -> the name to give a Stock Entry Type this site is missing. The
# site renamed ERPNext's standard types in Indonesian (Barang Masuk / Barang
# Keluar / Relokasi Barang) and has none for Repack, which set assemblies need.
STOCK_ENTRY_TYPES = {"Repack": "Rakit Set"}


def ensure_stock_entry_types(dry_run=True):
	"""Create a Stock Entry Type for each purpose Legacy Import needs and the site lacks.

	    bench --site bp.localhost execute bp.utils.legacy_import.setup.ensure_stock_entry_types \\
	        --kwargs "{'dry_run': False}"
	"""
	actions = []
	for purpose, name in STOCK_ENTRY_TYPES.items():
		if frappe.db.exists("Stock Entry Type", {"purpose": purpose}):
			continue
		actions.append(f"create Stock Entry Type {name} (purpose {purpose})")
		if not dry_run:
			frappe.get_doc({"doctype": "Stock Entry Type", "name": name, "purpose": purpose}).insert(
				ignore_permissions=True
			)
	if not dry_run and actions:
		frappe.db.commit()
	print(f"--- stock entry types ({'DRY RUN, nothing written' if dry_run else 'COMMITTED'}) ---")
	for action in actions or ["nothing to do"]:
		print(f"  {action}")
	return actions
