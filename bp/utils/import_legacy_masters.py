"""Create the master records that only exist in the legacy trading system.

The daily document import (bp.utils.legacy_import) deliberately never creates
master data: a delivery order whose customer is unknown fails with a clear
message instead. This script closes that gap for the migration week, filling
in what the first migration did not carry over or what the client has added
in the old system since.

**Create-only.** A record that already exists in ERP is never modified --
staff have edited thousands of them by hand since the first migration (credit
limits, item groups, "customer sejak" dates, active flags), and those edits
win. Legacy values that differ are written to differences.csv for review
instead. The single exception is the `salesperson` part, which fills
Customer.bp_sales_person where it is empty (it is empty on every record) --
that overwrites nothing.

Mapping follows what the already-migrated records actually look like, not
what seems reasonable; see the per-part builders below. Legacy tables used:
custtabl, supptabl, itemtabl, itemuom, itemprice, groutabl, brantabl.

Usage (from the bench directory):

    # Dry run first -- read the printed summary and the CSVs.
    bench --site bp.localhost execute bp.utils.import_legacy_masters.run

    # Then for real (--kwargs is eval'd as Python, not JSON):
    bench --site bp.localhost execute bp.utils.import_legacy_masters.run \\
        --kwargs "{'dry_run': False}"

    # One part only, or a small slice while testing:
    bench --site bp.localhost execute bp.utils.import_legacy_masters.run \\
        --kwargs "{'parts': ['customer'], 'limit': 20}"

Reports land in sites/<site>/private/files/legacy_master_import/.
Credentials come from BP Settings (Old System Import) -- see bp.utils.legacy_db.
"""

import csv
import os
import re

import frappe
from frappe.utils import cint, flt, getdate

from bp.utils.import_legacy_item_prices import _import_row as _import_price_row
from bp.utils.legacy_db import fetch_all, get_legacy_connection

PARTS = ("item_group", "brand", "supplier", "customer", "item", "uom", "price", "salesperson")
BATCH_SIZE = 200
REPORT_DIR = "legacy_master_import"

COMPANY_FALLBACK_WAREHOUSE = "A - BP"
CUSTOMER_GROUP = "Individual"
TERRITORY = "All Territories"
CURRENCY = "IDR"
# CustType on custtabl drives which selling price list the customer gets.
PRICE_LIST_BY_CUST_TYPE = {1: "Retail", 2: "User 1"}
ITEM_END_OF_LIFE = "2099-12-31"


def run(dry_run=True, parts=None, batch_size=BATCH_SIZE, limit=None):
	"""Create missing masters from the legacy database.

	Args:
		dry_run: if True (default) everything runs and is reported, then
			rolled back. Nothing is written.
		parts: subset of PARTS to run, in that order. Default: all.
		batch_size: rows between commits when not a dry run.
		limit: only process this many legacy rows per part (for a test run).
	"""
	parts = _validate_parts(parts)
	ctx = _Context(batch_size=batch_size, dry_run=dry_run, limit=limit)
	ctx.load_legacy()

	stats = {}
	for part in parts:
		stats[part] = PART_RUNNERS[part](ctx)
		ctx.commit()

	if ("customer" in parts or "supplier" in parts) and not dry_run:
		_reseed_naming_counters(ctx)

	ctx.collect_erp_only()

	if dry_run:
		frappe.db.rollback()
	else:
		frappe.db.commit()

	report_dir = ctx.write_reports()
	_print_summary(stats, ctx, report_dir, dry_run)
	return stats


def _validate_parts(parts):
	if not parts:
		return list(PARTS)
	unknown = [p for p in parts if p not in PARTS]
	if unknown:
		frappe.throw(f"Unknown part(s): {', '.join(unknown)}. Valid parts: {', '.join(PARTS)}")
	return [p for p in PARTS if p in parts]


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------


