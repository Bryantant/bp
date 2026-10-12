import frappe
from frappe.tests import IntegrationTestCase

from bp.patches.v1_0 import set_cascading_discount_labels as patch

EXPECTED = {fieldname: (label, columns) for fieldname, label, columns in patch.FIELDS}


class TestCascadingDiscountLabels(IntegrationTestCase):
	def test_sales_order_and_invoice_items_share_labels_and_grid(self):
		patch.execute()
		for doctype in patch.DOCTYPES:
			meta = frappe.get_meta(doctype, cached=False)
			for fieldname, (label, columns) in EXPECTED.items():
				df = meta.get_field(fieldname)
				self.assertEqual(df.label, label, f"{doctype}.{fieldname}")
				self.assertTrue(df.in_list_view, f"{doctype}.{fieldname}")
				self.assertEqual(df.columns, columns, f"{doctype}.{fieldname}")
