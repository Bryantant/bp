import frappe
from frappe import _
from frappe.model.document import Document


class BPSettings(Document):
	def validate(self):
		self.validate_print_lock_formats()
		self.validate_legacy_warehouse_map()
		self.validate_legacy_payment_method_map()

	def validate_print_lock_formats(self):
		for row in self.get("print_lock_formats") or []:
			doc_type = frappe.db.get_value("Print Format", row.print_format, "doc_type")
			if doc_type != "Sales Invoice":
				frappe.throw(
					_("Row {0}: Print Format {1} is not a Sales Invoice format.").format(
						row.idx, frappe.bold(row.print_format)
					)
				)

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

	def validate_legacy_payment_method_map(self):
		seen = set()
		for row in self.get("legacy_payment_method_map") or []:
			row.legacy_method = (row.legacy_method or "").strip()
			if row.legacy_method in seen:
				frappe.throw(
					_("Row {0}: Old System Payment Method {1} is mapped more than once.").format(
						row.idx, row.legacy_method
					)
				)
			seen.add(row.legacy_method)
