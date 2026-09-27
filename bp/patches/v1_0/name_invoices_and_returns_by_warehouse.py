"""Number purchases and all returns by warehouse code.

Decided 2026-09-27:
	Purchase Invoice   P  + warehouse code + YYMM + 4 digits   PA26090001
	Purchase return    PR + warehouse code + YYMM + 4 digits   PRA26090001
	Sales return       SR + warehouse code + YYMM + 4 digits   SRA26090001
	Sales Invoice      unchanged (warehouse code + YYMM + 4 digits)

Replaces P.invoice_type_code (PF/PC by Cash/Credit) and R.warehouse_name_code
(RA...). Documents already named keep their names; tabSeries counters are
keyed by the resolved prefix, so the new prefixes start their own counters.
The series are picked in bp.overrides.purchase_invoice.before_naming and
bp.overrides.sales_invoice.before_naming; the first option stays the default.

Idempotent: Property Setters are keyed by (doctype, fieldname, property).
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

PURCHASE_SERIES = "P.purchase_warehouse_code.YY.MM.####"
PURCHASE_RETURN_SERIES = "PR.purchase_warehouse_code.YY.MM.####"
SALES_RETURN_SERIES = "SR.warehouse_name_code.YY.MM.####"

# Kept literal here so the patch does not depend on later edits elsewhere.
SALES_WAREHOUSE_SERIES = "warehouse_name_code.YY.MM.####"
SALES_NON_STOCK_SERIES = "NDB-.YY.-.####"


def execute():
	frappe.reload_doctype("Purchase Invoice")
	frappe.reload_doctype("Sales Invoice")
	make_property_setter(
		doctype="Purchase Invoice",
		fieldname="naming_series",
		property="options",
		value="\n".join([PURCHASE_SERIES, PURCHASE_RETURN_SERIES, "ACC-PINV-.YYYY.-", "ACC-PINV-RET-.YYYY.-"]),
		property_type="Text",
	)
	make_property_setter(
		doctype="Sales Invoice",
		fieldname="naming_series",
		property="options",
		value="\n".join(
			[
				SALES_WAREHOUSE_SERIES,
				SALES_RETURN_SERIES,
				SALES_NON_STOCK_SERIES,
				"ACC-SINV-.YYYY.-",
				"ACC-SINV-RET-.YYYY.-",
			]
		),
		property_type="Text",
	)
	frappe.clear_cache(doctype="Purchase Invoice")
	frappe.clear_cache(doctype="Sales Invoice")
