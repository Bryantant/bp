# Copyright (c) 2026, BP and contributors
# For license information, please see license.txt

"""Server methods for the Inquiry desk page.

Item-level inquiry tool with four tabs (Balance, Sales, Purchase, Price List).
Each whitelisted method takes a single JSON ``filters`` argument and returns a
uniform ``{"columns": [...], "data": [...]}`` payload so the client can render
dynamic columns (warehouses, price lists) generically.

Column objects are ``{"label", "fieldname", "fieldtype"}``; every row in
``data`` is a dict keyed by ``fieldname``.
"""

import erpnext
import frappe
from frappe import _
from frappe.utils import add_months, flt, getdate, nowdate

# Rows returned for the unbounded history tabs, as a safety net.
HISTORY_LIMIT = 1000

# Items scanned for the Balance / Price List pivots when filters are broad, as a safety net.
ITEM_LIMIT = 5000


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _parse_filters(filters):
	if isinstance(filters, str):
		filters = frappe.parse_json(filters) or {}
	return filters or {}


def _as_list(value):
	"""Normalize a filter value to a list (MultiSelectList sends lists, links send scalars)."""
	if not value:
		return []
	if isinstance(value, (list, tuple)):
		return [v for v in value if v]
	return [value]


def _default_company():
	company = erpnext.get_default_company()
	if not company:
		frappe.throw(_("No default company is configured. Set one in Global Defaults."))
	return company


def _item_groups_with_descendants(item_groups):
	"""Return the selected item groups plus all of their descendants (nested set).

	Accepts a single group name or a list. Returns ``None`` when nothing is selected.
	"""
	groups = _as_list(item_groups)
	if not groups:
		return None
	names = set()
	for group in groups:
		bounds = frappe.db.get_value("Item Group", group, ["lft", "rgt"])
		if not bounds:
			continue
		lft, rgt = bounds
		names.update(
			frappe.db.sql_list(
				"""select name from `tabItem Group` where lft >= %s and rgt <= %s""",
				(lft, rgt),
			)
		)
	return list(names) or None


def _leaf_warehouses(company):
	"""Non-group, enabled warehouses of the company, ordered for stable columns."""
	return frappe.get_all(
		"Warehouse",
		filters={"company": company, "is_group": 0, "disabled": 0},
		order_by="name",
		pluck="name",
	)


def _item_conditions(filters, alias):
	"""Build a parametrized WHERE fragment + params for the item filters.

	``alias`` is the table alias that exposes ``item_code``, ``item_name`` and
	``item_group`` (the Item table or an invoice item child table).
	"""
	conds, params = [], {}
	groups = _item_groups_with_descendants(filters.get("item_group"))
	if groups:
		conds.append(f"{alias}.item_group in %(item_groups)s")
		params["item_groups"] = tuple(groups)
	if filters.get("item"):
		conds.append(f"{alias}.item_code = %(item)s")
		params["item"] = filters["item"]
	return " and ".join(conds), params


def _matching_item_codes(filters):
	"""Item codes matching the item/group filters (enabled items only)."""
	conds, params = _item_conditions(filters, "it")
	params["limit"] = ITEM_LIMIT
	where = "it.disabled = 0"
	if conds:
		where += " and " + conds
	return frappe.db.sql_list(
		f"select it.item_code from `tabItem` it where {where} order by it.item_code limit %(limit)s",
		params,
	)


# ---------------------------------------------------------------------------
# Balance tab
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_balance(filters=None):
	filters = _parse_filters(filters)

	company = _default_company()
	warehouses = _leaf_warehouses(company)

	# Resolve the matching items first (capped) so the Bin join never truncates an item's
	# warehouse rows mid-pivot when filters are broad / empty.
	conds, params = _item_conditions(filters, "it")
	where = "it.disabled = 0"
	if conds:
		where += " and " + conds
	params["limit"] = ITEM_LIMIT

	items = frappe.db.sql(
		f"""
		select it.item_code, it.item_name, it.stock_uom, it.valuation_rate
		from `tabItem` it
		where {where}
		order by it.item_code
		limit %(limit)s
		""",
		params,
		as_dict=True,
	)

	by_item = {}
	for it in items:
		row = {
			"item_code": it.item_code,
			"item_name": it.item_name,
			"stock_uom": it.stock_uom,
			"total_qty": 0.0,
			"hpp": flt(it.valuation_rate),
		}
		for wh in warehouses:
			row[wh] = 0.0
		by_item[it.item_code] = row

	if by_item and warehouses:
		bins = frappe.db.sql(
			"""
			select item_code, warehouse, actual_qty
			from `tabBin`
			where item_code in %(items)s and warehouse in %(whs)s
			""",
			{"items": tuple(by_item.keys()), "whs": tuple(warehouses)},
			as_dict=True,
		)
		for b in bins:
			item = by_item.get(b.item_code)
			if item is not None:
				item[b.warehouse] = flt(item.get(b.warehouse)) + flt(b.actual_qty)
				item["total_qty"] = flt(item["total_qty"]) + flt(b.actual_qty)

	columns = [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link"},
		{"label": _("Description"), "fieldname": "item_name", "fieldtype": "Data"},
	]
	for wh in warehouses:
		columns.append({"label": wh, "fieldname": wh, "fieldtype": "Float"})
	columns += [
		{"label": _("Unit"), "fieldname": "stock_uom", "fieldtype": "Data"},
		{"label": _("Total Qty"), "fieldname": "total_qty", "fieldtype": "Float"},
		{"label": _("HPP"), "fieldname": "hpp", "fieldtype": "Currency"},
	]

	return {"columns": columns, "data": list(by_item.values())}


