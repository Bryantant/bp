"""Backfill BP Naming Counter from existing Customer / Supplier names.

After bulk imports, customers and suppliers were inserted with explicit names
(e.g. C0275, A0030) but no naming counter was ever advanced. This seeds one
``BP Naming Counter`` row per (doctype, prefix) at the highest number already
in use, so newly created records continue the sequence instead of colliding
with imported ones.

Idempotent: inserts missing rows and only raises an existing ``current_value``
(never lowers it), so an admin's manual adjustments are preserved.
"""

import re
from collections import defaultdict

import frappe
from frappe.utils import cint

# Only letter-prefixed codes participate in the initial+counter scheme.
# Legacy numeric-only codes (e.g. 90003) are intentionally ignored.
NAME_PATTERN = re.compile(r"^([A-Za-z]+)(\d+)$")


def execute():
	for doctype in ("Customer", "Supplier"):
		maxima = defaultdict(int)
		for (name,) in frappe.db.sql("SELECT name FROM `tab{0}`".format(doctype)):
			match = NAME_PATTERN.match(name or "")
			if match:
				prefix = match.group(1).upper()
				maxima[prefix] = max(maxima[prefix], int(match.group(2)))

		for prefix, value in maxima.items():
			counter_name = "{0}-{1}".format(doctype, prefix)
			if frappe.db.exists("BP Naming Counter", counter_name):
				current = cint(frappe.db.get_value("BP Naming Counter", counter_name, "current_value"))
				if current < value:
					frappe.db.set_value("BP Naming Counter", counter_name, "current_value", value)
			else:
				frappe.get_doc(
					{
						"doctype": "BP Naming Counter",
						"document_type": doctype,
						"prefix": prefix,
						"current_value": value,
					}
				).insert(ignore_permissions=True)

	frappe.db.commit()
