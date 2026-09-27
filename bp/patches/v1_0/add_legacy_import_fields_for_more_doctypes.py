"""Legacy reference fields for the documents Legacy Import now also creates.

Legacy Import brings in sales returns, stock mutations, set assemblies, AR
receipts and AP payments as well as delivery orders and receivings. Their
legacy numbers repeat across kinds -- a return and a set share the yymm+####
format, both stock kinds become Stock Entries, AR receipts and AP payments
both become Journal Entries -- so the legacy number alone no longer
identifies a document. custom_legacy_type (the kind, as in
bp.utils.legacy_import.kinds) is added next to it and deduplication matches
on the pair.

- Sales Invoice, Purchase Invoice: add custom_legacy_type and fill it for
  documents imported before it existed.
- Stock Entry, Journal Entry: add the full set (type, no, created by, last
  updated).

Idempotent: create_custom_fields(update=True) and a backfill that only
touches rows still missing the type.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def _type_field(insert_after):
	return {
		"fieldname": "custom_legacy_type",
		"fieldtype": "Data",
		"label": "Old System Document Type",
		"insert_after": insert_after,
		"read_only": 1,
		"no_copy": 1,
		"search_index": 1,
		"in_standard_filter": 1,
		"depends_on": "custom_legacy_no",
	}


def _full_set(insert_after):
	return [
		{
			"fieldname": "custom_legacy_section",
			"fieldtype": "Section Break",
			"label": "Old System",
			"insert_after": insert_after,
			"collapsible": 1,
			"depends_on": "custom_legacy_no",
		},
		{
			"fieldname": "custom_legacy_no",
			"fieldtype": "Data",
			"label": "Old System No",
			"insert_after": "custom_legacy_section",
			"read_only": 1,
			"no_copy": 1,
			"search_index": 1,
			"in_standard_filter": 1,
			"in_global_search": 1,
			"description": "Document number in the old system. Set by Legacy Import.",
		},
		_type_field("custom_legacy_no"),
		{
			"fieldname": "custom_legacy_created_by",
			"fieldtype": "Data",
			"label": "Old System Created By",
			"insert_after": "custom_legacy_type",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "custom_legacy_updated_at",
			"fieldtype": "Datetime",
			"label": "Old System Last Updated",
			"insert_after": "custom_legacy_created_by",
			"read_only": 1,
			"no_copy": 1,
		},
	]


CUSTOM_FIELDS = {
	"Sales Invoice": [_type_field("custom_legacy_updated_at")],
	"Purchase Invoice": [_type_field("custom_legacy_updated_at")],
	"Stock Entry": _full_set("remarks"),
	# After the usage guide (add_journal_entry_usage_guide), which sits right
	# under the remarks and should stay there.
	"Journal Entry": _full_set("custom_usage_guide"),
}


def execute():
	for doctype in CUSTOM_FIELDS:
		frappe.reload_doctype(doctype)
	create_custom_fields(CUSTOM_FIELDS, update=True)

	frappe.db.sql(
		"""UPDATE `tabSales Invoice`
		SET custom_legacy_type = IF(is_return, 'Sales Return', 'Sales Invoice')
		WHERE IFNULL(custom_legacy_no, '') != '' AND IFNULL(custom_legacy_type, '') = ''"""
	)
	frappe.db.sql(
		"""UPDATE `tabPurchase Invoice`
		SET custom_legacy_type = 'Purchase Invoice'
		WHERE IFNULL(custom_legacy_no, '') != '' AND IFNULL(custom_legacy_type, '') = ''"""
	)
