"""Legacy Import: pull documents from the old Access/MySQL trading system
(`bpol-trd`) into ERP during the migration period.

- source.py            SELECTs against the legacy server (read-only)
- context.py           master/mapping lookups shared by the builders
- kinds.py             the registry: one entry per kind of legacy document
- sales_invoice.py     deliorde/dodetail      -> Sales Invoice
- purchase_invoice.py  pcrecdor/pcrddeta      -> Purchase Invoice
- sales_return.py      saleretu/saredeta      -> Sales Invoice (is_return)
- stock_mutation.py    stockmut/stockmutdt    -> Stock Entry (receipt/issue/transfer)
- stock_set.py         stockmutset/...dt      -> Stock Entry (Repack)
- ar_receipt.py        arrecnot/arpaymen      -> Journal Entry
- ap_payment.py        appaynot/appaymen      -> Journal Entry
- runner.py            preview / run / re-sync / revert, driven by Legacy Import

A "kind" is the legacy document type. It is what Legacy Import Log records in
`legacy_doctype` and what ERP documents carry in `custom_legacy_type`; it is
NOT the ERP doctype -- a sales return and a sales invoice are both Sales
Invoices, and AR receipts and AP payments are both Journal Entries.
"""

SALES_INVOICE = "Sales Invoice"
PURCHASE_INVOICE = "Purchase Invoice"
SALES_RETURN = "Sales Return"
STOCK_MUTATION = "Stock Mutation"
STOCK_SET = "Stock Set"
AR_RECEIPT = "AR Receipt"
AP_PAYMENT = "AP Payment"

# Legacy status codes (modStatus.bas): 1 = Normal (draft), 2 = Confirm,
# 3 = Invoiced (DO only), 9 = Cancel. Reverse puts a document back to 1.
# Receipts and payments have no Confirm step: 1 = saved (effective), 9 = cancelled.
LEGACY_STATUS_LABELS = {1: "Draft", 2: "Confirmed", 3: "Invoiced", 9: "Cancelled"}
PAYMENT_STATUS_LABELS = {1: "Saved", 9: "Cancelled"}

# Legacy AR receipt method that offsets a sales return against an invoice
# rather than bringing money in.
SALES_RETURN_METHOD = "Retur Penjualan"


class LegacyImportError(Exception):
	"""A legacy document cannot be mapped (missing master, unmapped branch, ...)."""


def legacy_status_label(status, kind=None):
	labels = PAYMENT_STATUS_LABELS if kind in (AR_RECEIPT, AP_PAYMENT) else LEGACY_STATUS_LABELS
	return labels.get(status, str(status))
