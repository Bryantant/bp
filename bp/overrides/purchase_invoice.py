# Copyright (c) 2026, Hicom System and contributors
# For license information, please see license.txt

"""Naming-series custom parser mapping Purchase Invoice's Cash/Credit
"Invoice Type" to a one-letter naming series code (C / F).

Registered via the ``naming_series_variables`` hook in hooks.py so the
native naming-series engine (frappe.model.naming.parse_naming_series) can
resolve the "invoice_type_code" token in the series pattern
(invoice_type_code.YY.MM.####) to a code, without exposing "C"/"F" as
selectable values on the (user-facing) custom_invoice_type field itself.
"""

INVOICE_TYPE_CODES = {"Cash": "C", "Credit": "F"}


def get_invoice_type_code(doc, token=None):
	return INVOICE_TYPE_CODES.get(doc.get("custom_invoice_type"), "")

