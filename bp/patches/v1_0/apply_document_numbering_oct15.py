"""Document numbers decided with the client on 2026-10-15 (HT-169).

	Delivery Note             DO-  + warehouse code + YYMM + 4 digits   DO-A26100001
	Stock Entry               MI- / MO- / MA- / MR- + YYMM + 4 digits    MI-26100001
	                          (Barang Masuk / Barang Keluar / Rakit Set / Relokasi Barang)
	Purchase Order            PO-  + YYMM + 4 digits                      PO-26100001
	Purchase Invoice          PI-  + YYMM + 4 digits                      PI-26100001
	Purchase return, goods    PR-  + YYMM + 4 digits                      PR-26100001
	                          (Bry 2026-10-17; was PR + warehouse code, PRA26090001)
	Purchase return, no goods AP-ND- + YYMM + 4 digits                    AP-ND-26100001
	Quotation                 Q-   + YYMM + 4 digits                      Q-26100001
	Sales Invoice credit note AR-NC- + YYMM + 4 digits (return, no goods)
	Sales Invoice debit note  AR-ND- + YYMM + 4 digits (Is Debit Note)
	Sales Invoice with goods  INV- + warehouse code + YYMM + 4 digits     INV-A26100001
	                          (Bry 2026-10-17, instead of SINV-; prints stay SJ-A26100001)
	Sales return with goods   SR- + warehouse code + YYMM + 4 digits      SR-A26100001
	Value-only Sales Invoice  ND- + YYMM + 4 digits                       ND-26100001
	                          (was NDB-26-0001; ND System invoices are still named after
	                          their own ND number, so the two do not collide)
	Journal Entry             JE-  + YYMM + 4 digits                      JE-26100001
	Sales Order               SO-  + YYMM + 4 digits                      SO-26100001
	Stock Reconciliation      REC- + YYMM + 4 digits                      REC-26100001
	                          (these three: Bry 2026-10-18; Bry wrote "JE-.YYMM.", but YYMM
	                          is not a naming token, so YY.MM.#### as for the others)

The first option is the default; the per-document choice is made in each
doctype's before_naming (bp.overrides.*). Documents already named keep their
names. The series field stays hidden from users, as for the invoices.

Idempotent: Property Setters are keyed by (doctype, fieldname, property).
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

DELIVERY_NOTE_SERIES = "DO-.warehouse_name_code.YY.MM.####"

STOCK_ENTRY_SERIES = {
	"Material Receipt": "MI-.YY.MM.####",
	"Material Issue": "MO-.YY.MM.####",
	"Repack": "MA-.YY.MM.####",
	"Material Transfer": "MR-.YY.MM.####",
}

PURCHASE_ORDER_SERIES = "PO-.YY.MM.####"
PURCHASE_INVOICE_SERIES = "PI-.YY.MM.####"
PURCHASE_DEBIT_NOTE_SERIES = "AP-ND-.YY.MM.####"
PURCHASE_RETURN_SERIES_OCT15 = "PR-.YY.MM.####"
QUOTATION_SERIES = "Q-.YY.MM.####"
SALES_CREDIT_NOTE_SERIES = "AR-NC-.YY.MM.####"
SALES_DEBIT_NOTE_SERIES = "AR-ND-.YY.MM.####"
SALES_INVOICE_SERIES_OCT15 = "INV-.warehouse_name_code.YY.MM.####"
SALES_RETURN_SERIES_OCT15 = "SR-.warehouse_name_code.YY.MM.####"
SALES_NON_STOCK_SERIES_OCT15 = "ND-.YY.MM.####"
JOURNAL_ENTRY_SERIES = "JE-.YY.MM.####"
SALES_ORDER_SERIES = "SO-.YY.MM.####"
STOCK_RECONCILIATION_SERIES = "REC-.YY.MM.####"

# Kept literal so the patch does not depend on later edits elsewhere.
PURCHASE_RETURN_SERIES = "PR.purchase_warehouse_code.YY.MM.####"
SALES_WAREHOUSE_SERIES = "warehouse_name_code.YY.MM.####"
SALES_RETURN_SERIES = "SR.warehouse_name_code.YY.MM.####"
SALES_NON_STOCK_SERIES = "NDB-.YY.-.####"

OPTIONS = {
	"Delivery Note": [DELIVERY_NOTE_SERIES, "MAT-DN-.YYYY.-", "MAT-DN-RET-.YYYY.-"],
	"Stock Entry": [*STOCK_ENTRY_SERIES.values(), "MAT-STE-.YYYY.-"],
	"Purchase Order": [PURCHASE_ORDER_SERIES, "PO.YY.MM.####", "PUR-ORD-.YYYY.-"],
	"Purchase Invoice": [
		PURCHASE_INVOICE_SERIES,
		PURCHASE_RETURN_SERIES_OCT15,
		PURCHASE_DEBIT_NOTE_SERIES,
		PURCHASE_RETURN_SERIES,
		"P.purchase_warehouse_code.YY.MM.####",
		"ACC-PINV-.YYYY.-",
		"ACC-PINV-RET-.YYYY.-",
	],
	"Quotation": [QUOTATION_SERIES, "Q.YY.MM.####", "SAL-QTN-.YYYY.-"],
	"Journal Entry": [JOURNAL_ENTRY_SERIES, "ACC-JV-.YY.MM.", "ACC-JV-.YYYY.-"],
	"Sales Order": [SALES_ORDER_SERIES, "SAL-ORD-.YYYY.-"],
	"Stock Reconciliation": [STOCK_RECONCILIATION_SERIES, "MAT-RECO-.YYYY.-"],
	"Sales Invoice": [
		SALES_INVOICE_SERIES_OCT15,
		SALES_RETURN_SERIES_OCT15,
		SALES_WAREHOUSE_SERIES,
		SALES_RETURN_SERIES,
		SALES_NON_STOCK_SERIES_OCT15,
		SALES_NON_STOCK_SERIES,
		SALES_CREDIT_NOTE_SERIES,
		SALES_DEBIT_NOTE_SERIES,
		"ACC-SINV-.YYYY.-",
		"ACC-SINV-RET-.YYYY.-",
	],
}


def execute():
	for doctype, options in OPTIONS.items():
		frappe.reload_doctype(doctype)
		make_property_setter(doctype, "naming_series", "options", "\n".join(options), "Text")
		make_property_setter(doctype, "naming_series", "default", options[0], "Text")
		make_property_setter(doctype, "naming_series", "depends_on", "eval: 0", "Data")
		frappe.clear_cache(doctype=doctype)
