"""Master and mapping lookups shared by the legacy document builders.

Loaded once per batch and prefetched for every code the batch touches, so
building thousands of documents does not cost thousands of single-row
queries.

Master data is NOT created here: customers, suppliers, items and sales
persons are migrated separately, so a legacy code without an ERP record
makes the document fail with a clear message instead.

Receipts and payments also need to find ERP documents created earlier --
possibly earlier in the same batch (a receipt paying an invoice imported a
minute ago). Those lookups therefore go to the database on demand and only
cache hits; a miss is looked up again next time.
"""

import frappe
from frappe.utils import flt

from bp.utils.legacy_import import (
	AP_PAYMENT,
	AR_RECEIPT,
	PURCHASE_INVOICE,
	SALES_INVOICE,
	SALES_RETURN,
	SALES_RETURN_METHOD,
)

CUSTOMER_KINDS = (SALES_INVOICE, SALES_RETURN, AR_RECEIPT)
SUPPLIER_KINDS = (PURCHASE_INVOICE, AP_PAYMENT)

# What a resolver returns during a Preview for a target that this same batch
# is about to create: it does not exist yet, but it is not an error either.
PENDING = "__pending__"


def _code(value):
	return (value or "").strip()


def is_nd_invoice_no(invoice_no):
	"""ND System invoices are "I" + 9 digits (I260900187); invoices from a
	delivery order are "I" + the DO number, which carries a letter (IC26090149)."""
	return len(invoice_no) == 10 and invoice_no[0] == "I" and invoice_no[1:].isdigit()


