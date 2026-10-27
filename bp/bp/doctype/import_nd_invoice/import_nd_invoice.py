"""Import ND Invoice: paste from Excel -> editable grid -> Submit creates Sales Invoices.

Rebuilds the legacy Access "Import Sales Invoice" tool that imports invoices
from the ND System -- a separate, currently-active system this integration
pulls invoice data from on an ongoing basis. ND itself is not legacy; only
the old Access-based tool being replaced here is. Modeled on
iib.iib.doctype.so_batch.so_batch.SOBatch: one submittable parent document
holding an editable child-table grid; Submit creates the target documents,
Cancel reverses them.

Each Sales Invoice is named after the ND "Invoice Number" from the Excel file
(e.g. I260700167), not the BP naming series -- client decision 2026-10-17.
The batch itself keeps its own INDI-YYYY-##### name.

Each batch row becomes a Sales Invoice that is submitted right away, with Update Stock off
(Bry 2026-10-25).

ND invoices carry no salesperson, as in the old Access tool (Bry 2026-10-17), and
the placeholder item is a non-stock item, so they move no stock (Bry 2026-10-19):
the batch has no Salesman or Warehouse fields (removed 2026-10-24).

Rows come in by copy-paste (Bry 2026-10-23, replaces the Excel file upload):
the user selects the ND export rows in Excel (header row optional), copies, and
clicks "Paste dari Excel"; the browser sends the clipboard text (tab-separated)
to parse_pasted(). The ND System's export (InvND) uses column headers that
don't match Frappe field-label conventions, so COLUMN_MAP is hardcoded rather
than left to generic column matching, matched case-insensitively ("CustomerID"
vs "CustomerId"), in any column order, extra columns ignored; the report's blank
lines and its Subtotal / Report Total lines are skipped without a message. Only 4 columns are
read (Invoice Number, Invoice Date, CustomerID, Net Amount) -- Cust Code and
Customer Name are derived from the matched Customer record in
resolve_customers().

Copied text carries what Excel *displays*, which follows the PC's locale: the
ND export's date cells use Excel's built-in short date, so the same file pastes
as 17/10/2026 on an Indonesian PC and 10/17/2026 on a US one, and amounts as
1.016.195,70 or 1,016,195.70. parse_dates() settles day/month order for the
whole paste (a part above 12 decides; otherwise the month in the ND invoice
number, I26*10*00444) and parse_amount() reads either separator style.
Unlike SOBatch.validate(), this validate() never blocks a Draft save
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

import re
from datetime import date, datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

# Headers as the ND export writes them; COLUMN_MAP (matched case-insensitively) is built from them.
TEMPLATE_COLUMNS = [
	("Invoice Number", "nd_invoice_no"),
	("Invoice Date", "invoice_date"),
	("CustomerID", "cust_code_nd"),
	("Net Amount", "amount"),
]
COLUMN_MAP = {header.lower(): fieldname for header, fieldname in TEMPLATE_COLUMNS}
# The ND report groups invoices and closes each group with "Subtotal (5)" and the report with
# "Report Total" in the Invoice Number column; those lines are not invoices.
SUMMARY_LINE = re.compile(r"^(sub\s*total|report\s+total|grand\s+total)\b", re.IGNORECASE)


def _resolve_customer_map(cust_code_nd_values):
	"""Batch-resolve {cust_code_nd: (customer_name_as_id, customer_display_name)}.

	One query for the whole set instead of one per row -- used both by
	resolve_customers() (on save) and parse_pasted() (immediately on paste,
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
		Rows freshly added via parse_pasted() already arrive pre-resolved (see
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
			if frappe.db.exists("Sales Invoice", {"custom_nd_invoice_no": row.nd_invoice_no}):
				problems.append(
					_("Row {0}: a Sales Invoice already exists for ND invoice number {1}").format(
						row.idx, row.nd_invoice_no
					)
				)
			elif frappe.db.exists("Sales Invoice", row.nd_invoice_no.strip()):
				# The new invoice takes this number as its name, so any invoice already
				# holding it (an opening invoice named after the legacy number, say) blocks it.
				problems.append(
					_("Row {0}: Sales Invoice {1} already exists, so it cannot be used as the name").format(
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
			# ND invoices move no stock (the placeholder is non-stock); never let a default turn it on
			si.update_stock = 0
			si.custom_nd_invoice_no = row.nd_invoice_no
			si.append(
				"items",
				{
					"item_code": placeholder_item,
					"qty": 1,
					"rate": row.amount,
				},
			)
			# set_name skips before_naming and the naming series entirely
			si.insert(ignore_permissions=True, set_name=row.nd_invoice_no)
			# Submitted straight away (Bry 2026-10-25). If it fails the exception rolls back the
			# whole batch, so no half-created set of invoices is left behind.
			si.flags.ignore_permissions = True
			si.submit()
			# on_submit runs after this document's own db_update() already ran, so mutating
			# row.sales_invoice in-memory alone would silently not persist -- write it directly.
			frappe.db.set_value(
				"Import ND Invoice Item", row.name, "sales_invoice", si.name, update_modified=False
			)
			row.sales_invoice = si.name

		created = [row.sales_invoice for row in self.rows]
		lines = [_("<b>{0} Sales Invoice(s) created and submitted:</b>").format(len(created))]
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


MONTHS = {
	"jan": 1, "feb": 2, "peb": 2, "mar": 3, "apr": 4, "may": 5, "mei": 5, "jun": 6, "jul": 7,
	"aug": 8, "agu": 8, "agt": 8, "sep": 9, "oct": 10, "okt": 10, "nov": 11, "nop": 11, "dec": 12, "des": 12,
}  # fmt: skip
ISO_DATE = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})")
NUMERIC_DATE = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})(?:\s|$)")
NAMED_DATE = re.compile(r"^(\d{1,2})[-/ .]([A-Za-z]{3,})[-/ .,]+(\d{2}|\d{4})(?:\s|$)")
ND_NUMBER_MONTH = re.compile(r"^[A-Za-z]\d{2}(\d{2})")


