"""Make Purchase Invoice behave like the old receiving screen (FmReceDeli).

The old system:
- let the received price differ from the PO price (the only price check was
  "Harga harus diisi lebih besar atau sama dengan 0");
- required "No. DO Supplier" and rejected a number already used by the same
  supplier (CekSuppDODupl).

In ERP terms:
- Buying Settings.maintain_same_rate off, so a PI made from a PO may carry
  another rate;
- Accounts Settings.check_supplier_invoice_uniqueness on (ERPNext checks the
  same supplier within one fiscal year; returns are skipped);
- Purchase Invoice.bill_no ("Supplier Invoice No") mandatory. Returns made
  with Create > Return / Debit Note copy it from the original invoice.

Idempotent: single values are set, the Property Setter is replaced on re-run.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	frappe.db.set_single_value("Buying Settings", "maintain_same_rate", 0)
	frappe.db.set_single_value("Accounts Settings", "check_supplier_invoice_uniqueness", 1)

	make_property_setter(
		doctype="Purchase Invoice",
		fieldname="bill_no",
		property="reqd",
		value="1",
		property_type="Check",
	)

	frappe.clear_cache(doctype="Purchase Invoice")
