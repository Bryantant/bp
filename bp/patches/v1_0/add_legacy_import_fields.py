"""Add old-system reference fields to Sales Invoice and Purchase Invoice.

Used by Legacy Import (bp.utils.legacy_import) during the migration week,
when documents are still typed into the old Access system and pulled into ERP
at the end of each day:

- custom_legacy_no: the old system's document number (DONumber / RecDOrNo).
  Dedupe key -- a legacy document already imported is never created twice --
  and searchable from the list view so staff can find an ERP invoice by the
  number printed on the old-system paper.
- custom_legacy_created_by: the old-system user who created it (CreaUser).
- custom_legacy_updated_at: the old system's LasUpdDt at import time. When a
  later import sees a newer LasUpdDt, the document is flagged "Changed in
  Legacy" for an admin to decide on.

Idempotent: create_custom_fields(update=True) is safe to re-run.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def _fields(insert_after):
	return [
		{
			"fieldname": "custom_legacy_no",
			"fieldtype": "Data",
			"label": "Old System No",
			"insert_after": insert_after,
			"read_only": 1,
			"no_copy": 1,
			"search_index": 1,
			"in_standard_filter": 1,
			"in_global_search": 1,
			"description": "Document number in the old system. Set by Legacy Import.",
		},
		{
			"fieldname": "custom_legacy_created_by",
			"fieldtype": "Data",
			"label": "Old System Created By",
			"insert_after": "custom_legacy_no",
			"read_only": 1,
			"no_copy": 1,
			"depends_on": "custom_legacy_no",
		},
		{
			"fieldname": "custom_legacy_updated_at",
			"fieldtype": "Datetime",
			"label": "Old System Last Updated",
			"insert_after": "custom_legacy_created_by",
			"read_only": 1,
			"no_copy": 1,
			"depends_on": "custom_legacy_no",
		},
	]


CUSTOM_FIELDS = {
	"Sales Invoice": _fields("custom_nd_invoice_no"),
	"Purchase Invoice": _fields("custom_invoice_type"),
}


def execute():
	frappe.reload_doctype("Sales Invoice")
	frappe.reload_doctype("Purchase Invoice")
	create_custom_fields(CUSTOM_FIELDS, update=True)