class _Context:
	def __init__(self, batch_size=BATCH_SIZE, dry_run=True, limit=None):
		self.batch_size = batch_size
		self.dry_run = dry_run
		self.limit = limit
		self.pending = 0
		self.company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
			"Global Defaults", "default_company"
		)
		self.skipped = {}
		self.errors = []
		self.differences = []
		self.created = {}
		self.erp_only = []

	# -- legacy data ------------------------------------------------------

	def load_legacy(self):
		conn = get_legacy_connection()
		try:
			self.customers = fetch_all(conn, "SELECT * FROM custtabl ORDER BY CustCode")
			self.suppliers = fetch_all(conn, "SELECT * FROM supptabl ORDER BY SuppCode")
			self.items = fetch_all(conn, "SELECT * FROM itemtabl ORDER BY ItemCode")
			self.groups = fetch_all(conn, "SELECT * FROM groutabl ORDER BY GrouCode")
			self.brands = fetch_all(conn, "SELECT * FROM brantabl ORDER BY BranCode")
			self.item_uoms = fetch_all(conn, "SELECT * FROM itemuom ORDER BY ItemCode, UnitMeas")
			self.item_prices = fetch_all(conn, "SELECT * FROM itemprice ORDER BY ItemCode, Unit")
		finally:
			conn.close()

	def rows(self, rows):
		return rows[: self.limit] if self.limit else rows

	# -- bookkeeping ------------------------------------------------------

	def commit(self, force=True):
		"""Commit a batch unless this is a dry run (where everything is rolled back)."""
		if self.dry_run:
			return
		self.pending += 1
		if force or self.pending >= self.batch_size:
			frappe.db.commit()
			self.pending = 0

	def skip(self, reason, row):
		self.skipped.setdefault(reason, []).append(row)

	def note_created(self, doctype, name, extra=None):
		self.created.setdefault(doctype, []).append({"name": name, **(extra or {})})

	def note_difference(self, doctype, name, field, erp_value, legacy_value):
		self.differences.append(
			{
				"doctype": doctype,
				"name": name,
				"field": field,
				"erp_value": erp_value,
				"legacy_value": legacy_value,
			}
		)

	def collect_erp_only(self):
		"""Records that exist in ERP but no longer in the legacy system (reported, never deleted)."""
		for doctype, rows, key in (
			("Customer", self.customers, "CustCode"),
			("Supplier", self.suppliers, "SuppCode"),
			("Item", self.items, "ItemCode"),
		):
			legacy_codes = {_code(r[key]) for r in rows}
			for name in frappe.get_all(doctype, pluck="name"):
				if name not in legacy_codes:
					self.erp_only.append({"doctype": doctype, "name": name})

	# -- reports ----------------------------------------------------------

	def write_reports(self):
		log_dir = frappe.get_site_path("private", "files", REPORT_DIR)
		os.makedirs(log_dir, exist_ok=True)
		# Clear the previous run's reports first, so an empty bucket this time
		# does not leave a stale file that looks like this run's result.
		for stale in os.listdir(log_dir):
			if stale.endswith(".csv"):
				os.remove(os.path.join(log_dir, stale))
		for doctype, rows in self.created.items():
			_write_csv(os.path.join(log_dir, f"created_{doctype.lower().replace(' ', '_')}.csv"), rows)
		for reason, rows in self.skipped.items():
			_write_csv(os.path.join(log_dir, f"skipped_{reason}.csv"), rows)
		_write_csv(os.path.join(log_dir, "differences.csv"), self.differences)
		_write_csv(os.path.join(log_dir, "erp_only.csv"), self.erp_only)
		_write_csv(os.path.join(log_dir, "errors.csv"), self.errors)
		return log_dir


def _code(value):
	return (value or "").strip()


def _clean(value):
	value = (value or "").strip() if isinstance(value, str) else value
	return value or None


def _payment_terms(cred_term):
	"""Legacy CredTerm -> Payment Terms Template "<n> Days" (blank when 0)."""
	days = cint(cred_term)
	if not days:
		return None
	template = f"{days} Days"
	return template if frappe.db.exists("Payment Terms Template", template) else None


