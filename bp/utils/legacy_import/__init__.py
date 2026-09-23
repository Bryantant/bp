"""Legacy Import: pull confirmed documents from the old Access/MySQL trading
system (`bpol-trd`) into ERP during the migration week.

- source.py         SELECTs against the legacy server (read-only)
- context.py        master/mapping lookups shared by the builders
- sales_invoice.py  deliorde/dodetail  -> Sales Invoice
- purchase_invoice.py pcrecdor/pcrddeta -> Purchase Invoice
- runner.py         preview / run / re-sync, driven by the Legacy Import doctype
"""

SALES_INVOICE = "Sales Invoice"
PURCHASE_INVOICE = "Purchase Invoice"

# Legacy status codes (modStatus.bas): 1 = Normal (draft), 2 = Confirm,
# 3 = Invoiced (DO only), 9 = Cancel. Reverse puts a document back to 1.
LEGACY_STATUS_LABELS = {1: "Draft", 2: "Confirmed", 3: "Invoiced", 9: "Cancelled"}
CONFIRMED_STATUSES = {
	SALES_INVOICE: (2, 3),
	PURCHASE_INVOICE: (2,),
}


class LegacyImportError(Exception):
	"""A legacy document cannot be mapped (missing master, unmapped branch, ...)."""


def legacy_status_label(status):
	return LEGACY_STATUS_LABELS.get(status, str(status))
