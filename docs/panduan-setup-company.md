# Panduan Pengaturan (Setup) Company di ERPNext

Panduan ini dibuat untuk membantu Anda — pemilik/pengelola bisnis — mengisi sendiri pengaturan **Company** di ERPNext, tanpa perlu memahami istilah teknis atau bahasa Inggris secara mendalam.

Setiap kolom (field) di layar ERPNext ditampilkan dalam **Bahasa Inggris**. Panduan ini menuliskan nama Inggrisnya persis seperti yang Anda lihat di layar, lalu menjelaskan **artinya**, **pengaruhnya** kalau diisi/diaktifkan, dan **rekomendasi pengisian** dalam Bahasa Indonesia.

Panduan ini hanya membahas 4 tab berikut (sesuai urutan tab di layar):

1. **Accounts** (Akuntansi)
2. **Accounts Closing** (Penutupan Akuntansi)
3. **Buying and Selling** (Pembelian dan Penjualan)
4. **Stock and Manufacturing** (Persediaan dan Manufaktur)

Tab lain (Details, Dashboard) tidak dibahas di sini karena sudah berisi data dasar perusahaan (nama, alamat, mata uang, dll.) yang biasanya sudah diisi saat perusahaan pertama kali dibuat.

---

## Cara Membuka Halaman Company

1. Login ke ERPNext.
2. Ketik **"Company"** di kotak pencarian di bagian atas layar (ikon kaca pembesar).
3. Pilih perusahaan Anda dari daftar yang muncul.
4. Anda akan melihat beberapa tab di bagian atas form: **Details, Accounts, Accounts Closing, Buying and Selling, Stock and Manufacturing, Dashboard**. Klik tab yang ingin diatur.

**Cara membaca panduan ini:** setiap kolom diberi tanda berikut agar Anda tahu seberapa penting dan seberapa aman untuk diisi sendiri:

- **[PENTING]** — sebaiknya diisi karena langsung memengaruhi transaksi sehari-hari (penjualan, pembelian, kas).
- **[OPSIONAL]** — hanya isi kalau memang relevan dengan cara bisnis Anda berjalan. Kalau tidak yakin, boleh dikosongkan dulu.
- **[LANJUTAN]** — pengaturan teknis/akuntansi khusus. Kalau ragu, **biarkan default/kosong** dan tanyakan ke akuntan atau konsultan ERPNext sebelum mengubah.

Aturan emas: **kalau Anda tidak tahu efek suatu kolom, jangan diisi/dicentang.** Hampir semua kolom di tab-tab ini boleh dikosongkan dan diisi belakangan setelah Anda berdiskusi dengan akuntan — sistem tetap bisa dipakai tanpa semua kolom terisi.

---

## 1. Tab "Accounts" (Akuntansi)

### 1.1 Bagian "Chart of Accounts" (Bagan Akun)

Bagian ini biasanya hanya diisi **satu kali saat perusahaan pertama kali dibuat**. Jangan diubah lagi setelah transaksi mulai berjalan.

| Kolom di layar | Arti | Pengaruh | Rekomendasi |
|---|---|---|---|
| **Create Chart Of Accounts Based On** | Sumber daftar akun (Bagan Akun) yang dipakai | Menentukan apakah daftar akun keuangan Anda (Kas, Piutang, Pendapatan, dll.) dibuat dari template standar, atau disalin dari perusahaan lain yang sudah ada di sistem | [LANJUTAN] Biasanya sudah diatur oleh konsultan saat instalasi awal. Jangan diubah lagi. |
| **Chart Of Accounts Template** | Nama template bagan akun standar | Menentukan struktur akun bawaan (mis. template untuk Indonesia) | [LANJUTAN] Diisi otomatis sesuai pilihan di atas. |
| **Existing Company** | Perusahaan lain yang bagan akunnya ingin dicontoh | Menyalin struktur akun dari perusahaan tersebut | [LANJUTAN] Hanya relevan jika bisnis Anda punya banyak cabang/anak perusahaan di sistem yang sama. |

### 1.2 Bagian "Default Accounts" (Akun Default) — **paling penting di tab ini**

