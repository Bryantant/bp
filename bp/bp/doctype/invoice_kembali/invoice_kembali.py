"""Invoice Kembali: Sales Invoices brought back to head office by the salesmen
who took them out to collect payment (HT-42, meeting MULYADI 15 Okt 2026).

Each row is one invoice, added by scanning the Code 128 barcode on the Sales
Invoice / Delivery Order print (bp/utils/barcode.py) or by typing its number.
Submit marks every invoice as returned (Sales Invoice.bp_invoice_kembali and
the who/when/which fields); Cancel clears them again. The report "Invoice
Belum Kembali" lists the invoices not yet marked.

Tracked invoices: submitted Sales Invoices that are not returns/credit notes
and not ND invoices (Import ND Invoice, custom_nd_invoice_no set).
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import format_datetime, now_datetime

SI_FIELDS = ["name", "docstatus", "is_return", "custom_nd_invoice_no", "posting_date", "customer",
	"customer_name", "bp_sales_person", "grand_total", "outstanding_amount", "company",
	"bp_invoice_kembali", "bp_kembali_at", "bp_kembali_by", "bp_kembali_ref"]


class InvoiceKembali(Document):
	def validate(self):
		seen = set()
		for row in self.invoices:
			if row.sales_invoice in seen:
				frappe.throw(_("Row {0}: Sales Invoice {1} is listed twice.").format(row.idx, row.sales_invoice))
			seen.add(row.sales_invoice)
			si = frappe.db.get_value("Sales Invoice", row.sales_invoice, SI_FIELDS, as_dict=True)
			error = invoice_error(si, self.name)
			if error:
				frappe.throw(_("Row {0}: {1}").format(row.idx, error))
			if si.company != self.company:
				frappe.throw(_("Row {0}: Sales Invoice {1} belongs to company {2}.").format(row.idx, si.name, si.company))
			row.update(row_values(si))
			row.scanned_at = row.scanned_at or now_datetime()
		self.total_invoices = len(self.invoices)
		self.scan_invoice = None

	def before_submit(self):
		if not self.invoices:
			frappe.throw(_("Scan at least one Sales Invoice."))

	def on_submit(self):
		at, by = now_datetime(), frappe.session.user
		for row in self.invoices:
			frappe.db.set_value(
				"Sales Invoice",
				row.sales_invoice,
				{"bp_invoice_kembali": 1, "bp_kembali_at": at, "bp_kembali_by": by, "bp_kembali_ref": self.name},
				update_modified=False,
			)

	def on_cancel(self):
		for row in self.invoices:
			if frappe.db.get_value("Sales Invoice", row.sales_invoice, "bp_kembali_ref") == self.name:
				frappe.db.set_value(
					"Sales Invoice",
					row.sales_invoice,
					{"bp_invoice_kembali": 0, "bp_kembali_at": None, "bp_kembali_by": None, "bp_kembali_ref": None},
					update_modified=False,
				)


def invoice_error(si, current=None):
	"""Why this Sales Invoice cannot be marked returned, or None if it can."""
	if not si:
		return _("Sales Invoice not found.")
	if si.docstatus != 1:
		return _("Sales Invoice {0} is not submitted.").format(si.name) if si.docstatus == 0 else _(
			"Sales Invoice {0} is cancelled."
		).format(si.name)
	if si.is_return:
		return _("{0} is a return / credit note and is not tracked.").format(si.name)
	if si.custom_nd_invoice_no:
		return _("{0} is an ND invoice and is not tracked.").format(si.name)
	if si.bp_invoice_kembali and si.bp_kembali_ref != current:
		return _("Sales Invoice {0} was already returned on {1} by {2} ({3}).").format(
			si.name,
			format_datetime(si.bp_kembali_at, "dd-MM-yyyy HH:mm"),
			frappe.utils.get_fullname(si.bp_kembali_by),
			si.bp_kembali_ref,
		)
	return None


def row_values(si):
	return {
		"posting_date": si.posting_date,
		"customer": si.customer,
		"customer_name": si.customer_name,
		"sales_person": si.bp_sales_person,
		"grand_total": si.grand_total,
		"outstanding_amount": si.outstanding_amount,
	}


def find_invoice(value):
	"""Sales Invoice name for a scanned or typed value: the invoice name (what the
	barcode holds), else the legacy number of a migrated invoice."""
	value = (value or "").strip()
	if not value:
		return None
	for candidate in (value, value.upper()):
		if frappe.db.exists("Sales Invoice", candidate):
			return candidate
	return frappe.db.get_value("Sales Invoice", {"custom_legacy_no": value.upper(), "docstatus": 1}, "name")


@frappe.whitelist()
def resolve_invoice(value, company=None, current=None):
	"""Called by the Scan Invoice field: the row values for the scanned invoice,
	or {"error": message} when it cannot be added."""
	frappe.has_permission("Invoice Kembali", "write", throw=True)
	name = find_invoice(value)
	si = frappe.db.get_value("Sales Invoice", name, SI_FIELDS, as_dict=True) if name else None
	if not si:
		return {"error": _("Sales Invoice {0} not found.").format(frappe.bold(value))}
	error = invoice_error(si, current)
	if not error and company and si.company != company:
		error = _("Sales Invoice {0} belongs to company {1}.").format(si.name, si.company)
	if error:
		return {"error": error}
	return {"sales_invoice": si.name, "scanned_at": now_datetime(), **row_values(si)}
