# Copyright (c) 2026, Hicom System and contributors
# For license information, please see license.txt

"""Doctype-scoped naming for Customer and Supplier.

Both doctypes name documents as <initial-letter><4-digit counter> (e.g. C0276).
Frappe's built-in ``tabSeries`` counter is keyed only by the resolved prefix
string, with no doctype awareness, so a Customer "C" and a Supplier "C" would
share one counter and interleave. To keep the identical visible format while
giving each doctype its own independent, admin-controllable counter, we set
``doc.name`` here from the ``BP Naming Counter`` DocType.

Wired via ``doc_events`` ``autoname`` in hooks.py. ``set_new_name`` runs
``doc.run_method("autoname")`` (which composes the ERPNext controller's own
autoname *then* this hook) before the ``naming_series:`` branch, and that
branch only runs when ``doc.name`` is still empty -- so setting ``doc.name``
here cleanly bypasses ``tabSeries``.

The initial is normally pre-filled client-side (see the "Customer Naming"
Client Script) from the first character of the title field, so users see it
before saving. That client script never runs for documents created via the
REST API, Data Import Tool, or other server-side code, so this module
mirrors the same first-character derivation as a fallback when the field is
still blank at save time -- callers no longer need to know about the
internal initial field to create a Customer/Supplier programmatically.
"""

import re

import frappe
from frappe import _
from frappe.utils import cint

# Field on each doctype holding the initial letter used as the name prefix.
INITIAL_FIELD = {"Customer": "custom_cn_initial", "Supplier": "custom_initial"}
# Field the initial is derived from when not already set (matches each
# doctype's title_field).
SOURCE_FIELD = {"Customer": "customer_name", "Supplier": "supplier_name"}
PAD = 4  # matches the existing #### format


def autoname(doc, method=None):
	field = INITIAL_FIELD.get(doc.doctype)
	if not field:
		return
	initial = (doc.get(field) or "").strip().upper()
	if not initial:
		source = (doc.get(SOURCE_FIELD.get(doc.doctype)) or "").strip()
		initial = source[0].upper() if source else ""
		if initial:
			doc.set(field, initial)
	if not initial:
		frappe.throw(
			_("Initial ({0}) is required to generate the {1} code.").format(field, doc.doctype)
		)
	number = _next_value(doc.doctype, initial)
	doc.name = "{0}{1:0{2}d}".format(initial, number, PAD)


def _next_value(doctype, initial):
	"""Atomically return the next counter value for (doctype, initial).

	Uses a row-level lock (SELECT ... FOR UPDATE), mirroring Frappe's own
	``frappe.model.naming.getseries``. Seeds an unseen prefix from the highest
	number already present in the target table so generated codes never
	collide with previously imported records.
	"""
	counter_name = "{0}-{1}".format(doctype, initial)
	row = frappe.db.sql(
		"SELECT current_value FROM `tabBP Naming Counter` WHERE name=%s FOR UPDATE",
		counter_name,
	)
	if row:
		new_value = cint(row[0][0]) + 1
		frappe.db.sql(
			"UPDATE `tabBP Naming Counter` SET current_value=%s WHERE name=%s",
			(new_value, counter_name),
		)
	else:
		new_value = _current_max(doctype, initial) + 1
		frappe.get_doc(
			{
				"doctype": "BP Naming Counter",
				"document_type": doctype,
				"prefix": initial,
				"current_value": new_value,
			}
		).insert(ignore_permissions=True)
	return new_value


def _current_max(doctype, initial):
	"""Highest <initial><digits> number already used in the target table."""
	rows = frappe.db.sql(
		"SELECT name FROM `tab{0}` WHERE name LIKE %s".format(doctype),
		initial + "%",
	)
	pattern = re.compile(r"^" + re.escape(initial) + r"(\d+)$")
	maximum = 0
	for (name,) in rows:
		match = pattern.match(name or "")
		if match:
			maximum = max(maximum, int(match.group(1)))
	return maximum