def _insert(doc, ctx):
	"""Insert with the document's own name kept.

	frappe.model.naming.set_new_name() clears doc.name unless frappe.flags.in_import
	is set, and for Customer/Supplier the bp autoname hook (bp/overrides/naming.py)
	would then allocate a fresh C0001-style code. The first migration used the Data
	Import Tool, which sets the same flag -- so this is the same path that produced
	the existing records.
	"""
	doc.flags.ignore_permissions = True
	in_import = frappe.flags.in_import
	frappe.flags.in_import = True
	try:
		doc.insert()
	finally:
		frappe.flags.in_import = in_import
	return doc


def _run_rows(ctx, rows, key, importer):
	"""Shared per-row loop: count outcomes, never let one row abort the part."""
	stats = {"created": 0, "unchanged": 0, "skipped": 0, "errors": 0}
	for row in ctx.rows(rows):
		# One savepoint per row: a row that fails half-way (e.g. the party
		# inserted but its address rejected) leaves nothing behind.
		frappe.db.savepoint("legacy_master_row")
		try:
			outcome = importer(row, ctx)
		except Exception:
			frappe.db.rollback(save_point="legacy_master_row")
			frappe.log_error(title=f"legacy master import failed: {row.get(key)}")
			ctx.errors.append({"code": row.get(key), "error": frappe.get_traceback(with_context=False)})
			stats["errors"] += 1
			continue
		stats[outcome or "skipped"] += 1
		if outcome == "created":
			ctx.commit(force=False)
	return stats


# ---------------------------------------------------------------------------
# Item Group / Brand
# ---------------------------------------------------------------------------


def _import_item_groups(ctx):
	return _run_rows(ctx, ctx.groups, "GrouCode", _import_item_group)


def _import_item_group(row, ctx):
	code = _code(row["GrouCode"])
	if not code:
		return "skipped"
	if frappe.db.exists("Item Group", code):
		return "unchanged"

	parent = _code(row["ProdCode"])
	if not parent or not frappe.db.exists("Item Group", parent):
		ctx.skip("item_group_parent_not_found", {"code": code, "parent": parent})
		return "skipped"

	doc = frappe.new_doc("Item Group")
	doc.update(
		{
			"item_group_name": _code(row["GrouName"]) or code,
			"parent_item_group": parent,
			"is_group": 0,
			# Site-specific mandatory fields; every existing group has
			# custom_abbr == its own code and custom_kode_produk == its parent.
			"custom_abbr": code,
			"custom_kode_produk": parent,
		}
	)
	doc.name = code
	_insert(doc, ctx)
	ctx.note_created("Item Group", code, {"item_group_name": doc.item_group_name, "parent": parent})
	return "created"


def _import_brands(ctx):
	return _run_rows(ctx, ctx.brands, "BranCode", _import_brand)


def _import_brand(row, ctx):
	code = _code(row["BranCode"])
	if not code:
		return "skipped"
	if frappe.db.exists("Brand", code):
		return "unchanged"

	doc = frappe.new_doc("Brand")
	doc.brand = code
	doc.description = _clean(row["BranName"])
	doc.name = code
	_insert(doc, ctx)
	ctx.note_created("Brand", code, {"description": doc.description})
	return "created"


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------


def build_customer(row, ctx):
	"""Legacy custtabl row -> unsaved Customer, mirroring the migrated records."""
	code = _code(row["CustCode"])
	doc = frappe.new_doc("Customer")
	doc.update(
		{
			"customer_name": _code(row["CustName"]) or code,
			"custom_cn_initial": code[:1].upper(),
			"customer_type": "Company",
			"customer_group": CUSTOMER_GROUP,
			"territory": TERRITORY,
			"default_currency": CURRENCY,
			"default_price_list": PRICE_LIST_BY_CUST_TYPE.get(cint(row["CustType"])),
			"payment_terms": _payment_terms(row["CredTerm"]),
			"custom_customer_sejak": getdate(row["CustSinc"]) if row["CustSinc"] else None,
			"custom_nd_code": _clean(row["CustND"]),
		}
	)
	sales_person = ctx.sales_person_by_code.get(_code(row["SaleCode"]).upper())
	if sales_person:
		doc.bp_sales_person = sales_person
		doc.append("sales_team", {"sales_person": sales_person, "allocated_percentage": 100})
	if flt(row["CredLimi"]):
		doc.append("credit_limits", {"company": ctx.company, "credit_limit": flt(row["CredLimi"])})
	doc.name = code
	return doc


