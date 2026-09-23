import frappe
from frappe.tests import IntegrationTestCase

from bp.overrides.sales_invoice import before_naming, require_warehouse_when_stock_moves
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
		"""A goods invoice that is simply not filled in yet must keep the
		warehouse series and fail validation, not be renamed."""
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

	# -- warehouse rule -------------------------------------------------------

	def test_stock_invoice_without_warehouse_is_refused(self):
		"""mandatory_depends_on is a browser-only rule in Frappe, so the same
		rule has to exist server-side for imports and the REST API."""
		with self.assertRaises(frappe.ValidationError):
			require_warehouse_when_stock_moves(invoice(set_warehouse=None))

	def test_value_only_invoice_needs_no_warehouse(self):
		require_warehouse_when_stock_moves(invoice(update_stock=0, set_warehouse=None))