# ---------------------------------------------------------------------------
# Sales tab
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_sales(filters=None):
	filters = _parse_filters(filters)
	from_date = filters.get("from_date") or add_months(nowdate(), -3)
	to_date = filters.get("to_date") or nowdate()

	conds, params = _item_conditions(filters, "sii")
	params.update({"from_date": getdate(from_date), "to_date": getdate(to_date), "limit": HISTORY_LIMIT})

	where = "si.docstatus = 1 and si.posting_date between %(from_date)s and %(to_date)s"
	if conds:
		where += " and " + conds
	customers = _as_list(filters.get("customer"))
	if customers:
		where += " and si.customer in %(customers)s"
		params["customers"] = tuple(customers)

	data = frappe.db.sql(
		f"""
		select sii.item_code, sii.item_name, si.posting_date as date,
		       sii.qty, sii.uom as unit, si.currency as ccy, sii.rate as price,
		       si.customer as cust, si.name as do_no
		from `tabSales Invoice Item` sii
		join `tabSales Invoice` si on si.name = sii.parent
		where {where}
		order by si.posting_date desc, si.name
		limit %(limit)s
		""",
		params,
		as_dict=True,
	)

	columns = [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link"},
		{"label": _("Description"), "fieldname": "item_name", "fieldtype": "Data"},
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date"},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float"},
		{"label": _("Unit"), "fieldname": "unit", "fieldtype": "Data"},
		{"label": _("Ccy"), "fieldname": "ccy", "fieldtype": "Data"},
		{"label": _("Price"), "fieldname": "price", "fieldtype": "Currency"},
		{"label": _("Cust."), "fieldname": "cust", "fieldtype": "Link"},
		{"label": _("DO No."), "fieldname": "do_no", "fieldtype": "Link"},
	]

	return {"columns": columns, "data": data}


# ---------------------------------------------------------------------------
# Purchase tab
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_purchase(filters=None):
	filters = _parse_filters(filters)
	from_date = filters.get("from_date") or add_months(nowdate(), -3)
	to_date = filters.get("to_date") or nowdate()

	conds, params = _item_conditions(filters, "pii")
	params.update({"from_date": getdate(from_date), "to_date": getdate(to_date), "limit": HISTORY_LIMIT})

	where = "pi.docstatus = 1 and pi.posting_date between %(from_date)s and %(to_date)s"
	if conds:
		where += " and " + conds
	suppliers = _as_list(filters.get("supplier"))
	if suppliers:
		where += " and pi.supplier in %(suppliers)s"
		params["suppliers"] = tuple(suppliers)

	data = frappe.db.sql(
		f"""
		select pii.item_code, pii.item_name, pi.posting_date as date,
		       pii.qty, pii.uom as unit, pi.currency as ccy, pii.rate as price,
		       pi.is_return as rtn, pi.supplier as supp, pi.name as purchase_no,
		       pi.bill_no as supp_do_no
		from `tabPurchase Invoice Item` pii
		join `tabPurchase Invoice` pi on pi.name = pii.parent
		where {where}
		order by pi.posting_date desc, pi.name
		limit %(limit)s
		""",
		params,
		as_dict=True,
	)

	columns = [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link"},
		{"label": _("Description"), "fieldname": "item_name", "fieldtype": "Data"},
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date"},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float"},
		{"label": _("Unit"), "fieldname": "unit", "fieldtype": "Data"},
		{"label": _("Ccy"), "fieldname": "ccy", "fieldtype": "Data"},
		{"label": _("Price"), "fieldname": "price", "fieldtype": "Currency"},
		{"label": _("Rtn"), "fieldname": "rtn", "fieldtype": "Check"},
		{"label": _("Supp."), "fieldname": "supp", "fieldtype": "Link"},
		{"label": _("Purchase No."), "fieldname": "purchase_no", "fieldtype": "Link"},
		{"label": _("Supp DO No."), "fieldname": "supp_do_no", "fieldtype": "Data"},
	]

	return {"columns": columns, "data": data}