def _year(text):
	year = int(text)
	return year + 2000 if year < 100 else year


def parse_amount(value):
	"""Number from a pasted cell, either separator style: 1,016,195.70 / 1.016.195,70 / 204281 / Rp 5.000."""
	if isinstance(value, int | float):
		return flt(value)
	text = str(value or "").strip()
	negative = text.startswith("-") or (text.startswith("(") and text.endswith(")"))
	text = re.sub(r"[^\d,.]", "", text)
	if not text:
		return None
	if "," in text and "." in text:
		decimal = "," if text.rfind(",") > text.rfind(".") else "."
		text = text.replace("." if decimal == "," else ",", "").replace(decimal, ".")
	elif "," in text or "." in text:
		sep = "," if "," in text else "."
		parts = text.split(sep)
		# 1.234.567 or 1,234 (three digits after) are thousands; 1016195,7 is a decimal
		if len(parts) > 2 or len(parts[-1]) == 3:
			text = text.replace(sep, "")
		else:
			text = text.replace(sep, ".")
	number = flt(text)
	return -number if negative else number


def parse_dates(cells):
	"""Dates for a list of (nd_invoice_no, cell) pairs, one day/month order for the whole paste.

	Returns (dates, error). dates[i] is a date or None when the cell is unreadable.
	"""
	parsed, ambiguous = [], []
	for nd_no, cell in cells:
		if isinstance(cell, datetime):
			parsed.append(("date", cell.date()))
			continue
		if isinstance(cell, date):
			parsed.append(("date", cell))
			continue
		text = str(cell or "").strip()
		if m := ISO_DATE.match(text):
			parsed.append(("ymd", (int(m[1]), int(m[2]), int(m[3]))))
		elif m := NUMERIC_DATE.match(text):
			parsed.append(("ab", (int(m[1]), int(m[2]), _year(m[3]))))
			ambiguous.append((nd_no, int(m[1]), int(m[2])))
		elif (m := NAMED_DATE.match(text)) and m[2][:3].lower() in MONTHS:
			parsed.append(("ymd", (_year(m[3]), MONTHS[m[2][:3].lower()], int(m[1]))))
		else:
			parsed.append((None, None))

	day_first = True
	if ambiguous:
		first_is_day = any(a > 12 for _, a, _ in ambiguous)
		second_is_day = any(b > 12 for _, _, b in ambiguous)
		if first_is_day and second_is_day:
			return [None] * len(cells), _(
				"Invoice Date mixes day-month and month-day order; check the copied cells."
			)
		if second_is_day:
			day_first = False
		elif not first_is_day:
			# every part is 12 or less: let the month in the ND number (I26 10 00444) decide
			votes_day = votes_month = 0
			for nd_no, a, b in ambiguous:
				if m := ND_NUMBER_MONTH.match(str(nd_no or "")):
					month = int(m[1])
					votes_day += b == month
					votes_month += a == month
			day_first = votes_day >= votes_month

	dates = []
	for kind, value in parsed:
		try:
			if kind == "date":
				dates.append(value)
			elif kind == "ymd":
				dates.append(date(*value))
			elif kind == "ab":
				a, b, year = value
				dates.append(date(year, b, a) if day_first else date(year, a, b))
			else:
				dates.append(None)
		except ValueError:
			dates.append(None)
	return dates, None


