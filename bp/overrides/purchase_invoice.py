# Copyright (c) 2026, Hicom System and contributors
# For license information, please see license.txt

"""Purchase Invoice naming: PI-YYMM####, PR-YYMM#### for returns with goods
(Bry 2026-10-17), AP-ND-YYMM#### for returns without goods (meeting 2026-10-15,
HT-169).

Invoices and returns named with the warehouse code before 2026-10-17
(PA26090001, PRA26090001) keep their names.

Registered via the ``naming_series_variables`` hook in hooks.py so the native
naming-series engine (frappe.model.naming.parse_naming_series) can resolve the
"purchase_warehouse_code" token in the series pattern
(P.purchase_warehouse_code.YY.MM.####) to the receiving warehouse's display
name, e.g. PA26090001, PGS26090001, PRA26090001.

Invoices named under the older Cash/Credit series (PF/PC) keep their names;
the Invoice Type field that drove it was removed.
"""

import frappe

from bp.overrides.series import (
	PURCHASE_DEBIT_NOTE_SERIES,
	PURCHASE_INVOICE_SERIES,
	PURCHASE_RETURN_SERIES,
	PURCHASE_RETURN_SERIES_OCT15,
	PURCHASE_SERIES,
)


def _warehouse(doc):
	"""Accepted Warehouse, or the first item's warehouse when the header is empty."""
	if doc.get("set_warehouse"):
		return doc.set_warehouse
	for item in doc.get("items") or []:
		if item.get("warehouse"):
			return item.warehouse
	return None


def get_purchase_warehouse_code(doc, token=None):
	warehouse = _warehouse(doc)
	if not warehouse:
		return ""
	return frappe.db.get_value("Warehouse", warehouse, "warehouse_name") or ""


def before_naming(doc, method=None):
	"""Pick PI (invoice), PR (return with goods) or AP-ND (return without goods).

	Only the default series is replaced: one picked deliberately (API, Data
	Import, an amended document) is left alone, and opening invoices are named
	after their legacy number before they reach here.
	"""
	if doc.naming_series and doc.naming_series not in (
		PURCHASE_INVOICE_SERIES,
		PURCHASE_SERIES,
		PURCHASE_RETURN_SERIES,
		PURCHASE_RETURN_SERIES_OCT15,
	):
		return
	if doc.get("is_opening") == "Yes":
		return

	if not doc.is_return:
		doc.naming_series = PURCHASE_INVOICE_SERIES
	elif not doc.update_stock:
		doc.naming_series = PURCHASE_DEBIT_NOTE_SERIES
	else:
		doc.naming_series = PURCHASE_RETURN_SERIES_OCT15

# The Expense Head step (set_expense_account before core validate, no "Expense Head Changed" popup) is a Server Script on
# the site since 2026-11-16: "Purchase Invoice - Expense Head Stok" (Client/BP/bp-dev/scripts/server_scripts).