# ---------------------------------------------------------------------------
# Price List tab
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_price_list(filters=None):
	filters = _parse_filters(filters)

	company = _default_company()
	warehouses = _leaf_warehouses(company)

	item_codes = _matching_item_codes(filters)
	if not item_codes:
		return {"columns": _price_list_columns([]), "data": []}

	selling_lists = frappe.get_all(
		"Price List",
		filters={"selling": 1, "enabled": 1},
		order_by="name",
		pluck="name",
	)

	# Item meta: description, stock uom, hpp.
	items = frappe.get_all(
		"Item",
		filters={"item_code": ["in", item_codes]},
		fields=["item_code", "item_name", "stock_uom", "valuation_rate"],
	)
	item_meta = {it.item_code: it for it in items}

	# Total stock per item (company leaf warehouses).
	stock = {}
	if warehouses:
		bins = frappe.db.sql(
			"""
			select item_code, sum(actual_qty) as qty
			from `tabBin`
			where item_code in %(items)s and warehouse in %(whs)s
			group by item_code
			""",
			{"items": tuple(item_codes), "whs": tuple(warehouses)},
			as_dict=True,
		)
		stock = {b.item_code: flt(b.qty) for b in bins}

	# Selling item prices.
	prices = frappe.db.sql(
		"""
		select item_code, uom, price_list, price_list_rate, currency
		from `tabItem Price`
		where selling = 1 and item_code in %(items)s
		""",
		{"items": tuple(item_codes)},
		as_dict=True,
	)

	# Pivot keyed by (item_code, uom).
	by_key = {}
	for p in prices:
		uom = p.uom or item_meta.get(p.item_code, {}).get("stock_uom")
		key = (p.item_code, uom)
		row = by_key.get(key)
		if row is None:
			meta = item_meta.get(p.item_code, {})
			row = {
				"item_code": p.item_code,
				"item_name": meta.get("item_name"),
				"ccy": p.currency,
				"qty": stock.get(p.item_code, 0.0),
				"unit": uom,
				"hpp": flt(meta.get("valuation_rate")),
			}
			for pl in selling_lists:
				row[pl] = None
			by_key[key] = row
		if not row.get("ccy"):
			row["ccy"] = p.currency
		row[p.price_list] = flt(p.price_list_rate)

	return {"columns": _price_list_columns(selling_lists), "data": list(by_key.values())}


def _price_list_columns(selling_lists):
	columns = [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link"},
		{"label": _("Description"), "fieldname": "item_name", "fieldtype": "Data"},
		{"label": _("Ccy"), "fieldname": "ccy", "fieldtype": "Data"},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float"},
		{"label": _("Unit"), "fieldname": "unit", "fieldtype": "Data"},
	]
	for pl in selling_lists:
		columns.append({"label": pl, "fieldname": pl, "fieldtype": "Currency"})
	columns.append({"label": _("HPP"), "fieldname": "hpp", "fieldtype": "Currency"})
	return columns


# ---------------------------------------------------------------------------
# Item detail subform (per-UOM pack + selling prices + image)
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_item_detail(item_code):
	"""Detail panel for a single item: image, meta, and a per-UOM pack/price table."""
	if not item_code:
		return {}

	item = frappe.db.get_value(
		"Item",
		item_code,
		["item_code", "item_name", "stock_uom", "valuation_rate", "image"],
		as_dict=True,
	)
	if not item:
		return {}

	selling_lists = frappe.get_all(
		"Price List",
		filters={"selling": 1, "enabled": 1},
		order_by="name",
		pluck="name",
	)

	# UOM rows: stock UOM (pack = 1) plus the item's UOM conversion rows.
	uom_rows = {}

	def _row(uom):
		row = uom_rows.get(uom)
		if row is None:
			row = {"uom": uom, "pack": None, "ccy": None}
			for pl in selling_lists:
				row[pl] = None
			uom_rows[uom] = row
		return row

	if item.stock_uom:
		_row(item.stock_uom)["pack"] = 1.0

	conversions = frappe.get_all(
		"UOM Conversion Detail",
		filters={"parent": item_code},
		fields=["uom", "conversion_factor"],
	)
	for conv in conversions:
		_row(conv.uom)["pack"] = flt(conv.conversion_factor)

	# Selling prices per UOM.
	prices = frappe.db.sql(
		"""
		select uom, price_list, price_list_rate, currency
		from `tabItem Price`
		where selling = 1 and item_code = %s
		""",
		(item_code,),
		as_dict=True,
	)
	for p in prices:
		uom = p.uom or item.stock_uom
		row = _row(uom)
		row[p.price_list] = flt(p.price_list_rate)
		if not row.get("ccy"):
			row["ccy"] = p.currency

	return {
		"item_code": item.item_code,
		"item_name": item.item_name,
		"stock_uom": item.stock_uom,
		"hpp": flt(item.valuation_rate),
		"image": item.image,
		"price_lists": selling_lists,
		"uoms": list(uom_rows.values()),
	}
