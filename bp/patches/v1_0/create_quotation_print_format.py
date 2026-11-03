"""Create the "Quotation" print format (A4), recreating the legacy Access quotation print
(HicomQuo.mdb, report PrtQuotForm). Template in bp/templates/print_formats/quotation.html + .css.

Idempotent: re-running re-syncs the DB copy from the template files.
"""

from bp.patches.v1_0.create_do_invoice_print_formats import upsert


def execute():
	upsert([{"name": "Quotation", "doc_type": "Quotation", "template": "quotation.html", "style": "quotation.css"}])