Akun-akun ini akan **otomatis dipakai** oleh sistem setiap kali Anda membuat transaksi (invoice, pembayaran, dsb.) apabila Anda tidak memilih akun secara manual. Salah isi di sini bisa membuat laporan keuangan (neraca/laba rugi) tercatat di akun yang keliru.

| Kolom di layar | Arti | Pengaruh | Rekomendasi |
|---|---|---|---|
| **Default Bank Account** [PENTING] | Akun bank utama perusahaan | Dipakai sebagai akun bank bawaan saat mencatat pembayaran masuk/keluar lewat transfer bank | Pilih akun bank yang paling sering dipakai untuk transaksi harian. |
| **Default Cash Account** [PENTING] | Akun kas (uang tunai) utama | Dipakai sebagai akun bawaan saat mencatat transaksi tunai | Pilih akun "Kas" utama toko/kantor Anda. |
| **Default Receivable Account** [PENTING] | Akun Piutang Usaha (uang yang harus dibayar customer ke Anda) | Semua transaksi penjualan kredit akan tercatat menambah saldo di akun ini | Biasanya hanya ada satu akun "Piutang Usaha" — pilih itu. Jangan diubah setelah banyak invoice dibuat. |
| **Default Payable Account** [PENTING] | Akun Hutang Usaha (uang yang harus Anda bayar ke supplier) | Semua transaksi pembelian kredit akan tercatat menambah saldo di akun ini | Sama seperti di atas, pilih akun "Hutang Usaha" utama. Jangan diubah setelah banyak transaksi. |
| **Write Off Account** [OPSIONAL] | Akun untuk "menghapuskan" selisih kecil yang tidak bisa ditagih/dibayar | Dipakai saat Anda membulatkan/menghapus sisa tagihan kecil (misal selisih Rp 500 karena pembulatan) | Kalau ragu, isi dengan akun "Beban Lain-lain" atau tanya akuntan. |
| **Unrealized Profit / Loss Account** [LANJUTAN] | Akun laba/rugi yang "belum terealisasi" | Dipakai saat ada transfer barang antar gudang/perusahaan dalam satu grup usaha yang belum terjual ke pihak luar | Hanya relevan jika Anda punya lebih dari satu Company (grup usaha) di sistem yang sama. |
| **Allow Account Creation Against Child Company** [LANJUTAN] | Izinkan transaksi anak perusahaan membuat akun sendiri | Hanya muncul jika perusahaan ini punya "Parent Company" (induk) | Hanya relevan untuk struktur holding/grup usaha. Abaikan jika bisnis Anda berdiri sendiri. |
| **Default Cost of Goods Sold Account** [PENTING] | Akun HPP (Harga Pokok Penjualan) | Setiap kali barang stok terjual, biaya pokoknya otomatis tercatat ke akun ini | Pilih akun "Harga Pokok Penjualan" / "HPP". |
| **Default Income Account** [PENTING] | Akun Pendapatan utama | Dipakai sebagai akun pendapatan bawaan pada baris penjualan jika item tidak punya akun pendapatan khusus sendiri | Pilih akun "Penjualan" / "Pendapatan Usaha" utama. |
| **Default Payment Discount Account** [OPSIONAL] | Akun untuk diskon pembayaran lebih awal | Dipakai kalau Anda memberi/menerima potongan karena pelunasan lebih cepat dari jatuh tempo | Isi hanya jika bisnis Anda punya kebijakan diskon pelunasan cepat. |
| **Default Payment Terms Template** [OPSIONAL] | Syarat pembayaran default (mis. jatuh tempo 30 hari) | Otomatis terisi di setiap transaksi baru sebagai jatuh tempo bawaan | Isi jika Anda punya kebijakan tempo pembayaran standar untuk semua customer/supplier. |
| **Default Cost Center** [OPSIONAL] | Pusat biaya/unit bisnis default | Dipakai untuk mengelompokkan biaya per divisi/cabang jika Anda tidak memilih manual | Isi jika Anda melacak laporan per divisi/cabang. Kalau bisnis Anda hanya satu unit, boleh dikosongkan. |
| **Default Finance Book** [LANJUTAN] | Buku akuntansi default (untuk standar pelaporan ganda, mis. lokal vs internasional) | Mempengaruhi laporan yang memakai lebih dari satu standar akuntansi sekaligus | Hampir semua bisnis kecil-menengah bisa mengabaikan ini. |

