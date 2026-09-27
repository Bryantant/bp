import frappe
from frappe.tests import IntegrationTestCase

from bp.overrides.sales_invoice import before_naming, get_warehouse_name_code
from bp.patches.v1_0.allow_non_stock_sales_invoices import NON_STOCK_SERIES, WAREHOUSE_SERIES


def invoice(**kw):
	doc = frappe._dict(
		{"naming_series": WAREHOUSE_SERIES, "update_stock": 1, "set_warehouse": "A - BP", "is_opening": "No"}
	)
	doc.update(kw)
	return doc


class IntegrationTestSalesInvoiceRules(IntegrationTestCase):
	# -- naming series --------------------------------------------------------

	def test_value_only_invoice_gets_its_own_series(self):
		"""A debit note for a principal's claim moves no goods, so the
		warehouse-based series has nothing to resolve."""
		doc = invoice(update_stock=0, set_warehouse=None)
		before_naming(doc)
		self.assertEqual(doc.naming_series, NON_STOCK_SERIES)

	def test_goods_invoice_keeps_the_warehouse_series(self):
		doc = invoice()
		before_naming(doc)
		self.assertEqual(doc.naming_series, WAREHOUSE_SERIES)

	def test_update_stock_decides_not_the_empty_warehouse(self):
		"""A goods invoice with an empty header warehouse keeps the warehouse
		series; the code comes from its item rows."""
		doc = invoice(set_warehouse=None)
		before_naming(doc)
		self.assertEqual(doc.naming_series, WAREHOUSE_SERIES)

	def test_a_series_picked_deliberately_is_left_alone(self):
		doc = invoice(update_stock=0, set_warehouse=None, naming_series="ACC-SINV-.YYYY.-")
		before_naming(doc)
		self.assertEqual(doc.naming_series, "ACC-SINV-.YYYY.-")

	def test_opening_invoice_is_not_touched(self):
		"""It is named after the legacy invoice number before it gets here."""
		doc = invoice(update_stock=0, set_warehouse=None, is_opening="Yes")
		before_naming(doc)
		self.assertEqual(doc.naming_series, WAREHOUSE_SERIES)

	# -- warehouse code for the name ------------------------------------------

	def test_code_comes_from_the_header_warehouse(self):
		wh = frappe.db.get_value("Warehouse", {"is_group": 0}, ["name", "warehouse_name"], as_dict=True)
		self.assertEqual(get_warehouse_name_code(invoice(set_warehouse=wh.name, items=[])), wh.warehouse_name)

	def test_code_falls_back_to_the_first_item_warehouse(self):
		"""Create > Return / Credit Note blanks the header warehouse (standard
		ERPNext); the return must still be named SR + warehouse letter."""
		wh = frappe.db.get_value("Warehouse", {"is_group": 0}, ["name", "warehouse_name"], as_dict=True)
		doc = invoice(set_warehouse=None, items=[frappe._dict(warehouse=None), frappe._dict(warehouse=wh.name)])
		self.assertEqual(get_warehouse_name_code(doc), wh.warehouse_name)

	def test_no_warehouse_anywhere_gives_no_code(self):
		self.assertEqual(get_warehouse_name_code(invoice(set_warehouse=None, items=[])), "")
