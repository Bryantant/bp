"""Lock Purchase Invoice's Invoice Type field after the first save.

custom_invoice_type (see add_purchase_invoice_invoice_type_field.py) drives
the Cash/Credit naming code baked into the document name at insert (see
bp.overrides.purchase_invoice.get_invoice_type_code). Changing it after save
wouldn't retroactively rename the document, so the value and the name would
silently disagree -- lock it the same way core locks naming_series itself
(set_only_once: 1 on Purchase Invoice.naming_series).

Two properties, two different mechanisms:

- read_only_depends_on ("eval:!doc.__islocal", greys the field out once the
  document is no longer new) IS a real column on the Custom Field doctype,
  so it's set directly via create_custom_fields.

- set_only_once is NOT a column on the Custom Field doctype (only on core
  DocField), so setting it via create_custom_fields silently no-ops. It must
  go through a Property Setter instead: frappe.model.meta.Meta.process()
  runs add_custom_fields() (merges Custom Field records into self.fields)
  *before* apply_property_setters() (which then matches this Property
  Setter's field_name against that already-merged list and sets the
  property directly on the in-memory DocField object) -- so a DocField-type
  Property Setter reaches custom fields too, even though Custom Field's own
  schema doesn't expose set_only_once.

Idempotent: create_custom_fields(update=True) is safe to re-run, and
Property Setter records are keyed by (doctype, fieldname, property) --
PropertySetter.validate() deletes any existing record for that key before
inserting the new one.

Runs post_model_sync: needs the Purchase Invoice doctype's metadata already
migrated.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

CUSTOM_FIELDS = {
	"Purchase Invoice": [
		{
			"fieldname": "custom_invoice_type",
			"read_only_depends_on": "eval:!doc.__islocal",
		},
	]
}


def execute():
	frappe.reload_doctype("Purchase Invoice")
	create_custom_fields(CUSTOM_FIELDS, update=True)
	make_property_setter(
		doctype="Purchase Invoice",
		fieldname="custom_invoice_type",
		property="set_only_once",
		value="1",
		property_type="Check",
	)