@frappe.whitelist()
def parse_pasted(text):
	"""Parse ND rows copied from Excel (tab-separated, header row optional) into plain row dicts.

	Does not insert or save anything -- the client adds returned rows to the
	in-memory child table, so nothing persists until the user Saves/Submits.
	Rows come back with resolved_customer/cust_code/customer_name already
	filled in where a match exists, so the grid shows them immediately.
	"""
	frappe.only_for(["System Manager", "Accounts Manager"])

	text = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
	# keep each line's own number (blank lines included) so errors match the rows the user copied
	table = [(no, line.split("\t")) for no, line in enumerate(text.split("\n"), start=1) if line.strip()]
	if not table:
		frappe.throw(_("The clipboard is empty. Copy the rows in Excel first."))

	column_index = {}
	for idx, cell in enumerate(table[0][1]):
		fieldname = COLUMN_MAP.get(cell.strip().lower())
		if fieldname:
			column_index[fieldname] = idx

	if column_index:
		# a header row came along; it may be in any column order
		missing = [header for header, fieldname in TEMPLATE_COLUMNS if fieldname not in column_index]
		if missing:
			frappe.throw(
				_("The copied header row has no: {0}. Copy again with all four columns.").format(
					", ".join(missing)
				)
			)
		data_lines = table[1:]
	else:
		# no header row (data rows only): the ND report's own column order
		column_index = {fieldname: i for i, (_header, fieldname) in enumerate(TEMPLATE_COLUMNS)}
		data_lines = table

	raw, errors = [], []
	for line_no, cells in data_lines:
		values = {f: (cells[i].strip() if i < len(cells) else "") for f, i in column_index.items()}
		if not any(values.values()) or SUMMARY_LINE.match(values["nd_invoice_no"]):
			continue
		if not values["nd_invoice_no"]:
			errors.append(_("Line {0}: missing Invoice Number").format(line_no))
			continue
		raw.append((line_no, values))

	dates, date_error = parse_dates([(v["nd_invoice_no"], v["invoice_date"]) for _, v in raw])
	if date_error:
		frappe.throw(date_error)

	parsed = []
	for (line_no, values), invoice_date in zip(raw, dates, strict=True):
		amount = parse_amount(values["amount"])
		if not invoice_date:
			errors.append(
				_("Line {0} ({1}): Invoice Date {2} not recognised").format(
					line_no, values["nd_invoice_no"], values["invoice_date"]
				)
			)
			continue
		if amount is None:
			errors.append(
				_("Line {0} ({1}): Net Amount {2} not recognised").format(
					line_no, values["nd_invoice_no"], values["amount"]
				)
			)
			continue
		parsed.append(
			{
				"nd_invoice_no": values["nd_invoice_no"],
				"cust_code_nd": values["cust_code_nd"],
				"invoice_date": invoice_date.isoformat(),
				"amount": amount,
			}
		)

	customer_map = _resolve_customer_map(row["cust_code_nd"] for row in parsed)
	for row in parsed:
		match = customer_map.get(row["cust_code_nd"])
		if match:
			row["resolved_customer"] = row["cust_code"] = match[0]
			row["customer_name"] = match[1]

	return {"rows": parsed, "errors": errors}
