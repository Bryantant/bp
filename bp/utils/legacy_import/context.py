"""Master and mapping lookups shared by the legacy document builders.

Loaded once per batch and prefetched for every code the batch touches, so
building ~300 invoices does not cost thousands of single-row queries.

Master data is NOT created here: customers, suppliers, items and sales
persons are migrated separately, so a legacy code without an ERP record
makes the document fail with a clear message instead.
"""

import frappe
from frappe.utils import flt

from bp.utils.legacy_import import PURCHASE_INVOICE, SALES_INVOICE


def _code(value):
	return (value or "").strip()


class ImportContext:
	def __init__(self):
		settings = frappe.get_single("BP Settings")
		self.company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
			"Global Defaults", "default_company"
		)
		self.company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
		self.tolerance = flt(settings.get("legacy_amount_tolerance"))
		self.warehouse_map = {
			_code(row.branch_code).upper(): row.warehouse for row in settings.get("legacy_warehouse_map") or []
		}
		self.sales_person_map = {
			_code(sp.custom_code).upper(): sp.name
			for sp in frappe.get_all(
				"Sales Person", filters={"enabled": 1, "custom_code": ["is", "set"]}, fields=["name", "custom_code"]
			)
		}
		self.uom_map = {name.lower(): name for name in frappe.get_all("UOM", pluck="name")}
		self.customers = set()
		self.suppliers = set()
		self.items = {}

	def prefetch(self, legacy_docs):
		customers = {_code(d["party"]) for d in legacy_docs if d["doctype"] == SALES_INVOICE}
		suppliers = {_code(d["party"]) for d in legacy_docs if d["doctype"] == PURCHASE_INVOICE}
		items = {_code(line["ItemCode"]) for d in legacy_docs for line in d["lines"]}

		if customers:
			self.customers |= set(
				frappe.get_all("Customer", filters={"name": ["in", list(customers)], "disabled": 0}, pluck="name")
			)
		if suppliers:
			self.suppliers |= set(
				frappe.get_all("Supplier", filters={"name": ["in", list(suppliers)], "disabled": 0}, pluck="name")
			)
		if items:
			for row in frappe.get_all(
				"Item",
				filters={"name": ["in", list(items)], "disabled": 0},
				fields=["name", "item_name"],
			):
				self.items[row.name] = row.item_name
		return self

	def warehouse(self, branch_code):
		return self.warehouse_map.get(_code(branch_code).upper())

	def sales_person(self, sale_code):
		return self.sales_person_map.get(_code(sale_code).upper())

	def uom(self, unit):
		return self.uom_map.get(_code(unit).lower())

	def has_customer(self, code):
		return _code(code) in self.customers

	def has_supplier(self, code):
		return _code(code) in self.suppliers

	def item_name(self, code):
		return self.items.get(_code(code))

	def check_currency(self, currency, problems):
		currency = _code(currency)
		if currency and currency != self.company_currency:
			problems.append(f"Currency {currency} is not supported by the import (only {self.company_currency})")

	def check_lines(self, lines, problems):
		"""Validate item/UOM for every line with a quantity; returns the usable lines."""
		usable = []
		for line in lines:
			if flt(line["Quantity"]) <= 0:
				continue
			row = f"row {line.get('RowNumber') or line.get('SequNumb')}"
			if not self.item_name(line["ItemCode"]):
				problems.append(f"{row}: item {_code(line['ItemCode'])} not found or disabled")
			if not self.uom(line["UnitMeas"]):
				problems.append(f"{row}: UOM {_code(line['UnitMeas'])} not found")
			usable.append(line)
		if not usable:
			problems.append("no lines with a quantity")
		return usable
