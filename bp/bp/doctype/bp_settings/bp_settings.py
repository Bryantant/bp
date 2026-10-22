import frappe
from frappe import _
from frappe.model.document import Document


class BPSettings(Document):
	def validate(self):
		self.validate_print_lock_formats()

	def validate_print_lock_formats(self):
		for row in self.get("print_lock_formats") or []:
			doc_type = frappe.db.get_value("Print Format", row.print_format, "doc_type")
			if doc_type != "Sales Invoice":
				frappe.throw(
					_("Row {0}: Print Format {1} is not a Sales Invoice format.").format(
						row.idx, frappe.bold(row.print_format)
					)
				)