### 1.3 Bagian "Exchange Gain / Loss" (Selisih Kurs) [LANJUTAN — hanya jika transaksi pakai mata uang asing]

| Kolom di layar | Arti | Pengaruh | Rekomendasi |
|---|---|---|---|
| **Exchange Gain / Loss Account** | Akun selisih kurs yang sudah terealisasi | Dipakai saat Anda menerima/membayar dalam USD (atau mata uang lain) dan kursnya berbeda dari saat invoice dibuat | Isi bersama akuntan jika Anda bertransaksi dalam mata uang asing. Jika transaksi selalu dalam Rupiah, boleh dikosongkan. |
| **Unrealized Exchange Gain/Loss Account** | Akun selisih kurs yang belum terealisasi | Dipakai saat sistem menilai ulang piutang/hutang valas yang belum dibayar di akhir periode | Sama seperti di atas — hanya relevan untuk transaksi mata uang asing. |

### 1.4 Bagian "Round Off" (Pembulatan) [OPSIONAL]

| Kolom di layar | Arti | Pengaruh | Rekomendasi |
|---|---|---|---|
| **Round Off Account** | Akun pembulatan nilai transaksi | Selisih pembulatan (misal total invoice dibulatkan ke Rp 100 terdekat) dicatat ke akun ini | Isi dengan akun "Selisih Pembulatan" jika Anda ingin total invoice tampil bulat. |
| **Round Off Cost Center** | Pusat biaya untuk entry pembulatan | Mengelompokkan pencatatan pembulatan ke unit bisnis tertentu | Isi hanya jika Anda memakai Cost Center. |
| **Round Off for Opening** | Akun pembulatan khusus saldo awal (opening balance) | Dipakai saat Anda memasukkan saldo awal akuntansi pertama kali di sistem | Biasanya samakan dengan Round Off Account di atas. |

### 1.5 Bagian "Deferred Accounting" (Akuntansi Tangguhan) [LANJUTAN — hanya jika relevan]

| Kolom di layar | Arti | Pengaruh | Rekomendasi |
|---|---|---|---|
| **Default Deferred Revenue Account** | Akun pendapatan diterima di muka | Dipakai jika Anda menjual jasa/langganan yang pendapatannya diakui bertahap (misal kontrak 12 bulan) | Isi hanya jika bisnis Anda menjual paket/langganan jangka panjang. Jika tidak, kosongkan. |
| **Default Deferred Expense Account** | Akun biaya dibayar di muka | Kebalikan dari di atas — untuk biaya yang dibayar sekaligus tapi diakui bertahap | Sama seperti di atas, tanyakan akuntan jika ragu. |

### 1.6 Bagian "Advance Payments" (Uang Muka)

| Kolom di layar | Arti | Pengaruh | Rekomendasi |
|---|---|---|---|
| **Book Advance Payments in Separate Party Account** [LANJUTAN] | Catat uang muka di akun terpisah | Jika **dicentang**: uang muka dari customer dicatat di akun kewajiban (liability) terpisah, bukan langsung mengurangi Piutang; uang muka ke supplier dicatat di akun aset terpisah, bukan mengurangi Hutang. Jika **tidak dicentang**: uang muka langsung tercampur dengan saldo Piutang/Hutang biasa | Diskusikan dengan akuntan — beberapa bisnis lebih suka laporan Piutang/Hutang yang "bersih" (tidak tercampur uang muka), sebagian lagi tidak masalah. Kalau ragu, biarkan tidak dicentang (lebih sederhana). |
| **Reconciliation Takes Effect On** | Kapan uang muka dianggap "berlaku" untuk mencocokkan dengan invoice | Menentukan tanggal yang dipakai saat sistem mencocokkan uang muka dengan invoice terkait (tanggal uang muka dibayar, tanggal tertua di antara invoice/uang muka, atau tanggal saat pencocokan dilakukan) | [LANJUTAN] Biarkan default ("Oldest Of Invoice Or Advance") kecuali akuntan Anda punya preferensi khusus. |
| **Default Advance Received Account** | Akun khusus uang muka dari customer | Hanya muncul/berlaku jika kolom "Book Advance Payments..." di atas dicentang | Isi hanya jika opsi di atas diaktifkan. |
| **Default Advance Paid Account** | Akun khusus uang muka ke supplier | Hanya muncul/berlaku jika kolom "Book Advance Payments..." di atas dicentang | Isi hanya jika opsi di atas diaktifkan. |

