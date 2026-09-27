# Copyright (c) 2026, Hicom System and contributors
# For license information, please see license.txt

"""Purchase Invoice naming: P + warehouse code, PR + warehouse code for returns.

Registered via the ``naming_series_variables`` hook in hooks.py so the native
naming-series engine (frappe.model.naming.parse_naming_series) can resolve the
"purchase_warehouse_code" token in the series pattern
(P.purchase_warehouse_code.YY.MM.####) to the receiving warehouse's display
name, e.g. PA26090001, PGS26090001, PRA26090001.

Invoices named under the older Cash/Credit series (PF/PC) keep their names;
the Invoice Type field that drove it was removed
(bp.patches.v1_0.remove_purchase_invoice_invoice_type_field).
"""

import frappe
from frappe import _

from bp.patches.v1_0.name_invoices_and_returns_by_warehouse import (
	PURCHASE_RETURN_SERIES,
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
	"""Pick P (invoice) or PR (return) + warehouse code.

	Only the default series is replaced: one picked deliberately (API, Data
	Import, an amended document) is left alone, and opening invoices are named
	after their legacy number before they reach here.
	"""
	if doc.naming_series and doc.naming_series not in (PURCHASE_SERIES, PURCHASE_RETURN_SERIES):
		return
	if doc.get("is_opening") == "Yes":
		return

	if not _warehouse(doc):
		frappe.throw(
			_("Accepted Warehouse is required: the invoice number is built from the warehouse code."),
			title=_("Missing Warehouse"),
		)
	doc.naming_series = PURCHASE_RETURN_SERIES if doc.is_return else PURCHASE_SERIES