class ImportContext:
	def __init__(self):
		settings = frappe.get_single("BP Settings")
		self.company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
			"Global Defaults", "default_company"
		)
		self.company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
		self.cost_center = frappe.get_cached_value("Company", self.company, "cost_center")
		self.tolerance = flt(settings.get("legacy_amount_tolerance"))
		self.warehouse_map = {
			_code(row.branch_code).upper(): row.warehouse for row in settings.get("legacy_warehouse_map") or []
		}
		self.method_overrides = {
			_code(row.legacy_method): row.account for row in settings.get("legacy_payment_method_map") or []
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
		# Legacy payment methods (methodtabldt), loaded by the runner with the
		# legacy connection it already has open.
		self.payment_methods = {}
		self._accounts_by_number = None
		self._found = {}
		self._stock_entry_types = {}
		# Old system's average cost per item (source.fetch_legacy_costs), loaded
		# by the runner for the items a batch's returns touch.
		self.legacy_costs = {}
		# (kind, legacy_no) the current Preview would create -- see PENDING.
		self.pending = set()

	def prefetch(self, legacy_docs):
		customers = {_code(d["party"]) for d in legacy_docs if d["kind"] in CUSTOMER_KINDS}
		suppliers = {_code(d["party"]) for d in legacy_docs if d["kind"] in SUPPLIER_KINDS}
		items = {_code(line["ItemCode"]) for d in legacy_docs for line in d["lines"] if line.get("ItemCode")}

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

	# -- masters ----------------------------------------------------------

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

	def stock_entry_type(self, purpose):
		"""The site's Stock Entry Type for a purpose, or None.

		Looked up by purpose, never by name: sites rename the standard types
		(on bp.localhost they are Barang Masuk / Barang Keluar / Relokasi Barang).
		"""
		if purpose not in self._stock_entry_types:
			self._stock_entry_types[purpose] = frappe.db.get_value(
				"Stock Entry Type", {"purpose": purpose}, "name", order_by="is_standard desc, creation asc"
			)
		return self._stock_entry_types[purpose]

	def missing_valuation_rate(self, item_code, warehouse, posting_date):
		"""Rate for goods coming into a warehouse ERP cannot value, or None.

		None means ERP values the line itself: the item already has a valuation
		in that warehouse. Otherwise ERP refuses the document ("Valuation Rate
		... is required") -- a standalone return into GS/BR, which only ever
		receive returns, or a stock-in mutation typed with no price. The old
		system kept one average cost per item, not per warehouse, so the same
		rule applies here: the item's latest ERP valuation in any warehouse of
		the company as of the date, then the old system's average cost, then
		the Item's own valuation rate; 0 when there is none at all. Rates are
		per stock unit.
		"""
		key = (item_code, warehouse, posting_date)
		if key in self._found:
			return self._found[key]
		sle = frappe.qb.DocType("Stock Ledger Entry")

		def latest(*conditions):
			query = (
				frappe.qb.from_(sle)
				.select(sle.valuation_rate)
				.where(
					(sle.item_code == item_code)
					& (sle.company == self.company)
					& (sle.is_cancelled == 0)
					& (sle.posting_date <= posting_date)
					& (sle.valuation_rate > 0)
				)
				.orderby(sle.posting_datetime, order=frappe.qb.desc)
				.orderby(sle.creation, order=frappe.qb.desc)
				.limit(1)
			)
			for condition in conditions:
				query = query.where(condition)
			rows = query.run()
			return flt(rows[0][0]) if rows else 0

		if latest(sle.warehouse == warehouse):
			rate = None  # ERP finds it itself
		else:
			rate = (
				latest()
				or self.legacy_costs.get(item_code)
				or flt(frappe.get_cached_value("Item", item_code, "valuation_rate"))
				or 0
			)
		self._found[key] = rate
		return rate

	# -- payment methods -> ERP accounts ------------------------------------

	def method_account(self, method, currency):
		"""ERP account for a legacy payment method, or None.

		BP Settings' Payment Method Map wins; otherwise the method's legacy GL
		account (methodtabldt.Accid) is matched to the ERP account with the
		same account_number -- this site's chart kept the old numbers.
		"""
		method = _code(method)
		if method in self.method_overrides:
			return self.method_overrides[method]
		legacy = self.payment_methods.get((method, _code(currency) or self.company_currency))
		if not legacy or not legacy["accid"]:
			return None
		return self._account_numbers().get(legacy["accid"])

	def is_return_method(self, method, currency):
		legacy = self.payment_methods.get((_code(method), _code(currency) or self.company_currency))
		return _code(method) == SALES_RETURN_METHOD or bool(legacy and legacy["retur"])

	def _account_numbers(self):
		if self._accounts_by_number is None:
			self._accounts_by_number = {
				row.account_number: row.name
				for row in frappe.get_all(
					"Account",
					filters={"company": self.company, "is_group": 0, "account_number": ["is", "set"]},
					fields=["name", "account_number"],
				)
			}
		return self._accounts_by_number

	# -- documents this or an earlier batch created --------------------------

	def invoice_for(self, doctype, legacy_invoice_no, import_kind):
		"""The submitted ERP invoice a legacy AR/AP document number points at.

		Three places it can be: an opening invoice, named after the legacy number
		itself (bp.utils.import_legacy_opening_invoices); an ND System invoice
		brought in with Import ND Invoice, which keeps the ND number -- the old
		system stored that same number as InvoicNo (qFmImportSlsAppInv); or an
		invoice imported from its delivery order/receiving, whose legacy
		invoice number is "I" + the document number (see source.SPECS).
		"""
		legacy_invoice_no = _code(legacy_invoice_no)
		key = (doctype, legacy_invoice_no)
		if key in self._found:
			return self._found[key]

		found = None
		if frappe.db.get_value(doctype, {"name": legacy_invoice_no, "docstatus": 1}):
			found = legacy_invoice_no
		elif doctype == "Sales Invoice" and is_nd_invoice_no(legacy_invoice_no):
			found = frappe.db.get_value(
				doctype, {"custom_nd_invoice_no": legacy_invoice_no, "docstatus": 1}
			)
		elif legacy_invoice_no.startswith("I"):
			found = self._imported(doctype, import_kind, legacy_invoice_no[1:])
			if not found and (import_kind, legacy_invoice_no[1:]) in self.pending:
				return PENDING
		if found:
			self._found[key] = found
		return found

	def sales_return_for(self, legacy_return_no):
		legacy_return_no = _code(legacy_return_no)
		if not legacy_return_no:
			return None
		key = ("Sales Invoice", "return", legacy_return_no)
		if key in self._found:
			return self._found[key]
		found = self._imported("Sales Invoice", SALES_RETURN, legacy_return_no)
		if not found and (SALES_RETURN, legacy_return_no) in self.pending:
			return PENDING
		if found:
			self._found[key] = found
		return found

	def return_credit(self, name):
		"""(customer, credit still unapplied) of an imported return -- read fresh,
		since receipts earlier in the run use it up."""
		customer, outstanding = frappe.db.get_value("Sales Invoice", name, ["customer", "outstanding_amount"])
		return customer, -flt(outstanding)

	def _imported(self, doctype, kind, legacy_no):
		return frappe.db.get_value(
			doctype,
			{"custom_legacy_type": kind, "custom_legacy_no": legacy_no, "docstatus": 1},
		)

	def party_account(self, doctype, name):
		"""debit_to / credit_to of an invoice, so the JE row matches it exactly."""
		field = "debit_to" if doctype == "Sales Invoice" else "credit_to"
		return frappe.db.get_value(doctype, name, field)
