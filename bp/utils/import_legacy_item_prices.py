"""Backfill the "User 1" Price List from the legacy trading database.

Context: in the legacy Access/MySQL trading system (`bpol-trd`.`itemprice`),
the column `StdPrice` -- labelled "Harga User" on screen -- holds a price for
7,503 of 8,727 rows (86%). That data was never migrated into ERP: the "User 1"
Price List, which is the default selling price list for ~3,900 customers, has
zero Item Price rows. Meanwhile `StdPrice2` ("Harga Retail", 3,271 rows) WAS
migrated correctly into the "Retail" Price List. This script closes that gap
by importing `StdPrice` into "User 1", one Item Price row per (item, unit,
currency), matching the legacy table's own grain.

This is a one-time backfill, not a patch: it depends on network access to a
legacy server outside this bench, so it must never run automatically via
`bench migrate`. Run it by hand, once per site that needs it.

Safety:
- Dry run by default. Nothing is written until you pass dry_run=False.
- Idempotent: re-running updates existing "User 1" Item Price rows in place
  instead of duplicating them, so it's safe to re-run after fixing data.
- Per-row try/except: one bad row is logged and skipped, never aborts the run.
- Skipped/errored rows are written to CSV files you can hand back to whoever
  owns the source data, instead of only being printed to the console.

Usage (from the bench directory, against the site you want to fix):

    # 1. Point it at the legacy server -- never hardcode credentials in code.
    #    (Skip this if BP Settings > Old System Import is already filled in.)
    export LEGACY_DB_HOST=<legacy server>       # ask Bry
    export LEGACY_DB_USER=hicom
    export LEGACY_DB_PASSWORD='...'          # ask Bry
    export LEGACY_DB_NAME=bpol-trd           # default if omitted

    # 2. Dry run first. Read the summary and the CSVs before doing anything else.
    bench --site bp.hicomsystem.com execute bp.utils.import_legacy_item_prices.run

    # 3. Once the dry run looks right, commit for real.
    bench --site bp.hicomsystem.com execute bp.utils.import_legacy_item_prices.run \\
        --kwargs '{"dry_run": false}'

CSV reports land in this site's private files, under
`legacy_item_price_import/`: `skipped_item_not_found.csv`,
`skipped_uom_not_found.csv`, `skipped_currency_not_found.csv`, and
`errors.csv`. Review skipped_item_not_found.csv especially -- those are
prices for items that don't exist in ERP under that exact code.
"""

import csv
import os

import frappe
from frappe.utils import cint, flt

PRICE_LIST = "User 1"
LEGACY_PRICE_COLUMN = "StdPrice"
BATCH_SIZE = 200


def run(dry_run=True, price_list=PRICE_LIST, batch_size=BATCH_SIZE, only_item_codes=None):
	"""Import legacy `itemprice.StdPrice` ("Harga User") rows into `price_list`.

	Args:
		dry_run: if True (default), nothing is committed -- everything runs and
			is reported, then rolled back.
		price_list: target Price List. Defaults to "User 1"; override only if
			you are re-running this against a different gap.
		batch_size: how many rows between `frappe.db.commit()` calls when not
			a dry run. Keeps one giant transaction from holding locks too long.
		only_item_codes: optional iterable of item codes to restrict the run
			to -- use this to test on a handful of items before the full run.
	"""
	_require_price_list(price_list)
	rows = _fetch_legacy_rows(only_item_codes)
	frappe.logger().info(f"[legacy_item_price_import] fetched {len(rows)} candidate rows")

	stats = {"created": 0, "updated": 0, "unchanged": 0}
	skipped = {
		"item_not_found": [],
		"uom_not_found": [],
		"uom_not_on_item": [],
		"currency_not_found": [],
	}
	errors = []

	for i, row in enumerate(rows, start=1):
		try:
			outcome = _import_row(row, price_list, skipped)
			if outcome:
				stats[outcome] += 1
		except Exception:
			frappe.log_error(
				title="legacy_item_price_import row failed",
				message=frappe.get_traceback(),
			)
			errors.append({**row, "error": frappe.get_traceback(with_context=False)})

		if not dry_run and i % batch_size == 0:
			frappe.db.commit()
			frappe.logger().info(f"[legacy_item_price_import] committed after {i} rows")

	if dry_run:
		frappe.db.rollback()
	else:
		frappe.db.commit()

	log_dir = _write_reports(skipped, errors)

	mode = "(DRY RUN, nothing written)" if dry_run else "(COMMITTED)"
	print(f"\n--- legacy_item_price_import summary {mode} ---")
	print(f"Price List target:      {price_list}")
	print(f"Legacy rows read:       {len(rows)}")
	print(f"Item Price created:     {stats['created']}")
	print(f"Item Price updated:     {stats['updated']}")
	print(f"Already up to date:     {stats['unchanged']}")
	print(f"Skipped - item missing: {len(skipped['item_not_found'])}")
	print(f"Skipped - UOM missing:  {len(skipped['uom_not_found'])}")
	print(f"Skipped - UOM not on item's conversion table: {len(skipped['uom_not_on_item'])}")
	print(f"Skipped - currency:     {len(skipped['currency_not_found'])}")
	print(f"Errors:                 {len(errors)}")
	print(f"Reports written to:     {log_dir}")
	if dry_run:
		print("\nThis was a dry run. Re-run with --kwargs '{\"dry_run\": false}' once you've checked the reports.")

	return stats