def _import_customers(ctx):
	ctx.sales_person_by_code = _sales_person_map()
	return _run_rows(ctx, ctx.customers, "CustCode", _import_customer)


def _import_customer(row, ctx):
	code = _code(row["CustCode"])
	if not code:
		return "skipped"
	if frappe.db.exists("Customer", code):
		_compare_customer(row, code, ctx)
		_customer_children(ctx, row, code)
		return "unchanged"

	doc = build_customer(row, ctx)
	if not doc.bp_sales_person and _code(row["SaleCode"]):
		ctx.skip("customer_sales_person_not_found", {"code": code, "sale_code": _code(row["SaleCode"])})
	_insert(doc, ctx)
	_customer_children(ctx, row, code)
	ctx.note_created("Customer", code, {"customer_name": doc.customer_name})
	return "created"


def _customer_children(ctx, row, code):
	_ensure_party_children(
		ctx,
		"Customer",
		code,
		{
			"line1": row["BillAdd1"],
			"line2": row["BillAdd2"],
			"city": row["BillCity"],
			"pincode": row["BillZipC"],
			"phone": row["BillTelp"],
			"fax": row["BillFaxx"],
		},
		{"person": row["ContPers"] or row["BillAttn"], "phone": row["BillTelp"]},
	)


def _compare_customer(row, code, ctx):
	erp = frappe.db.get_value(
		"Customer",
		code,
		["customer_name", "payment_terms", "default_price_list", "disabled"],
		as_dict=True,
	)
	expected = {
		"customer_name": _code(row["CustName"]) or code,
		"payment_terms": _payment_terms(row["CredTerm"]),
		"default_price_list": PRICE_LIST_BY_CUST_TYPE.get(cint(row["CustType"])),
	}
	for field, legacy_value in expected.items():
		if (erp.get(field) or None) != (legacy_value or None):
			ctx.note_difference("Customer", code, field, erp.get(field), legacy_value)


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------


def build_supplier(row, ctx):
	code = _code(row["SuppCode"])
	doc = frappe.new_doc("Supplier")
	doc.update(
		{
			"supplier_name": _code(row["SuppName"]) or code,
			"custom_initial": code[:1].upper(),
			"supplier_type": "Company",
			"country": "Indonesia",
			"payment_terms": _payment_terms(row["CredTerm"]),
		}
	)
	doc.name = code
	return doc


def _supplier_children(ctx, row, code):
	_ensure_party_children(
		ctx,
		"Supplier",
		code,
		{
			"line1": row["SuppAdd1"],
			"line2": row["SuppAdd2"],
			"city": row["SuppCity"],
			"pincode": row["SuppZipC"],
			"phone": row["SuppTelp"],
			"fax": row["SuppFaxx"],
		},
		{"person": row["SuppAttn"] or row["AcctAttn"], "phone": row["SuppTelp"]},
	)


def _import_suppliers(ctx):
	return _run_rows(ctx, ctx.suppliers, "SuppCode", _import_supplier)


def _import_supplier(row, ctx):
	code = _code(row["SuppCode"])
	if not code:
		return "skipped"
	if frappe.db.exists("Supplier", code):
		erp_name = frappe.db.get_value("Supplier", code, "supplier_name")
		if (erp_name or "") != (_code(row["SuppName"]) or code):
			ctx.note_difference("Supplier", code, "supplier_name", erp_name, _code(row["SuppName"]))
		_supplier_children(ctx, row, code)
		return "unchanged"

	doc = build_supplier(row, ctx)
	_insert(doc, ctx)
	_supplier_children(ctx, row, code)
	ctx.note_created("Supplier", code, {"supplier_name": doc.supplier_name})
	return "created"


# ---------------------------------------------------------------------------
# Address + Contact (one Billing address per party, as the migration did)
# ---------------------------------------------------------------------------


