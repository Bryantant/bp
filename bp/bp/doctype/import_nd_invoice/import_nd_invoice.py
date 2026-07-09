"""Import ND Invoice: Excel upload -> editable grid -> Submit creates Sales Invoices.

Rebuilds the legacy Access "Import Sales Invoice" tool that imports invoices
from the ND System -- a separate, currently-active system this integration
pulls invoice data from on an ongoing basis. ND itself is not legacy; only
the old Access-based tool being replaced here is. Modeled on
iib.iib.doctype.so_batch.so_batch.SOBatch: one submittable parent document
holding an editable child-table grid; Submit creates the target documents,
Cancel reverses them.

The ND System's Excel export (InvND) uses column headers that don't match
Frappe field-label conventions, so COLUMN_MAP is hardcoded rather than left
to generic column matching. Header matching is case-insensitive since a real
export was found using "CustomerID" where an earlier assumption expected
"CustomerId". Only 4 columns are ever read from the file (Invoice Number,
Invoice Date, CustomerID, Net Amount) -- Cust Code and Customer Name are NOT
Excel columns, they're derived from the matched Customer record in
resolve_customers(). Salesman and Warehouse are not in the Excel file at
all -- they're filled in manually in the grid, over as many saves as needed,
before Submit. Unlike SOBatch.validate(), this validate() never blocks a Draft save
on unresolved/incomplete rows -- it only resolves what it can. All hard
requirements are enforced once, all-or-nothing, in before_submit() -- NOT
on_submit(): before_submit runs before docstatus=1 is written to the
database (see Document._save/run_before_save_methods), so a validation
failure there leaves the document untouched in Draft. Throwing from
on_submit instead would be too late -- db_update() has already persisted
docstatus=1 by the time on_submit runs, so a failure there can leave a
submitted-but-empty batch stuck in the database with no Sales Invoices and
no way to edit the rows short of Cancel + Amend. (Confirmed by hitting this
exact bug while testing this controller directly.)
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file

COLUMN_MAP = {
	"invoice number": "nd_invoice_no",
	"invoice date": "invoice_date",
	"customerid": "cust_code_nd",
	"net amount": "amount",
}


def _resolve_customer_map(cust_code_nd_values):
	"""Batch-resolve {cust_code_nd: (customer_name_as_id, customer_display_name)}.

	One query for the whole set instead of one per row -- used both by
	resolve_customers() (on save) and parse_excel() (immediately on import,
	so the grid shows Resolved Customer/Customer Name right away instead of
	waiting for the first Save).
	"""
	codes = {c for c in cust_code_nd_values if c}
	if not codes:
		return {}
	customers = frappe.get_all(
		"Customer",
		filters={"custom_nd_code": ["in", list(codes)]},
		fields=["name", "custom_nd_code", "customer_name"],
	)
	return {c.custom_nd_code: (c.name, c.customer_name) for c in customers}


class ImportNDInvoice(Document):
	def validate(self):
		self.check_duplicate_nd_invoice_numbers()
		self.resolve_customers()

	def check_duplicate_nd_invoice_numbers(self):
		seen = set()
		for row in self.rows:
			if not row.nd_invoice_no:
				continue
			if row.nd_invoice_no in seen:
				frappe.throw(
					_("Row {0}: ND Invoice No {1} appears more than once in this batch.").format(
						row.idx, row.nd_invoice_no
					)
				)
			seen.add(row.nd_invoice_no)

	def resolve_customers(self):
		"""Best-effort customer lookup so users get feedback before submitting.

		Never throws -- an unresolved row just keeps resolved_customer blank;
		create_sales_invoices() is where a missing match actually blocks anything.
		Re-runs on every save so edits to Cust Code ND after import stay in sync.
		Rows freshly added via parse_excel() already arrive pre-resolved (see
		below) -- this is what re-resolves manually added/edited rows.
		"""
		customer_map = _resolve_customer_map(row.cust_code_nd for row in self.rows)
		for row in self.rows:
			match = customer_map.get(row.cust_code_nd)
			row.resolved_customer, row.cust_code, row.customer_name = (
				(match[0], match[0], match[1]) if match else (None, None, None)
			)

	def before_submit(self):
		"""All-or-nothing: every row must be valid before docstatus is allowed to become 1."""
		if not self.rows:
			frappe.throw(_("Rows table is empty"))

		placeholder_item = frappe.db.get_single_value("BP Settings", "import_placeholder_item")
		if not placeholder_item:
			frappe.throw(_("Configure a Placeholder Item for imports in BP Settings before submitting."))

		problems = []
		for row in self.rows:
			if not row.resolved_customer:
				problems.append(
					_("Row {0}: no Customer found with Customer in ND (custom_nd_code) = {1}").format(
						row.idx, row.cust_code_nd
					)
				)
			if not row.salesman:
				problems.append(_("Row {0}: Salesman is required").format(row.idx))
			if not row.warehouse:
				problems.append(_("Row {0}: Warehouse is required").format(row.idx))
			if frappe.db.exists("Sales Invoice", {"custom_nd_invoice_no": row.nd_invoice_no}):
				problems.append(
					_("Row {0}: a Sales Invoice already exists for ND invoice number {1}").format(
						row.idx, row.nd_invoice_no
					)
				)

		if problems:
			frappe.throw(
				_("Cannot submit -- fix the following and try again:<br>{0}").format("<br>".join(problems))
			)

	def on_submit(self):
		self.create_sales_invoices()

	def on_cancel(self):
		self.cancel_related_sales_invoices()

	def create_sales_invoices(self):
		"""before_submit() already guaranteed every row is valid -- this just creates."""
		placeholder_item = frappe.db.get_single_value("BP Settings", "import_placeholder_item")

		for row in self.rows:
			si = frappe.new_doc("Sales Invoice")
			si.customer = row.resolved_customer
			si.posting_date = row.invoice_date
			si.set_posting_time = 1
			si.bp_sales_person = row.salesman
			si.custom_nd_invoice_no = row.nd_invoice_no
			si.append(
				"items",
				{
					"item_code": placeholder_item,
					"qty": 1,
					"rate": row.amount,
					"warehouse": row.warehouse,
				},
			)
			si.insert(ignore_permissions=True)
			# on_submit runs after this document's own db_update() already ran, so mutating
			# row.sales_invoice in-memory alone would silently not persist -- write it directly.
			frappe.db.set_value(
				"Import ND Invoice Item", row.name, "sales_invoice", si.name, update_modified=False
			)
			row.sales_invoice = si.name

		created = [row.sales_invoice for row in self.rows]
		lines = [_("<b>{0} Sales Invoice(s) created (Draft):</b>").format(len(created))]
		for name in created:
			lines.append(f"&bull; <a href='/app/sales-invoice/{name}'>{name}</a>")
		frappe.msgprint("<br>".join(lines), title=_("Import Complete"), indicator="green")

	def cancel_related_sales_invoices(self):
		for row in self.rows:
			if not row.sales_invoice or not frappe.db.exists("Sales Invoice", row.sales_invoice):
				continue
			si = frappe.get_doc("Sales Invoice", row.sales_invoice)
			if si.docstatus == 1:
				si.cancel()
			else:
				frappe.delete_doc("Sales Invoice", si.name, force=True, ignore_permissions=True)


@frappe.whitelist()
def parse_excel(file_url):
	"""Parse an uploaded ND System invoice export into plain row dicts for the client's grid.

	Does not insert or save anything -- the client adds returned rows to the
	in-memory child table, so nothing persists until the user Saves/Submits.
	Rows come back with resolved_customer/cust_code/customer_name already
	filled in where a match exists, so the grid shows them immediately on
	import instead of only after the first Save.
	"""
	frappe.only_for(["System Manager", "Accounts Manager"])

	rows = read_xlsx_file_from_attached_file(file_url=file_url) or []
	if not rows:
		frappe.throw(_("The uploaded file has no rows."))

	header = rows[0]
	column_index = {}
	for idx, cell in enumerate(header):
		key = str(cell).strip().lower() if cell is not None else ""
		fieldname = COLUMN_MAP.get(key)
		if fieldname:
			column_index[fieldname] = idx

	missing = [h for h, f in COLUMN_MAP.items() if f not in column_index]
	if missing:
		frappe.throw(_("The uploaded file is missing expected column(s): {0}").format(", ".join(missing)))

	parsed, errors = [], []
	for data_row in rows[1:]:
		if not any(data_row):
			continue

		values = {fieldname: data_row[idx] for fieldname, idx in column_index.items()}
		nd_invoice_no = values.get("nd_invoice_no")
		if not nd_invoice_no:
			errors.append({"row": data_row, "error": "Missing Invoice Number"})
			continue
		values["nd_invoice_no"] = str(nd_invoice_no).strip()
		parsed.append(values)

	customer_map = _resolve_customer_map(row["cust_code_nd"] for row in parsed)
	for row in parsed:
		match = customer_map.get(row["cust_code_nd"])
		if match:
			row["resolved_customer"] = row["cust_code"] = match[0]
			row["customer_name"] = match[1]

	return {"rows": parsed, "errors": errors}
