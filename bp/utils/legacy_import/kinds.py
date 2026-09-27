"""The registry of legacy document kinds Legacy Import knows how to bring over.

Everything that differs between kinds lives here, so the runner can treat
them alike: which ERP doctype a kind becomes, how to build it, what a
"confirmed" legacy status is, which amount to compare, which Legacy Import
checkbox selects it, and in which order kinds are processed and reverted.

Processing order follows the dependencies, not the calendar:
	receivings -> stock mutations -> sets -> sales -> returns -> receipts -> payments
Goods must be in stock before they are moved or sold, and invoices and returns
must exist before a receipt or payment can settle them. Reverting runs the
other way round: a payment is cancelled before the invoice it settles.
"""

from dataclasses import dataclass
from typing import Callable

from frappe.utils import flt

from bp.utils.legacy_import import (
	AP_PAYMENT,
	AR_RECEIPT,
	PURCHASE_INVOICE,
	SALES_INVOICE,
	SALES_RETURN,
	STOCK_MUTATION,
	STOCK_SET,
	LegacyImportError,
)
from bp.utils.legacy_import import ap_payment, ar_receipt, payment, sales_return, stock_mutation, stock_set
from bp.utils.legacy_import import purchase_invoice as purchase_invoice_mapper
from bp.utils.legacy_import import sales_invoice as sales_invoice_mapper


def check_amount(actual, expected, tolerance):
	difference = flt(actual) - flt(expected)
	if abs(difference) > flt(tolerance):
		raise LegacyImportError(
			f"ERP total {flt(actual):,.2f} differs from old system total {flt(expected):,.2f} "
			f"by {difference:,.2f} (tolerance {flt(tolerance):,.2f})"
		)


def _check_grand_total(expected_amount):
	return lambda doc, legacy_doc, tolerance: check_amount(doc.grand_total, expected_amount(legacy_doc), tolerance)


def _confirmed_in(*statuses):
	return lambda status: status in statuses


def _not_cancelled(status):
	# Receipts and payments have no Confirm step: saved is effective, 9 is cancelled.
	return status != 9


@dataclass(frozen=True)
class LegacyKind:
	key: str  # Legacy Import Log.legacy_doctype and custom_legacy_type on the ERP document
	erp_doctype: str
	batch_flag: str  # Legacy Import checkbox that selects this kind
	build: Callable  # (legacy_doc, ctx) -> unsaved ERP document
	expected_amount: Callable  # (legacy_doc) -> number or None
	check: Callable  # (doc, legacy_doc, tolerance) -> None, raises LegacyImportError
	amount_field: str | None  # ERP field shown as the ERP amount; None for stock
	is_confirmed: Callable  # (legacy status) -> bool
	order: int
	revert_order: int

	def erp_amount(self, doc):
		return flt(doc.get(self.amount_field)) if self.amount_field else None


KINDS = {
	kind.key: kind
	for kind in (
		LegacyKind(
			key=PURCHASE_INVOICE,
			erp_doctype="Purchase Invoice",
			batch_flag="import_purchase_invoice",
			build=purchase_invoice_mapper.build_purchase_invoice,
			expected_amount=purchase_invoice_mapper.expected_amount,
			check=_check_grand_total(purchase_invoice_mapper.expected_amount),
			amount_field="grand_total",
			is_confirmed=_confirmed_in(2),
			order=10,
			revert_order=70,
		),
		LegacyKind(
			key=STOCK_MUTATION,
			erp_doctype="Stock Entry",
			batch_flag="import_stock_mutation",
			build=stock_mutation.build_stock_mutation,
			expected_amount=stock_mutation.expected_amount,
			check=stock_mutation.check_quantity,
			amount_field=None,
			is_confirmed=_confirmed_in(2),
			order=20,
			revert_order=60,
		),
		LegacyKind(
			key=STOCK_SET,
			erp_doctype="Stock Entry",
			batch_flag="import_stock_set",
			build=stock_set.build_stock_set,
			expected_amount=stock_set.expected_amount,
			check=stock_mutation.check_quantity,
			amount_field=None,
			is_confirmed=_confirmed_in(2),
			order=30,
			revert_order=50,
		),
		LegacyKind(
			key=SALES_INVOICE,
			erp_doctype="Sales Invoice",
			batch_flag="import_sales_invoice",
			build=sales_invoice_mapper.build_sales_invoice,
			expected_amount=sales_invoice_mapper.expected_amount,
			check=_check_grand_total(sales_invoice_mapper.expected_amount),
			amount_field="grand_total",
			is_confirmed=_confirmed_in(2, 3),
			order=40,
			revert_order=40,
		),
		LegacyKind(
			key=SALES_RETURN,
			erp_doctype="Sales Invoice",
			batch_flag="import_sales_return",
			build=sales_return.build_sales_return,
			expected_amount=sales_return.expected_amount,
			check=_check_grand_total(sales_return.expected_amount),
			amount_field="grand_total",
			is_confirmed=_confirmed_in(2),
			order=50,
			revert_order=30,
		),
		LegacyKind(
			key=AR_RECEIPT,
			erp_doctype="Journal Entry",
			batch_flag="import_ar_receipt",
			build=ar_receipt.build_ar_receipt,
			expected_amount=payment.expected_amount,
			check=lambda doc, legacy_doc, tolerance: payment.check_total(
				doc, payment.expected_amount(legacy_doc), tolerance
			),
			amount_field="total_debit",
			is_confirmed=_not_cancelled,
			order=60,
			revert_order=20,
		),
		LegacyKind(
			key=AP_PAYMENT,
			erp_doctype="Journal Entry",
			batch_flag="import_ap_payment",
			build=ap_payment.build_ap_payment,
			expected_amount=payment.expected_amount,
			check=lambda doc, legacy_doc, tolerance: payment.check_total(
				doc, payment.expected_amount(legacy_doc), tolerance
			),
			amount_field="total_debit",
			is_confirmed=_not_cancelled,
			order=70,
			revert_order=10,
		),
	)
}

ORDERED = sorted(KINDS.values(), key=lambda kind: kind.order)


def get_kind(key):
	return KINDS[key]


def selected_kinds(batch):
	return [kind for kind in ORDERED if batch.get(kind.batch_flag)]
