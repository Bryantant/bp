"""Legacy AP payment (appaynot + appaymen) -> Journal Entry. See payment.py.

The mirror of an AR receipt: the purchase invoice is debited off Payables and
the method's account is credited. AP has no return-offset path in the old
system (its method list has no Retur flag), so every line books to the
method's own account -- including "Retur Pembelian" (51700).
"""

from bp.utils.legacy_import import PURCHASE_INVOICE
from bp.utils.legacy_import.payment import Side, build_payment, expected_amount

AP_SIDE = Side(
	invoice_doctype="Purchase Invoice",
	invoice_kind=PURCHASE_INVOICE,
	party_type="Supplier",
	party_field="SuppCode",
	date_field="PayNotDt",
	invoice_column="debit_in_account_currency",
	counter_column="credit_in_account_currency",
	offsets_returns=False,
)


def build_ap_payment(legacy_doc, ctx):
	return build_payment(legacy_doc, ctx, AP_SIDE)


__all__ = ["AP_SIDE", "build_ap_payment", "expected_amount"]
