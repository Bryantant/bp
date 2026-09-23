"""Import the legacy trading system's salesmen (`saletabl`) as Sales Persons.

Legacy Import (bp.utils.legacy_import) resolves a delivery order's SaleCode
through `Sales Person.custom_code`, so every code that appears on a document
must exist here before a batch can run. This is master data, so it is a
deliberate one-off script rather than part of the daily import: run it once
before the migration week, and again if the client adds a salesman.

Mapping: SaleCode -> custom_code, SaleName -> sales_person_name (the Sales
Person's name), ActFlag -1 -> enabled. All rows hang off the "All Sales"
root; regroup them by hand afterwards if the client wants a hierarchy.

Idempotent: an existing Sales Person with the same custom_code is updated in
place, and a name already taken by another record gets the code appended.

Usage (from the bench directory):

    bench --site bp.localhost execute bp.utils.import_legacy_salesmen.run
    bench --site bp.localhost execute bp.utils.import_legacy_salesmen.run \\
        --kwargs "{'dry_run': False}"      # --kwargs is eval'd as Python, not JSON

Credentials come from BP Settings (Old System Import) -- see bp.utils.legacy_db.
"""

import frappe

from bp.utils.legacy_db import fetch_all, get_legacy_connection

ROOT_SALES_PERSON = "All Sales"


def run(dry_run=True, only_active=True):
	"""Create/update a Sales Person for every row in the legacy `saletabl`."""
	rows = _fetch_legacy_salesmen(only_active)
	existing_by_code = {
		row.custom_code: row.name
		for row in frappe.get_all("Sales Person", fields=["name", "custom_code"])
		if row.custom_code
	}

	stats = {"created": 0, "updated": 0, "unchanged": 0}
	errors = []

	for row in rows:
		code = (row["SaleCode"] or "").strip()
		name = (row["SaleName"] or "").strip() or code
		enabled = 1 if int(row["ActFlag"] or 0) else 0
		if not code:
			continue
		try:
			stats[_import_salesman(code, name, enabled, existing_by_code)] += 1
		except Exception:
			frappe.log_error(title=f"legacy salesman import failed: {code}")
			errors.append((code, name, frappe.get_traceback(with_context=False)))

	if dry_run:
		frappe.db.rollback()
	else:
		frappe.db.commit()

	mode = "(DRY RUN, nothing written)" if dry_run else "(COMMITTED)"
	print(f"\n--- legacy salesman import {mode} ---")
	print(f"Legacy rows read:  {len(rows)}")
	print(f"Sales Person created: {stats['created']}")
	print(f"Sales Person updated: {stats['updated']}")
	print(f"Already up to date:   {stats['unchanged']}")
	print(f"Errors:               {len(errors)}")
	for code, name, trace in errors:
		print(f"  {code} / {name}: {trace.strip().splitlines()[-1]}")
	if dry_run:
		print("\nThis was a dry run. Re-run with --kwargs \"{'dry_run': False}\" to write.")

	return stats


def _fetch_legacy_salesmen(only_active):
	conn = get_legacy_connection()
	try:
		sql = "SELECT SaleCode, SaleName, ActFlag FROM saletabl"
		if only_active:
			sql += " WHERE ActFlag <> 0"
		return fetch_all(conn, sql + " ORDER BY SaleCode")
	finally:
		conn.close()


def _import_salesman(code, name, enabled, existing_by_code):
	if code in existing_by_code:
		doc = frappe.get_doc("Sales Person", existing_by_code[code])
		if doc.enabled == enabled:
			return "unchanged"
		doc.enabled = enabled
		doc.save()
		return "updated"

	# A Sales Person is named after sales_person_name, so an unrelated record
	# already holding this name would collide.
	if frappe.db.exists("Sales Person", name):
		name = f"{name} ({code})"

	frappe.get_doc(
		{
			"doctype": "Sales Person",
			"sales_person_name": name,
			"custom_code": code,
			"parent_sales_person": ROOT_SALES_PERSON,
			"is_group": 0,
			"enabled": enabled,
		}
	).insert()
	return "created"
