"""Legacy AR receipt (arrecnot + arpaymen) -> Journal Entry. See payment.py."""

from bp.utils.legacy_import import SALES_INVOICE
from bp.utils.legacy_import.payment import Side, build_payment, expected_amount

AR_SIDE = Side(
	invoice_doctype="Sales Invoice",
	invoice_kind=SALES_INVOICE,
	party_type="Customer",
	party_field="CustCode",
	date_field="RecNotDt",
	invoice_column="credit_in_account_currency",
	counter_column="debit_in_account_currency",
	offsets_returns=True,
)


def build_ar_receipt(legacy_doc, ctx):
	return build_payment(legacy_doc, ctx, AR_SIDE)


__all__ = ["AR_SIDE", "build_ar_receipt", "expected_amount"]