def _has_child(doctype, link_doctype, code):
	return bool(
		frappe.db.exists(
			"Dynamic Link",
			{"link_doctype": link_doctype, "link_name": code, "parenttype": doctype},
		)
	)


def _ensure_party_children(ctx, link_doctype, code, address_kwargs, contact_kwargs):
	"""Create the Billing Address / Contact this party is missing.

	Runs for new parties and for existing ones: a party whose address or
	contact failed on an earlier run (bad legacy phone data, for example) is
	completed on the next run instead of staying half-migrated. Existing
	Address/Contact records are never touched.
	"""
	if not _has_child("Address", link_doctype, code):
		_safely(ctx, "address", code, _create_address, link_doctype, code, **address_kwargs)
	if not _has_child("Contact", link_doctype, code):
		_safely(ctx, "contact", code, _create_contact, link_doctype, code, **contact_kwargs)


def _safely(ctx, what, code, fn, *args, **kwargs):
	"""Address/Contact are secondary to the party itself: on bad legacy data
	report it and keep the party, instead of failing the whole row."""
	frappe.db.savepoint("legacy_master_child")
	try:
		return fn(ctx, *args, **kwargs)
	except Exception:
		frappe.db.rollback(save_point="legacy_master_child")
		ctx.skip(
			f"{what}_failed",
			{"code": code, "error": frappe.get_traceback(with_context=False).strip().splitlines()[-1]},
		)
		return None


def _create_address(ctx, link_doctype, code, line1, line2, city, pincode, phone, fax):
	line1 = _clean(line1)
	if not line1:
		ctx.skip("party_without_address", {"doctype": link_doctype, "code": code})
		return None

	doc = frappe.new_doc("Address")
	doc.update(
		{
			"address_title": code,
			"address_type": "Billing",
			"address_line1": line1,
			"address_line2": _clean(line2),
			# City is mandatory on Address; the first migration wrote "-" for the
			# 3,091 legacy rows with no city, so keep that rather than inventing one.
			"city": _clean(city) or "-",
			"pincode": _clean(pincode),
			"phone": _first_phone(phone),
			"fax": _first_phone(fax),
			"country": "Indonesia",
			"is_primary_address": 1,
		}
	)
	doc.append("links", {"link_doctype": link_doctype, "link_name": code})
	_insert(doc, ctx)
	ctx.note_created("Address", doc.name, {"party": code})
	return doc


# Frappe validates every phone number it is given (Address.phone as well as
# each Contact Phone row), and the legacy fields are free text: several numbers
# packed into one string ("0812.../0813...", "426978 / 7100788/ 7100899") or
# notes instead of a number ("- EXT: 269").
MIN_PHONE_DIGITS = 5


def _split_phones(value):
	"""Split a legacy phone field into the individual usable numbers."""
	parts = [p.strip() for p in re.split(r"[/;,]", value or "") if p.strip()]
	return [p for p in parts if len(re.sub(r"\D", "", p)) >= MIN_PHONE_DIGITS]


def _first_phone(value):
	"""Address has a single phone field: keep the first usable number."""
	phones = _split_phones(value)
	return phones[0] if phones else None


def _create_contact(ctx, link_doctype, code, person, phone):
	phones = _split_phones(phone)
	person = _clean(person)
	if not (phones or person):
		return None

	doc = frappe.new_doc("Contact")
	doc.first_name = person or code
	doc.is_primary_contact = 1
	doc.append("links", {"link_doctype": link_doctype, "link_name": code})
	for i, number in enumerate(phones):
		doc.append("phone_nos", {"phone": number, "is_primary_phone": 1 if i == 0 else 0})
	_insert(doc, ctx)
	ctx.note_created("Contact", doc.name, {"party": code})
	return doc


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------


def item_description(row):
	"""ItemDesc + Size, then the legacy Model on its own line -- the shape the
	migrated items use (e.g. "KIN DEZZERT MILK CHOCO ALMOND80 GR\\n==== 411292")."""
	return f"{_code(row['ItemDesc'])}{_code(row['Size'])}\n==== {_code(row['Model'])}"


