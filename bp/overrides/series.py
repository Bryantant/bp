"""Naming series patterns the before_naming hooks choose between.

The list of series offered on each doctype (naming_series options and default)
is a Property Setter owned by the site, edited in Customize Form. These
patterns only have to match an option that exists there.

	Sales Invoice with goods  INV- + warehouse code + YYMM + 4 digits     INV-A26100001
	Sales return with goods   SR- + warehouse code + YYMM + 4 digits      SR-A26100001
	Value-only Sales Invoice  ND- + YYMM + 4 digits                       ND-26100001
	Sales credit / debit note AR-NC- / AR-ND- + YYMM + 4 digits
	Purchase Invoice          PI-  + YYMM + 4 digits                      PI-26100001
	Purchase return, goods    PR-  + YYMM + 4 digits                      PR-26100001
	Purchase return, no goods AP-ND- + YYMM + 4 digits                    AP-ND-26100001
	Stock Entry               MI- / MO- / MA- / MR- by purpose            MI-26100001

Series with a warehouse code resolve the token through the
naming_series_variables hook in hooks.py. Documents named under the older
patterns below keep their names.
"""

STOCK_ENTRY_SERIES = {
	"Material Receipt": "MI-.YY.MM.####",
	"Material Issue": "MO-.YY.MM.####",
	"Repack": "MA-.YY.MM.####",
	"Material Transfer": "MR-.YY.MM.####",
}

PURCHASE_INVOICE_SERIES = "PI-.YY.MM.####"
PURCHASE_DEBIT_NOTE_SERIES = "AP-ND-.YY.MM.####"
PURCHASE_RETURN_SERIES_OCT15 = "PR-.YY.MM.####"
SALES_CREDIT_NOTE_SERIES = "AR-NC-.YY.MM.####"
SALES_DEBIT_NOTE_SERIES = "AR-ND-.YY.MM.####"
SALES_INVOICE_SERIES_OCT15 = "INV-.warehouse_name_code.YY.MM.####"
SALES_RETURN_SERIES_OCT15 = "SR-.warehouse_name_code.YY.MM.####"
SALES_NON_STOCK_SERIES_OCT15 = "ND-.YY.MM.####"

# Patterns used before 2026-10-17; before_naming still recognises them.
PURCHASE_SERIES = "P.purchase_warehouse_code.YY.MM.####"
PURCHASE_RETURN_SERIES = "PR.purchase_warehouse_code.YY.MM.####"
WAREHOUSE_SERIES = "warehouse_name_code.YY.MM.####"
SALES_RETURN_SERIES = "SR.warehouse_name_code.YY.MM.####"
