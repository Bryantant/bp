"""Invoice Belum Kembali (HT-42): Sales Invoices not yet brought back by the
salesman, per salesman, with their age in days. Status "Sudah kembali" or
"Semua" shows the returned ones too, with when, by whom and the Invoice
Kembali form.

Same invoices as the Invoice Kembali form tracks: submitted, not a return /
credit note, not an ND invoice. From Date defaults to BP Settings > Invoice
Kembali Start Date (go-live), so migrated invoices do not flood the list.
"""

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return columns(), data(filters)


def columns():
	return [
		{"label": _("Sales Invoice"), "fieldname": "name", "fieldtype": "Link", "options": "Sales Invoice", "width": 160},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		# Data, not Int: the total row would add the ages up
		{"label": _("Age (Days)"), "fieldname": "age", "fieldtype": "Data", "width": 80},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 90},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 220},
		{"label": _("Salesman"), "fieldname": "sales_person", "fieldtype": "Link", "options": "Sales Person", "width": 140},
		{"label": _("Grand Total"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 130},
		{"label": _("Outstanding"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Kembali At"), "fieldname": "kembali_at", "fieldtype": "Datetime", "width": 150},
		{"label": _("Kembali By"), "fieldname": "kembali_by", "fieldtype": "Link", "options": "User", "width": 140},
		{"label": _("Invoice Kembali"), "fieldname": "kembali_ref", "fieldtype": "Link", "options": "Invoice Kembali", "width": 120},
	]


def data(filters):
	si = frappe.qb.DocType("Sales Invoice")
	q = (
		frappe.qb.from_(si)
		.select(
			si.name,
			si.posting_date,
			si.customer,
			si.customer_name,
			si.bp_sales_person.as_("sales_person"),
			si.grand_total,
			si.outstanding_amount,
			si.bp_kembali_at.as_("kembali_at"),
			si.bp_kembali_by.as_("kembali_by"),
			si.bp_kembali_ref.as_("kembali_ref"),
		)
		.where(si.docstatus == 1)
		.where(si.is_return == 0)
		.where((si.custom_nd_invoice_no.isnull()) | (si.custom_nd_invoice_no == ""))
		.orderby(si.bp_sales_person)
		.orderby(si.posting_date)
		.orderby(si.name)
	)
	if filters.company:
		q = q.where(si.company == filters.company)
	if filters.from_date:
		q = q.where(si.posting_date >= filters.from_date)
	if filters.to_date:
		q = q.where(si.posting_date <= filters.to_date)
	if filters.sales_person:
		q = q.where(si.bp_sales_person == filters.sales_person)
	if filters.customer:
		q = q.where(si.customer == filters.customer)

	status = filters.status or "Belum kembali"
	if status == "Belum kembali":
		q = q.where(si.bp_invoice_kembali == 0)
	elif status == "Sudah kembali":
		q = q.where(si.bp_invoice_kembali == 1)

	rows = q.run(as_dict=True)
	as_of = getdate(today())
	for row in rows:
		end = getdate(row.kembali_at) if row.kembali_at else as_of
		row.age = str(date_diff(end, row.posting_date))
	return rows


@frappe.whitelist()
def default_from_date():
	return frappe.db.get_single_value("BP Settings", "invoice_kembali_start_date")