def build_item(row, ctx):
	code = _code(row["ItemCode"])
	doc = frappe.new_doc("Item")
	doc.update(
		{
			"item_code": code,
			"item_name": _code(row["ItemDesc"]) or code,
			"description": item_description(row),
			"item_group": _code(row["GrouCode"]),
			"brand": _code(row["BranCode"]) or None,
			"stock_uom": _code(row["Unit1000"]),
			"custom_old_item_code": code,
			"custom_external_item_code": _clean(row["MaPartNo"]),
			"is_stock_item": 1,
			"is_sales_item": 1,
			"is_purchase_item": 1,
			"end_of_life": ITEM_END_OF_LIFE,
			"disabled": 0 if cint(row["ActiveFlag"]) else 1,
		}
	)
	doc.append("item_defaults", {"company": ctx.company, "default_warehouse": ctx.default_warehouse})
	for uom_row in ctx.uoms_by_item.get(code, []):
		doc.append("uoms", {"uom": uom_row["uom"], "conversion_factor": uom_row["factor"]})
	if not any(u.uom == doc.stock_uom for u in doc.uoms):
		doc.append("uoms", {"uom": doc.stock_uom, "conversion_factor": 1})
	doc.name = code
	return doc


def _import_items(ctx):
	ctx.default_warehouse = _default_warehouse(ctx)
	ctx.uoms_by_item = _legacy_uoms_by_item(ctx)
	return _run_rows(ctx, ctx.items, "ItemCode", _import_item)


def _import_item(row, ctx):
	code = _code(row["ItemCode"])
	if not code:
		return "skipped"
	if frappe.db.exists("Item", code):
		_compare_item(row, code, ctx)
		return "unchanged"

	group = _code(row["GrouCode"])
	if not group or not frappe.db.exists("Item Group", group):
		ctx.skip("item_group_not_found", {"item_code": code, "item_group": group})
		return "skipped"
	brand = _code(row["BranCode"])
	if brand and not frappe.db.exists("Brand", brand):
		ctx.skip("item_brand_not_found", {"item_code": code, "brand": brand})
		return "skipped"
	stock_uom = _code(row["Unit1000"])
	if not stock_uom or not frappe.db.exists("UOM", stock_uom):
		ctx.skip("item_uom_not_found", {"item_code": code, "uom": stock_uom})
		return "skipped"

	doc = build_item(row, ctx)
	_insert(doc, ctx)
	ctx.note_created("Item", code, {"item_name": doc.item_name, "item_group": doc.item_group})
	return "created"


def _compare_item(row, code, ctx):
	erp = frappe.db.get_value("Item", code, ["item_name", "item_group", "brand", "disabled"], as_dict=True)
	expected = {
		"item_name": _code(row["ItemDesc"]) or code,
		"item_group": _code(row["GrouCode"]),
		"brand": _code(row["BranCode"]) or None,
		"disabled": 0 if cint(row["ActiveFlag"]) else 1,
	}
	for field, legacy_value in expected.items():
		if (erp.get(field) or None) != (legacy_value or None):
			ctx.note_difference("Item", code, field, erp.get(field), legacy_value)


def _default_warehouse(ctx):
	existing = frappe.db.sql(
		"""select default_warehouse, count(*) n from `tabItem Default`
		where ifnull(default_warehouse, '') <> '' group by default_warehouse order by n desc limit 1"""
	)
	return existing[0][0] if existing else COMPANY_FALLBACK_WAREHOUSE


def _legacy_uoms_by_item(ctx):
	grouped = {}
	for row in ctx.item_uoms:
		uom = _code(row["UnitMeas"])
		factor = flt(row["Packing"]) or 1
		if uom:
			grouped.setdefault(_code(row["ItemCode"]), []).append({"uom": uom, "factor": factor})
	return grouped


# ---------------------------------------------------------------------------
# UOM conversion rows missing on items that already exist
# ---------------------------------------------------------------------------


