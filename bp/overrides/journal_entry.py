import frappe
from erpnext.accounts.doctype.journal_entry.journal_entry import JournalEntry


# ---------------------------------------------------------------------------
# Controller override
#
# Core's JournalEntry.on_submit runs the customer credit-limit check whenever
# a row debits a customer. Legacy Import (bp.utils.legacy_import.ar_receipt)
# posts receipts that offset an imported sales return against an invoice:
# one row debits the customer against the return, another credits the same
# amount against the invoice -- the customer's balance does not move, yet the
# check refuses the receipt when the customer is already over its limit.
# The receipt was issued in the old system, so ERP has nothing to decide.
# Only skipped during an import run; manual JEs are checked as before.
# ---------------------------------------------------------------------------


class BPJournalEntry(JournalEntry):
	def check_credit_limit(self):
		if frappe.flags.get("bp_legacy_import"):
			return
		super().check_credit_limit()
