"""Fill Price List Rate on purchases from the supplier's last purchase.

Bry's decision (2026-10-19): the starting price on a Purchase Invoice or
Purchase Order line is the last price paid to that supplier for that item,
not a price list. "Last price" is the Price List Rate (the gross price before
% Disk 1 / Disk 1) of the latest submitted Purchase Invoice from the same
supplier, company and currency; returns are skipped. Legacy imports carry
the old system's gross price there, so history from Hicom Access counts.

Wraps ERPNext's two whitelisted price lookups (override_whitelisted_methods
in hooks.py): get_item_details when an item or UOM is picked, apply_price_list
when the supplier, currency or price list changes. Without a previous
purchase the core result (Standard Buying, usually empty) is kept.
"""

import frappe
from erpnext.stock import get_item_details as core
from frappe.utils import flt

DOCTYPES = ("Purchase Invoice", "Purchase Order")


def last_price_per_stock_uom(supplier, item_code, company, currency):
	rows = frappe.db.sql(
		"""
		SELECT pii.price_list_rate, pii.rate, pii.conversion_factor
		FROM `tabPurchase Invoice Item` pii
		JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
		WHERE pi.docstatus = 1 AND pi.is_return = 0
			AND pi.supplier = %s AND pii.item_code = %s
			AND pi.company = %s AND pi.currency = %s
		ORDER BY pi.posting_date DESC, pi.posting_time DESC, pi.creation DESC, pii.idx DESC
		LIMIT 1
		""",
		(supplier, item_code, company, currency),
		as_dict=True,
	)
	if not rows:
		return None
	row = rows[0]
	price = flt(row.price_list_rate) or flt(row.rate)
	return price / (flt(row.conversion_factor) or 1) if price else None


def _price_for(ctx, item):
	if ctx.get("doctype") not in DOCTYPES or not ctx.get("supplier") or not item.get("item_code"):
		return None
	price = last_price_per_stock_uom(
		ctx.get("supplier"), item.get("item_code"), ctx.get("company"), ctx.get("currency")
	)
	if price is None:
		return None
	return flt(price * (flt(item.get("conversion_factor")) or 1), 9)


def _copy(ctx):
	# Read before core runs: it normalizes and changes the dict it is given.
	return frappe._dict(frappe.parse_json(frappe.as_json(ctx) if isinstance(ctx, dict) else ctx))


def _set_price(out, price):
	out["price_list_rate"] = price
	out["discount_percentage"] = 0
	out["discount_amount"] = 0
	out["rate"] = price


@frappe.whitelist()
def get_item_details(ctx, doc=None, for_validate=False, overwrite_warehouse=True):
	args = _copy(ctx)
	out = core.get_item_details(ctx, doc=doc, for_validate=for_validate, overwrite_warehouse=overwrite_warehouse)
	if for_validate:
		return out
	price = _price_for(args, {"item_code": args.get("item_code"), "conversion_factor": out.get("conversion_factor")})
	if price is not None:
		_set_price(out, price)
	return out


@frappe.whitelist()
def apply_price_list(ctx, as_doc=False, doc=None):
	args = _copy(ctx)
	out = core.apply_price_list(ctx, as_doc=as_doc, doc=doc)
	if as_doc:
		return out
	for item, child in zip(args.get("items") or [], out.get("children") or []):
		price = _price_for(args, item)
		if price is not None:
			_set_price(child, price)
	return out
