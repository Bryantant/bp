"""Prefix Purchase Invoice's Cash/Credit naming series with a literal "P".

Fixes a naming collision with Sales Invoice: both doctypes previously
resolved their custom naming-series token to a single letter --
``invoice_type_code`` on Purchase Invoice maps Cash/Credit to "C"/"F"
(bp.overrides.purchase_invoice.get_invoice_type_code), and
``warehouse_name_code`` on Sales Invoice resolves to the Source Warehouse's
name, which can also be a single letter (e.g. Warehouse "C"). Frappe's
naming counter (`tabSeries`) is keyed purely by the resolved prefix string
with no doctype column (frappe.model.naming.getseries), so whenever both
resolved to "C" in the same year/month the two doctypes silently shared one
counter -- a Cash Purchase Invoice created after a Sales Invoice from
Warehouse C (or vice versa) would skip a number instead of continuing its
own sequence.

Fix: add a literal "P" as its own dot-separated segment at the front of the
series. Naming-series dots are pure delimiters (stripped when the name is
resolved, never reinserted -- see frappe.model.naming.parse_naming_series),
and any segment that isn't a recognised token/date part is emitted as a
literal (parse_naming_series' final `else: part = e` branch), so
"P.invoice_type_code.YY.MM.####" resolves to a plain string like
PC26070001 / PF26070001 -- two letters that cannot collide with any current
or foreseeable single-letter Warehouse name (A/B/C/D, and any future
warehouse such as "KS").

Purchase Invoices already created under the old "C"/"F" naming keep their
existing name (naming is immutable after insert); only new ones from this
patch onward get the "P"-prefixed series.

Idempotent: Property Setter records are keyed by (doctype, fieldname,
property), and PropertySetter.validate() deletes any existing record for
that key before inserting the new one, so re-running this patch just
re-applies the same options string.

Runs post_model_sync: needs the Purchase Invoice doctype's metadata already
migrated.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

NAMING_SERIES_OPTIONS = "\n".join(
	[
		"P.invoice_type_code.YY.MM.####",
		"ACC-PINV-.YYYY.-",
		"ACC-PINV-RET-.YYYY.-",
	]
)


def execute():
	frappe.reload_doctype("Purchase Invoice")
	make_property_setter(
		doctype="Purchase Invoice",
		fieldname="naming_series",
		property="options",
		value=NAMING_SERIES_OPTIONS,
		property_type="Text",
	)