### 1.7 Bagian "Exchange Rate Revaluation Settings" [LANJUTAN — hanya jika transaksi mata uang asing]

| Kolom di layar | Arti | Pengaruh | Rekomendasi |
|---|---|---|---|
| **Auto Create Exchange Rate Revaluation** | Buat penilaian ulang kurs otomatis | Jika dicentang, sistem otomatis membuat jurnal penyesuaian kurs untuk saldo piutang/hutang mata uang asing secara berkala | Aktifkan hanya jika bisnis Anda rutin bertransaksi dalam mata uang asing dan ingin laporan kurs otomatis. |
| **Frequency** | Seberapa sering revaluasi dibuat (Harian/Mingguan/Bulanan) | Menentukan jadwal pembuatan jurnal otomatis di atas | Bulanan biasanya cukup untuk kebanyakan bisnis. |
| **Submit ERR Journals?** | Langsung "finalkan" jurnal revaluasi otomatis | Jika dicentang, jurnal otomatis tadi langsung final (tidak bisa diedit) tanpa direview dulu | Sebaiknya **jangan dicentang** dulu, agar akuntan bisa memeriksa jurnalnya sebelum difinalkan. |

### 1.8 Bagian "Budget Detail" [OPSIONAL]

| Kolom di layar | Arti | Pengaruh | Rekomendasi |
|---|---|---|---|
| **Exception Budget Approver Role** | Role/jabatan yang boleh menyetujui transaksi melebihi anggaran | Hanya berlaku jika Anda memakai fitur Budget (anggaran per Cost Center/Akun) di ERPNext | Isi hanya jika Anda sudah mengatur anggaran (Budget) dan ingin ada proses approval khusus saat anggaran terlampaui. |

### 1.9 Bagian "Fixed Asset Defaults" (Aset Tetap) [OPSIONAL — hanya jika mencatat aset tetap & penyusutan di sistem]

| Kolom di layar | Arti | Pengaruh | Rekomendasi |
|---|---|---|---|
| **Accumulated Depreciation Account** | Akun akumulasi penyusutan | Menampung total penyusutan seluruh aset tetap yang sudah berjalan | Isi dengan akun "Akumulasi Penyusutan". |
| **Depreciation Expense Account** | Akun beban penyusutan | Biaya penyusutan bulanan aset tetap tercatat ke sini (masuk laporan laba rugi) | Isi dengan akun "Beban Penyusutan". |
| **Series for Asset Depreciation Entry (Journal Entry)** | Format penomoran otomatis untuk jurnal penyusutan | Hanya memengaruhi format nomor dokumen, tidak memengaruhi nilai keuangan | [LANJUTAN] Boleh dibiarkan default. |
| **Gain/Loss Account on Asset Disposal** | Akun untung/rugi saat aset dijual/dibuang | Dipakai saat Anda menjual atau menghapus aset tetap dari pembukuan | Isi jika Anda memakai modul Aset Tetap. |
| **Asset Depreciation Cost Center** | Pusat biaya untuk beban penyusutan | Mengelompokkan biaya penyusutan ke divisi/cabang tertentu | Opsional, isi jika memakai Cost Center. |
| **Capital Work In Progress Account** | Akun aset dalam pengerjaan (belum selesai dibangun/dipasang) | Dipakai untuk aset yang masih dalam proses pembangunan sebelum siap dipakai (mis. gedung yang masih dibangun) | Isi jika bisnis Anda punya proyek pembangunan aset jangka panjang. |
| **Asset Received But Not Billed** | Akun aset yang sudah diterima fisik tapi tagihan supplier belum diterima | Mirip konsep "barang diterima belum ditagih" tapi khusus untuk Aset Tetap | Isi jika Anda sering menerima aset sebelum invoice supplier datang. |

