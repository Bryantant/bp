"""Sales Invoice Source Warehouse goes back to standard ERPNext: optional.

require_sales_invoice_source_warehouse and allow_non_stock_sales_invoices made
the header warehouse mandatory (always, then while Update Stock is on). That
broke every sales return: Create > Return / Credit Note blanks set_warehouse on
purpose (erpnext.controllers.sales_and_purchase_return.make_return_doc), so the
return was refused with "Source Warehouse is required".

Decided 2026-09-27: follow standard ERPNext. The item rows carry the warehouse
stock moves from, as core already requires for stock items when Update Stock is
on. The naming token (bp.overrides.sales_invoice.get_warehouse_name_code) falls
back to the first item's warehouse, so invoices and returns keep their letter
(A26090001, SRA26090001).

Removes only the two Property Setters on set_warehouse; Update Stock's default
of 1 and the naming-series options stay. Idempotent.
"""

import frappe


def execute():
	for prop in ("reqd", "mandatory_depends_on"):
		frappe.db.delete(
			"Property Setter",
			{"doc_type": "Sales Invoice", "field_name": "set_warehouse", "property": prop},
		)
	frappe.clear_cache(doctype="Sales Invoice")
