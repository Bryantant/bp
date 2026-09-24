"""Add a short usage guide at the bottom of the Journal Entry "Details" tab.

The Details tab ends with the Auto Repeat section, right before
`tax_withholding_tab`. The guide goes after `user_remark` rather than
`auto_repeat`: for a custom *Section Break*, Frappe's Meta.sort_fields walks
forward to the next Section Break and skips Tab Breaks, so anchoring on
`auto_repeat` lands the section inside the Tax Withholding tab. From
`user_remark` the walk stops at `auto_repeat_section`, keeping it in Details
(Auto Repeat only shows on saved, repeatable entries). The
guide is a read-only HTML field -- it stores nothing on the document.

Client-facing text: says "ERP" only (whitelabel), on-screen labels stay
English and verbatim.

Idempotent: create_custom_fields(update=True) is safe to re-run, and re-running
it also refreshes the guide text after an edit here.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

# (Entry Type, when to use it) -- the only types users should pick by hand.
# The rest of the list is created by the system (revaluation, deferred,
# depreciation, ...) and should not be chosen manually.
ENTRY_TYPES = [
	("Bank Entry", "Transaksi lewat rekening bank: biaya, bunga, biaya admin. Reference Number wajib diisi."),
	("Cash Entry", "Transaksi lewat kas: biaya harian, uang makan, parkir, pengembalian pinjaman karyawan."),
	("Contra Entry", "Pindah dana antar kas/bank, misalnya setoran tunai ke bank atau pindah saldo BCA ke OCBC."),
	("Journal Entry", "Koreksi dan reklasifikasi antar akun, pembulatan, amortisasi, dan jurnal lain tanpa kas/bank."),
	(
		"Opening Entry",
		"Hanya untuk saldo awal saat mulai memakai ERP, dan hanya oleh Accounts Manager. "
		"Jangan dipakai untuk transaksi biasa karena tidak masuk Laba Rugi periode berjalan.",
	),
]

GUIDE_HTML = """
<div style="font-size:13px; line-height:1.55; max-width:900px">
<p><b>Kapan memakai Journal Entry</b><br>
Untuk biaya atau pendapatan lewat kas/bank yang tidak punya invoice, pindah dana antar kas/bank,
reklasifikasi dan koreksi antar akun, serta saldo awal.<br>
<b>Jangan</b> pakai Journal Entry untuk: penjualan/pembelian barang (pakai <b>Sales Invoice</b> /
<b>Purchase Invoice</b>), menerima atau membayar invoice (pakai <b>Payment Entry</b>), dan retur
(buat invoice retur dari invoice asalnya). Jika lewat Journal Entry, stok dan status invoice tidak ikut berubah.</p>

<p><b>Entry Type yang dipakai</b></p>
<table class="table table-bordered table-condensed" style="font-size:13px; margin-bottom:12px">
{entry_type_rows}
</table>

<p><b>Mengisi baris (Accounting Entries)</b></p>
<ul>
<li>Total Debit harus sama dengan total Credit.</li>
<li>Akun piutang atau hutang wajib diisi <b>Party Type</b> dan <b>Party</b> (customer/supplier yang mana).</li>
<li>Jika baris itu melunasi atau mengurangi invoice tertentu, isi <b>Reference Type</b> dan
<b>Reference Name</b>. Tanpa itu saldo customer berubah, tetapi invoice tetap tercatat belum lunas.</li>
<li>Centang <b>Is Advance</b> untuk uang muka yang belum untuk invoice tertentu.</li>
</ul>

<p><b>Mengisi header</b></p>
<ul>
<li><b>Posting Date</b> = tanggal transaksi sebenarnya. Periode yang sudah dikunci tidak bisa diisi.</li>
<li><b>Reference Number / Reference Date</b> = nomor dan tanggal bukti transfer atau giro.</li>
<li><b>User Remark</b> = keterangan yang jelas: untuk apa, kepada siapa, nomor bukti.</li>
</ul>

<p><b>Setelah Submit</b><br>
Dokumen tidak bisa diedit. Untuk memperbaiki, <b>Cancel</b> lalu <b>Amend</b>, atau buat jurnal balik lewat
<b>Create &rarr; Reverse Journal Entry</b>. Dokumen yang sudah Submit tidak dihapus.</p>
</div>
"""


def _entry_type_rows():
	return "\n".join(f"<tr><td style='width:180px'><b>{t}</b></td><td>{desc}</td></tr>" for t, desc in ENTRY_TYPES)


CUSTOM_FIELDS = {
	"Journal Entry": [
		{
			"fieldname": "custom_usage_guide_section",
			"fieldtype": "Section Break",
			"label": "Panduan Journal Entry",
			"insert_after": "user_remark",
			"collapsible": 1,
		},
		{
			"fieldname": "custom_usage_guide",
			"fieldtype": "HTML",
			"label": "Panduan",
			"insert_after": "custom_usage_guide_section",
			"options": GUIDE_HTML.replace("{entry_type_rows}", _entry_type_rows()),
		},
	]
}


def execute():
	frappe.reload_doctype("Journal Entry")
	create_custom_fields(CUSTOM_FIELDS, update=True)