---

## 2. Tab "Accounts Closing" (Penutupan Akuntansi)

Tab ini sangat berguna untuk **mengunci data lama** agar tidak sengaja diubah setelah laporan keuangan periode tersebut sudah final/dilaporkan.

| Kolom di layar | Arti | Pengaruh | Rekomendasi |
|---|---|---|---|
| **Accounts Frozen Till Date** [PENTING] | Tanggal pembekuan transaksi | Semua transaksi dengan tanggal **pada atau sebelum** tanggal ini **tidak bisa lagi dibuat, diubah, atau dihapus** oleh user biasa | Setelah laporan bulanan/tahunan selesai dan disetujui, isi tanggal ini dengan tanggal akhir periode tersebut (misal akhir bulan lalu). Ini mencegah staf tidak sengaja mengubah data yang sudah dilaporkan ke pihak lain (bank, pajak, investor). |
| **Roles Allowed to Set and Edit Frozen Account Entries** [PENTING] | Role/jabatan yang tetap boleh mengubah transaksi meski sudah "dibekukan" | Hanya user dengan role ini (misal Akuntan Senior/Owner) yang masih bisa mengoreksi transaksi lama jika benar-benar diperlukan | Isi dengan role tepercaya, misalnya "Accounts Manager", supaya ada jalur koreksi darurat tapi tetap terbatas. |

**Catatan penting:** kolom **Accounts Frozen Till Date** adalah salah satu pengaturan paling berguna untuk mencegah kesalahan/kecurangan data — sangat disarankan untuk rutin diperbarui setiap kali tutup buku bulanan.

---

## 3. Tab "Buying and Selling" (Pembelian dan Penjualan)

### 3.1 Bagian "Buying & Selling Settings"

| Kolom di layar | Arti | Pengaruh | Rekomendasi |
|---|---|---|---|
| **Default Buying Terms** [OPSIONAL] | Syarat & ketentuan default untuk Purchase Order | Otomatis muncul di setiap Purchase Order baru | Isi jika Anda punya template S&K pembelian standar. |
| **Monthly Sales Target** [OPSIONAL] | Target penjualan bulanan | Hanya untuk keperluan monitoring/dashboard, **tidak memengaruhi** transaksi atau laporan keuangan | Isi jika Anda ingin memantau pencapaian target penjualan langsung dari sistem. |
| **Total Monthly Sales** | Total penjualan bulan berjalan | Kolom ini **otomatis terisi oleh sistem**, tidak bisa diedit manual | Abaikan — tidak perlu diisi sendiri. |
| **Default Selling Terms** [OPSIONAL] | Syarat & ketentuan default untuk Sales Order/Quotation | Otomatis muncul di setiap penawaran/pesanan penjualan baru | Isi jika Anda punya template S&K penjualan standar. |
| **Default Sales Contact** [OPSIONAL] | Kontak (PIC penjualan) default perusahaan | Muncul sebagai kontak bawaan di dokumen penjualan | Isi dengan nama PIC sales utama jika relevan. |
| **Default Warehouse for Sales Return** [OPSIONAL] | Gudang tujuan untuk barang retur dari customer | Saat customer mengembalikan barang, barang tersebut otomatis masuk ke gudang ini | Isi jika Anda punya gudang khusus untuk menampung retur (agar terpisah dari stok siap jual). |
| **Credit Limit** [OPSIONAL] | Batas kredit default untuk **semua** customer baru | Jika transaksi customer melebihi batas ini, sistem bisa memperingatkan atau memblokir transaksi baru (tergantung pengaturan lain di Selling Settings) | Isi dengan angka batas kredit standar Anda, atau kosongkan jika setiap customer diatur berbeda-beda secara manual. |

### 3.2 Bagian "Purchase Expense"

