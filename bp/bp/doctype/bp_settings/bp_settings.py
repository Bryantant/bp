import frappe
from frappe import _
from frappe.model.document import Document


class BPSettings(Document):
	def validate(self):
		self.validate_legacy_warehouse_map()

	def validate_legacy_warehouse_map(self):
		seen = set()
		for row in self.legacy_warehouse_map:
			row.branch_code = (row.branch_code or "").strip().upper()
			if row.branch_code in seen:
				frappe.throw(
					_("Row {0}: Old System Branch {1} is mapped more than once.").format(
						row.idx, row.branch_code
					)
				)
			seen.add(row.branch_code)
