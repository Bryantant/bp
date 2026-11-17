"""Stock Mutation (Stock Entry) numbering by type.

The role rule (sales admins may only relocate stock, DIPIN 2026-10-08, HT-8) is a Server Script and a Client Script on
the site since 2026-11-16 ("Stock Entry - Role Sales Hanya Relokasi"; sources in Client/BP/bp-dev/scripts).
"""

from bp.overrides.series import STOCK_ENTRY_SERIES


def before_naming(doc, method=None):
	"""Number by type (meeting 2026-10-15): MI Barang Masuk, MO Barang Keluar,
	MA Rakit Set, MR Relokasi Barang. A purpose outside the four keeps the
	series it came with."""
	if doc.naming_series and doc.naming_series not in STOCK_ENTRY_SERIES.values():
		return
	series = STOCK_ENTRY_SERIES.get(doc.purpose)
	if series:
		doc.naming_series = series
