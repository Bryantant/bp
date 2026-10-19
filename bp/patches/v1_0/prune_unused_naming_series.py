"""Drop the naming series no new document uses (Bry 2026-10-18).

Every doctype whose series BP sets still listed the series from before the
2026-10-15 numbering decision (HT-169) and ERPNext's own defaults; Payment
Entry still listed ACC-PAY-.YYYY.-. New documents only get the series below:
the first is the default, and before_naming (bp.overrides.sales_invoice /
purchase_invoice / stock_entry) or the Payment Entry Server Script
"Payment Entry - Seri per Tipe" picks the others. Customer, Supplier and Item
have a single series and are not listed.

Documents named with a dropped series keep their names, and drafts holding one
still save: Frappe does not check naming_series against its options
(BaseDocument._validate_selects skips it). The counters in tabSeries are left
as they are.

Idempotent: Property Setters are keyed by (doctype, fieldname, property).
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from bp.patches.v1_0.apply_document_numbering_oct15 import (
	DELIVERY_NOTE_SERIES,
	JOURNAL_ENTRY_SERIES,
	PURCHASE_DEBIT_NOTE_SERIES,
	PURCHASE_INVOICE_SERIES,
	PURCHASE_ORDER_SERIES,
	PURCHASE_RETURN_SERIES_OCT15,
	QUOTATION_SERIES,
	SALES_CREDIT_NOTE_SERIES,
	SALES_DEBIT_NOTE_SERIES,
	SALES_INVOICE_SERIES_OCT15,
	SALES_NON_STOCK_SERIES_OCT15,
	SALES_ORDER_SERIES,
	SALES_RETURN_SERIES_OCT15,
	STOCK_ENTRY_SERIES,
	STOCK_RECONCILIATION_SERIES,
)

OPTIONS = {
	"Sales Invoice": [
		SALES_INVOICE_SERIES_OCT15,
		SALES_RETURN_SERIES_OCT15,
		SALES_NON_STOCK_SERIES_OCT15,
		SALES_CREDIT_NOTE_SERIES,
		SALES_DEBIT_NOTE_SERIES,
	],
	"Purchase Invoice": [PURCHASE_INVOICE_SERIES, PURCHASE_RETURN_SERIES_OCT15, PURCHASE_DEBIT_NOTE_SERIES],
	"Journal Entry": [JOURNAL_ENTRY_SERIES],
	# RCV / PAY / TRF per Payment Type (decision 2026-09-27).
	"Payment Entry": ["RCV-.YY.MM.####", "PAY-.YY.MM.####", "TRF-.YY.MM.####"],
	# The 2026-10-15 list has no return series for Delivery Note: returns get DO- too.
	"Delivery Note": [DELIVERY_NOTE_SERIES],
	"Stock Entry": list(STOCK_ENTRY_SERIES.values()),
	"Purchase Order": [PURCHASE_ORDER_SERIES],
	"Quotation": [QUOTATION_SERIES],
	"Sales Order": [SALES_ORDER_SERIES],
	"Stock Reconciliation": [STOCK_RECONCILIATION_SERIES],
}


def execute():
	for doctype, options in OPTIONS.items():
		make_property_setter(doctype, "naming_series", "options", "\n".join(options), "Text")
		make_property_setter(doctype, "naming_series", "default", options[0], "Text")
		frappe.clear_cache(doctype=doctype)