| Kolom di layar | Arti | Pengaruh | Rekomendasi |
|---|---|---|---|
| **Purchase Expense Account** [OPSIONAL] | Akun beban default untuk pembelian non-stok | Dipakai sebagai akun bawaan saat mencatat pembelian yang sifatnya biaya langsung (bukan barang yang disimpan sebagai stok) | Isi dengan akun beban umum jika relevan; jika ragu, tanyakan akuntan. |
| **Service Expense Account** [OPSIONAL] | Akun beban khusus untuk item jenis "Layanan/Jasa" | Dipakai otomatis saat Anda membeli item bertipe jasa (bukan barang fisik) | Isi jika Anda sering membeli jasa (mis. jasa maintenance, konsultan) lewat Purchase Order/Invoice. |
| **Purchase Expense Contra Account** [LANJUTAN] | Akun lawan (penyeimbang) untuk pencatatan beban pembelian di atas | Pengaturan teknis akuntansi ganda (double-entry) yang jarang perlu diubah manual | Biarkan kosong kecuali diarahkan khusus oleh konsultan/akuntan Anda. |

---

## 4. Tab "Stock and Manufacturing" (Persediaan dan Manufaktur)

### 4.1 Bagian "Stock Settings"

| Kolom di layar | Arti | Pengaruh | Rekomendasi |
|---|---|---|---|
| **Enable Perpetual Inventory** [PENTING] | Aktifkan akuntansi stok otomatis (real-time) | Jika **diaktifkan**: setiap barang masuk/keluar gudang otomatis membuat jurnal akuntansi, sehingga nilai stok di neraca selalu up-to-date. Jika **dimatikan**: stok hanya tercatat jumlahnya saja, **tidak berpengaruh** ke laporan keuangan sama sekali | Sebaiknya **tetap diaktifkan** (ini pengaturan bawaan/default) untuk hampir semua bisnis dagang/manufaktur. Hanya matikan jika Anda sengaja mencatat akuntansi stok secara manual di luar sistem. |
| **Enable Item-wise Inventory Account** [LANJUTAN] | Akun persediaan ditentukan per jenis barang, bukan per gudang | Jika diaktifkan, tiap Item/Kategori Barang/Brand bisa punya akun persediaan sendiri-sendiri di neraca, alih-alih satu akun per gudang | Biarkan **tidak aktif** kecuali Anda memang butuh laporan neraca stok yang dipecah per jenis produk (biasanya untuk bisnis dengan kategori produk yang sangat beragam). |
| **Enable Provisional Accounting For Non Stock Items** [LANJUTAN] | Buat jurnal sementara untuk pembelian jasa/non-stok sebelum tagihan diterima | Fitur akuntansi lanjutan untuk mencatat estimasi biaya sebelum invoice resmi dari supplier datang | Umumnya tidak diperlukan untuk bisnis kecil-menengah. Aktifkan hanya atas rekomendasi akuntan. |
| **Default Inventory Account** [PENTING] | Akun Persediaan/Stok utama di neraca | Dipakai sebagai akun bawaan untuk mencatat nilai stok, jika gudang tertentu tidak diatur akun khususnya sendiri | Isi dengan akun "Persediaan Barang Dagang" atau sejenisnya. |
| **Default Stock Valuation Method** [PENTING — hati-hati mengubahnya] | Metode penghitungan nilai/biaya stok: **FIFO** (barang masuk pertama keluar pertama), **Moving Average** (rata-rata bergerak), atau **LIFO** | Menentukan bagaimana Harga Pokok Penjualan (HPP) dihitung setiap kali barang terjual | Pilih di **awal setup** sesuai kebijakan akuntansi Anda (FIFO paling umum dipakai di Indonesia). **Jangan diganti-ganti** setelah banyak transaksi berjalan — bisa membuat laporan HPP historis jadi tidak konsisten. |
| **Stock Adjustment Account** [OPSIONAL] | Akun untuk selisih stok hasil opname/penyesuaian manual | Dipakai saat Anda melakukan Stock Reconciliation (stok opname) dan ditemukan selisih jumlah barang | Isi dengan akun "Selisih Persediaan" atau sejenisnya. |
| **Stock Received But Not Billed** [PENTING jika sering terima barang sebelum invoice] | Akun "Barang Diterima Belum Ditagih" | Dipakai saat barang sudah masuk gudang secara fisik, tapi invoice/tagihan dari supplier belum Anda terima — ini akun kewajiban sementara | Isi dengan akun kewajiban khusus untuk ini jika Anda sering menerima barang duluan sebelum tagihan datang. |
| **Default Provisional Account** [LANJUTAN] | Akun provisional untuk item non-stok | Pasangan dari opsi "Enable Provisional Accounting..." di atas | Isi hanya jika opsi tersebut diaktifkan. |
| **Default In-Transit Warehouse** [OPSIONAL] | Gudang "transit" (dalam perjalanan) default | Dipakai saat memindahkan stok antar gudang yang butuh waktu tempuh — barang tercatat "di jalan", belum masuk gudang tujuan | Isi jika Anda punya proses pengiriman antar gudang yang memakan waktu (misal antar kota/cabang). |