def _import_uom_rows(ctx):
	"""Add legacy itemuom rows that are missing from an existing Item's UOM table.

	Only adds rows; an existing row whose factor differs is reported, never
	changed (changing a conversion factor would silently restate stock).
	"""
	stats = {"created": 0, "unchanged": 0, "skipped": 0, "errors": 0}
	existing = {
		(row[0], row[1]): flt(row[2])
		for row in frappe.db.sql("select parent, uom, conversion_factor from `tabUOM Conversion Detail`")
	}
	by_item = {}
	for row in ctx.rows(ctx.item_uoms):
		uom = _code(row["UnitMeas"])
		item = _code(row["ItemCode"])
		if not (item and uom):
			continue
		key = (item, uom)
		if key in existing:
			if abs(existing[key] - (flt(row["Packing"]) or 1)) > 0.0001:
				ctx.note_difference("Item", item, f"uom:{uom}", existing[key], flt(row["Packing"]) or 1)
			stats["unchanged"] += 1
			continue
		if not frappe.db.exists("Item", item):
			ctx.skip("uom_item_not_found", {"item_code": item, "uom": uom})
			stats["skipped"] += 1
			continue
		if not frappe.db.exists("UOM", uom):
			ctx.skip("uom_not_found", {"item_code": item, "uom": uom})
			stats["skipped"] += 1
			continue
		by_item.setdefault(item, []).append({"uom": uom, "conversion_factor": flt(row["Packing"]) or 1})

	for item, rows in by_item.items():
		try:
			doc = frappe.get_doc("Item", item)
			for row in rows:
				doc.append("uoms", row)
			doc.flags.ignore_permissions = True
			doc.save()
			stats["created"] += len(rows)
			for row in rows:
				ctx.note_created("UOM Conversion Detail", f"{item}:{row['uom']}", row)
			ctx.commit(force=False)
		except Exception:
			frappe.log_error(title=f"legacy uom import failed: {item}")
			ctx.errors.append({"code": item, "error": frappe.get_traceback(with_context=False)})
			stats["errors"] += 1
	return stats


# ---------------------------------------------------------------------------
# Item Price for items that have none yet
# ---------------------------------------------------------------------------

# Legacy price column -> ERP Price List, same split the first migration used.
PRICE_COLUMNS = {"StdPrice": "User 1", "StdPrice2": "Retail"}


def _import_prices(ctx):
	"""Create Item Price rows for items that do not have one yet.

	Reuses bp.utils.import_legacy_item_prices._import_row so the UOM/currency
	rules stay in one place; that helper updates an existing row in place, so
	this part only feeds it (item, unit, price list) combinations that are
	missing.
	"""
	stats = {"created": 0, "unchanged": 0, "skipped": 0, "errors": 0}
	existing = {
		(row[0], row[1], row[2])
		for row in frappe.db.sql("select item_code, uom, price_list from `tabItem Price`")
	}
	skipped = {"item_not_found": [], "uom_not_found": [], "uom_not_on_item": [], "currency_not_found": []}

	for row in ctx.rows(ctx.item_prices):
		item = _code(row["ItemCode"])
		uom = _code(row["Unit"])
		for column, price_list in PRICE_COLUMNS.items():
			price = flt(row.get(column))
			if price <= 0:
				continue
			if (item, uom, price_list) in existing:
				stats["unchanged"] += 1
				continue
			try:
				outcome = _import_price_row(
					{"ItemCode": item, "Unit": uom, "CurrCode": _code(row["CurrCode"]), "Price": price},
					price_list,
					skipped,
				)
			except Exception:
				frappe.log_error(title=f"legacy item price import failed: {item}")
				ctx.errors.append({"code": item, "error": frappe.get_traceback(with_context=False)})
				stats["errors"] += 1
				continue
			if outcome == "created":
				stats["created"] += 1
				ctx.note_created("Item Price", f"{item}:{uom}:{price_list}", {"rate": price})
				ctx.commit(force=False)
			elif outcome:
				stats[outcome if outcome in stats else "unchanged"] += 1
			else:
				stats["skipped"] += 1

	for reason, rows in skipped.items():
		for row in rows:
			ctx.skip(f"price_{reason}", row)
	return stats


# ---------------------------------------------------------------------------
# Sales Person on Customer (fills an empty field, never overwrites)
# ---------------------------------------------------------------------------


