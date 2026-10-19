"""Create the "Retur Penjualan" print format for Sales Invoice returns (HT-169).

Continuous form 9.5 x 5.5 in like "Invoice"; layout from the legacy sales
return print (PrtSaReForm). Template in
bp/templates/print_formats/retur_penjualan.html + .css. It is the default print
of a return with goods through bp/public/js/sales_invoice.js.

Idempotent: re-running re-syncs the DB copy from the template files.
"""

from bp.patches.v1_0.create_do_invoice_print_formats import RETUR_PENJUALAN, upsert


def execute():
	upsert([RETUR_PENJUALAN])
