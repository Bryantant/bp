"""Discount 1/2 % and Amount become four separate steps.

Until now each percentage and the amount next to it were one discount typed
two ways, and the browser, the legacy importer and the save hook always
filled in both. Under the new rule (bp.utils.cascading_discount) both would be
taken, so every row that has both would be discounted twice the next time it
is saved.

For those rows the amount is only the percentage in money: clear it and keep
the percentage, which is what the user typed or what the old system held.
Rate and totals are not touched, so submitted invoices keep their values.

Also refreshes the field descriptions to say which step each field is.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from bp.patches.v1_0.add_item_cascading_discount_fields import CUSTOM_FIELDS


def execute():
	create_custom_fields(CUSTOM_FIELDS, update=True)

	for doctype in CUSTOM_FIELDS:
		for tier in (1, 2):
			pct, amount = f"custom_discount{tier}_percentage", f"custom_discount{tier}_amount"
			frappe.db.sql(
				f"""update `tab{doctype}` set `{amount}` = 0
				where ifnull(`{pct}`, 0) != 0 and ifnull(`{amount}`, 0) != 0"""
			)