def _require_price_list(price_list):
	if not frappe.db.exists("Price List", price_list):
		frappe.throw(f'Price List "{price_list}" does not exist on this site. Create it first.')


def _fetch_legacy_rows(only_item_codes):
	conn = _legacy_connection()
	try:
		with conn.cursor() as cursor:
			sql = (
				f"SELECT ItemCode, Unit, CurrCode, {LEGACY_PRICE_COLUMN} AS Price "
				"FROM itemprice WHERE " + f"{LEGACY_PRICE_COLUMN} > 0"
			)
			params = []
			if only_item_codes:
				placeholders = ", ".join(["%s"] * len(only_item_codes))
				sql += f" AND ItemCode IN ({placeholders})"
				params = list(only_item_codes)
			sql += " ORDER BY ItemCode, Unit"
			cursor.execute(sql, params)
			return cursor.fetchall()
	finally:
		conn.close()


def _legacy_connection():
	# Credentials come from BP Settings, falling back to the LEGACY_DB_*
	# environment variables described in the module docstring.
	from bp.utils.legacy_db import get_legacy_connection

	return get_legacy_connection()


def _import_row(row, price_list, skipped):
	item_code = (row.get("ItemCode") or "").strip()
	uom = (row.get("Unit") or "").strip()
	currency = (row.get("CurrCode") or "").strip()
	rate = flt(row.get("Price"))

	if not item_code or not frappe.db.exists("Item", item_code):
		skipped["item_not_found"].append(row)
		return None

	resolved_uom = _resolve_uom(uom)
	if not resolved_uom:
		skipped["uom_not_found"].append(row)
		return None

	if not currency or not frappe.db.exists("Currency", currency):
		skipped["currency_not_found"].append(row)
		return None

	if not _uom_valid_for_item(item_code, resolved_uom):
		skipped["uom_not_on_item"].append(row)
		return None

	existing_name = frappe.db.get_value(
		"Item Price",
		{"item_code": item_code, "price_list": price_list, "uom": resolved_uom},
		"name",
	)

	if existing_name:
		doc = frappe.get_doc("Item Price", existing_name)
		if flt(doc.price_list_rate) == rate and doc.currency == currency:
			return "unchanged"
		doc.price_list_rate = rate
		doc.currency = currency
		doc.save(ignore_permissions=True)
		return "updated"

	doc = frappe.get_doc(
		{
			"doctype": "Item Price",
			"item_code": item_code,
			"price_list": price_list,
			"uom": resolved_uom,
			"currency": currency,
			"price_list_rate": rate,
			"selling": cint(frappe.db.get_value("Price List", price_list, "selling")),
			"buying": cint(frappe.db.get_value("Price List", price_list, "buying")),
			"note": "Imported from legacy itemprice.StdPrice (\"Harga User\") -- see "
			"bp.utils.import_legacy_item_prices",
		}
	)
	doc.insert(ignore_permissions=True)
	return "created"


def _resolve_uom(legacy_uom):
	"""Match a legacy unit code to an existing UOM, tolerating case only.

	Deliberately does NOT try to guess across genuinely different spellings --
	an unmatched UOM is reported in skipped_uom_not_found.csv for a human to
	map, rather than silently attached to the wrong unit of measure.
	"""
	if not legacy_uom:
		return None
	if frappe.db.exists("UOM", legacy_uom):
		return legacy_uom
	return frappe.db.get_value("UOM", {"uom_name": ["like", legacy_uom]}, "name")


def _uom_valid_for_item(item_code, uom):
	"""ERPNext's Item Price validation rejects a UOM that isn't the item's
	stock UOM and isn't in that item's own UOM conversion table -- a UOM
	existing globally isn't enough. Check that here so those rows land in
	skipped_uom_not_on_item.csv instead of erroring, since the real fix is
	adding the conversion factor to the item, not something this script
	should guess at.
	"""
	stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
	if uom == stock_uom:
		return True
	return bool(frappe.db.exists("UOM Conversion Detail", {"parent": item_code, "uom": uom}))


def _write_reports(skipped, errors):
	log_dir = frappe.get_site_path("private", "files", "legacy_item_price_import")
	os.makedirs(log_dir, exist_ok=True)

	for name, rows in skipped.items():
		_write_csv(os.path.join(log_dir, f"skipped_{name}.csv"), rows)
	_write_csv(os.path.join(log_dir, "errors.csv"), errors)

	return log_dir


def _write_csv(path, rows):
	if not rows:
		if os.path.exists(path):
			os.remove(path)
		return
	with open(path, "w", newline="", encoding="utf-8") as f:
		writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
		writer.writeheader()
		writer.writerows(rows)