### 4.2 Bagian "Manufacturing" (hanya relevan jika Anda memproduksi barang sendiri)

| Kolom di layar | Arti | Pengaruh | Rekomendasi |
|---|---|---|---|
| **Default Operating Cost Account** [OPSIONAL] | Akun biaya operasional produksi | Dipakai sebagai akun bawaan untuk biaya overhead/operasional saat proses produksi (Work Order) berjalan | Isi jika Anda menggunakan modul Manufaktur/Produksi. |
| **Default Work In Progress Warehouse** [OPSIONAL] | Gudang "Barang Dalam Proses" | Tempat bahan baku "disimpan sementara" selama proses produksi berlangsung, sebelum menjadi barang jadi | Isi dengan gudang WIP jika Anda berproduksi di sistem. |
| **Default Finished Goods Warehouse** [OPSIONAL] | Gudang Barang Jadi | Tempat hasil produksi disimpan setelah proses produksi selesai | Isi dengan gudang barang jadi Anda. |
| **Default Scrap Warehouse** [OPSIONAL] | Gudang untuk sisa/scrap produksi | Menampung material sisa/rusak dari proses produksi | Isi jika proses produksi Anda menghasilkan sisa material yang perlu dilacak terpisah. |

**Catatan:** seluruh bagian "Manufacturing" ini **boleh dikosongkan** jika bisnis Anda murni dagang (jual-beli) dan tidak memproduksi barang sendiri.

---

## Ringkasan: Kolom yang Paling Wajib Diisi di Awal

Kalau Anda hanya punya waktu terbatas, prioritaskan kolom-kolom ini terlebih dahulu (semua ada di tab **Accounts**, kecuali disebutkan lain):

1. Default Bank Account
2. Default Cash Account
3. Default Receivable Account (Piutang)
4. Default Payable Account (Hutang)
5. Default Cost of Goods Sold Account (HPP)
6. Default Income Account (Pendapatan)
7. Default Stock Valuation Method — *tab Stock and Manufacturing* (pilih FIFO jika ragu)
8. Enable Perpetual Inventory — *tab Stock and Manufacturing* (pastikan tetap aktif)
9. Default Inventory Account — *tab Stock and Manufacturing*
10. Accounts Frozen Till Date — *tab Accounts Closing* (update rutin setiap tutup buku bulanan)

Kolom lainnya bersifat opsional atau lanjutan — boleh diisi belakangan setelah berdiskusi dengan akuntan atau konsultan ERPNext Anda.

---

## Kapan Harus Bertanya ke IT/Konsultan?

Hubungi tim teknis Anda sebelum mengubah kolom bertanda **[LANJUTAN]**, atau jika:

- Anda ingin **mengganti** Default Stock Valuation Method setelah transaksi sudah berjalan lama.
- Anda ingin **mengubah** Chart of Accounts / struktur akun setelah banyak transaksi tercatat.
- Anda tidak yakin apakah bisnis Anda perlu fitur **Advance Payments dalam akun terpisah**, **Deferred Accounting**, atau **Exchange Rate Revaluation**.
- Ada perbedaan antara apa yang tertulis di panduan ini dengan tampilan layar Anda (kemungkinan versi ERPNext berbeda).
