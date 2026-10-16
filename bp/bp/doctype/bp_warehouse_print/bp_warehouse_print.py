# Copyright (c) 2026, Hicom System and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BPWarehousePrint(Document):
	"""One invoice sent by AR to the warehouse admin, in one print format.

	Each row may be printed once from the warehouse queue; the flow lives in
	bp.warehouse_print."""

	def validate(self):
		from bp.overrides.sales_invoice import _locked_formats

		if frappe.db.get_value("Sales Invoice", self.sales_invoice, "docstatus") != 1:
			frappe.throw(_("Only a submitted Sales Invoice can be sent to the warehouse."))
		if self.print_format not in _locked_formats():
			frappe.throw(
				_("Print Format {0} is not in BP Settings > Warehouse Print Formats.").format(
					frappe.bold(self.print_format)
				)
			)