def _import_sales_persons(ctx):
	"""Set Customer.bp_sales_person (+ a 100% Sales Team row) from custtabl.SaleCode.

	bp/public/js/customer.js keeps those two in sync in the browser only, so a
	server-side fill has to write both, exactly as the form would.
	"""
	stats = {"created": 0, "unchanged": 0, "skipped": 0, "errors": 0}
	by_code = _sales_person_map()
	empty = set(
		frappe.get_all("Customer", filters={"bp_sales_person": ["is", "not set"]}, pluck="name")
	)

	for row in ctx.rows(ctx.customers):
		code = _code(row["CustCode"])
		if code not in empty:
			stats["unchanged"] += 1
			continue
		sales_person = by_code.get(_code(row["SaleCode"]).upper())
		if not sales_person:
			ctx.skip("customer_sales_person_not_found", {"code": code, "sale_code": _code(row["SaleCode"])})
			stats["skipped"] += 1
			continue
		try:
			doc = frappe.get_doc("Customer", code)
			doc.bp_sales_person = sales_person
			if not doc.sales_team:
				doc.append("sales_team", {"sales_person": sales_person, "allocated_percentage": 100})
			doc.flags.ignore_permissions = True
			doc.save()
			stats["created"] += 1
			ctx.commit(force=False)
		except Exception:
			frappe.log_error(title=f"legacy sales person backfill failed: {code}")
			ctx.errors.append({"code": code, "error": frappe.get_traceback(with_context=False)})
			stats["errors"] += 1
	return stats


def _sales_person_map():
	return {
		_code(row.custom_code).upper(): row.name
		for row in frappe.get_all(
			"Sales Person",
			filters={"enabled": 1, "custom_code": ["is", "set"]},
			fields=["name", "custom_code"],
		)
	}


def _reseed_naming_counters(ctx):
	"""Raise BP Naming Counter to the new maximum so the next manually created
	Customer/Supplier does not collide with an imported code.

	Only ever called on a real run: the patch ends with frappe.db.commit(),
	which would make a "dry run" write everything created before it.
	"""
	from bp.patches.v1_0.seed_bp_naming_counters import execute as seed_counters

	if ctx.dry_run:
		raise RuntimeError("seed_bp_naming_counters commits; never call it during a dry run")
	seed_counters()


PART_RUNNERS = {
	"item_group": _import_item_groups,
	"brand": _import_brands,
	"supplier": _import_suppliers,
	"customer": _import_customers,
	"item": _import_items,
	"uom": _import_uom_rows,
	"price": _import_prices,
	"salesperson": _import_sales_persons,
}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _write_csv(path, rows):
	if not rows:
		if os.path.exists(path):
			os.remove(path)
		return
	fieldnames = sorted({key for row in rows for key in row})
	with open(path, "w", newline="", encoding="utf-8") as f:
		writer = csv.DictWriter(f, fieldnames=fieldnames)
		writer.writeheader()
		writer.writerows(rows)


def _print_summary(stats, ctx, report_dir, dry_run):
	mode = "(DRY RUN, nothing written)" if dry_run else "(COMMITTED)"
	print(f"\n--- legacy master import summary {mode} ---")
	print(f"{'part':<12} {'created':>8} {'unchanged':>10} {'skipped':>8} {'errors':>7}")
	for part, s in stats.items():
		print(f"{part:<12} {s['created']:>8} {s['unchanged']:>10} {s['skipped']:>8} {s['errors']:>7}")
	if ctx.skipped:
		print("\nSkipped by reason:")
		for reason, rows in sorted(ctx.skipped.items()):
			print(f"  {reason}: {len(rows)}")
	print(f"\nDifferences on existing records (not changed): {len(ctx.differences)}")
	print(f"In ERP but no longer in the old system (not deleted): {len(ctx.erp_only)}")
	print(f"Errors: {len(ctx.errors)}")
	print(f"Reports written to: {report_dir}")
	if dry_run:
		print("\nThis was a dry run. Re-run with --kwargs \"{'dry_run': False}\" to write.")
