"""Delivery Note numbers start with SJ- instead of DO- (Bry 2026-10-19):
SJ- + warehouse code + YYMM + 4 digits, e.g. SJ-A26100001. The Sales Invoice
print that used to show SJ- now shows DO- (rename_surat_jalan_print_format),
so the two never print the same number.

Notes already named DO-... keep their names. The DO- series stays in the list
after the default so those names remain valid in filters and amendments.

Idempotent: Property Setters are keyed by (doctype, fieldname, property).
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from bp.patches.v1_0.apply_document_numbering_oct15 import DELIVERY_NOTE_SERIES as OLD_SERIES

SERIES = "SJ-.warehouse_name_code.YY.MM.####"
OPTIONS = [SERIES, OLD_SERIES, "MAT-DN-.YYYY.-", "MAT-DN-RET-.YYYY.-"]


def execute():
	make_property_setter("Delivery Note", "naming_series", "options", "\n".join(OPTIONS), "Text")
	make_property_setter("Delivery Note", "naming_series", "default", SERIES, "Text")
	frappe.clear_cache(doctype="Delivery Note")
