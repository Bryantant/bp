---
summary: Rules, constraints, and lessons learned for building/adjusting Print Formats in the bp app
purpose: Single source of truth so print format work stays consistent across sessions
scope: Custom Print Formats (HTML/CSS/Jinja) for bp.localhost — layout rules, Bry's constraints, Frappe/wkhtmltopdf quirks discovered while building them
status: living document — keep it current, do not let it go stale
---

# Print Format Rules — bp app

> **CHANGE 2026-11-07 (Bry): the app no longer carries print templates or print patches.** Print formats are
> UI customizations owned by prod (bp.hicomsystem.com): edit them in the Print Format form there (dev first,
> prod only with Bry's confirmation), like Client Script and Server Script. The folder `bp/templates/print_formats/`
> and the ten patches that read it (create_*_print_format, rename_*, swap_surat_jalan_delivery_order_names) were
> deleted; they had all run on prod already. History and rollback: the daily snapshot in
> `~/Dev/snapshots/bp-prod-customizations/print_format/` (git, one commit per change). A copy of the last
> templates is in `Client/BP/bp-dev/archive/print-templates-2026-11-07/`. Dev gets the current formats by
> restoring prod (skill prod-to-dev-restore). What stays in the app: the Jinja helpers the formats call
> (`jinja.methods` in hooks.py: `code128_svg`, `bp_paginate`, `bp_item_line`) and the print lock/audit code.
> **Where this document still says "repo file", "template file", "upsert patch" or "re-run the patch", read
> "the Print Format in the UI"; the layout rules, quirks and lessons below remain valid.**

This file is the living rulebook for how print formats get built and adjusted in this
project. It should always reflect the *current* constraints — if a rule changes, edit
the rule in place rather than leaving the old one and adding a note.

## How to Update This File

Update it — without being asked — whenever any of the following happens:

- Bry states a new constraint or preference for how a print format should look or
  behave ("always show X", "never use Y font", "totals must be in bold", etc.)
- A previous rule is changed or dropped ("actually don't do that anymore")
- We hit a Frappe / Jinja / wkhtmltopdf quirk while building or debugging a print
  format that wasn't obvious from the standard docs
- A print-format bug gets fixed and the root cause wasn't obvious

How:
1. Rules/constraints go in **§2 Formatting Rules & Constraints** — one bullet per rule,
   grouped by doctype/print format if it's specific to one, or under "Global" if it
   applies everywhere.
2. Technical discoveries go in **§3 Technical Lessons** — short entry: what happened,
   why, the fix/workaround.
3. Keep entries terse — no padding, no restating what's already standard Frappe
   behavior (see the reference section for that).
4. If a rule is superseded, edit it in place and note the change isn't needed — this
   file reflects current state, not a changelog.

Cross-reference: general (non-print) Frappe/ERPNext lessons live in
`/Users/bryantantonio/Dev/docs/learning-reference/erpnext-dev-lessons.md` (shared across
benchv15/benchv16) — put print-format-specific stuff here instead, so it's easy to find
when working in `bp`.

### When stuck

Before guessing, check these two sources — both faster and more reliable than
trial-and-error:

1. **Official docs:** https://docs.frappe.io/erpnext/printing — printing/print-format
   docs for the exact ERPNext version this app targets.
2. **Standard native print formats already installed on the bench** — real, working
   Jinja/HTML/CSS shipped by Frappe/ERPNext core. Prefer copying patterns from these
   over inventing new ones. On this machine they live as JSON fixtures under:
   - `apps/erpnext/erpnext/accounts/print_format/` (e.g. `sales_invoice_standard`,
     `purchase_invoice_standard`, `credit_note`, `pos_invoice_standard`)
   - `apps/erpnext/erpnext/selling/print_format/` (e.g. `sales_order_standard`,
     `quotation_standard`)
   - `apps/erpnext/erpnext/stock/print_format/`, `.../buying/print_format/`,
     `.../regional/print_format/`
   - `apps/frappe/frappe/templates/print_formats/standard_macros.html` — reusable
     Jinja macros (`render_field`, `render_table`, `print_value`, `add_header`, etc.)
     used by the core "Standard" format; borrow these instead of rewriting field
     rendering from scratch.
   - Or, on the running site itself: Desk → **Print Format** list → open any format
     with `Standard = Yes` and inspect its `html`/`css` fields directly (only visible
     with developer mode, which is on for `bp.localhost`).

---

## 1. Project Conventions

- Custom print formats are built as **Custom HTML / Jinja** (`Print Format Type =
  Jinja`, Print Format Builder off), not the drag-and-drop builder — full control over
  markup/CSS.
- **Decision (2026-11-07, supersedes the 2026-07-21 patch/template decision):** print formats are
  edited only in the UI (Print Format form, `html` and `css` fields) and live in the site's database; prod is
  the source of truth. No fixtures, no patches, no template files in the app. The earlier pattern (HTML/CSS as repo
  files under `bp/templates/print_formats/`, copied into the Print Format by an idempotent `upsert` patch) was
  removed because a UI edit and the repo file could drift apart and one-directional re-syncs silently overwrote UI
  changes. Keep the formats self-contained: fonts as `data:` URIs in the CSS, no `{% include %}` of app files; the
  only app code they call is the `jinja.methods` helpers listed in hooks.py.
- **Decision (2026-07-21):** CSS lives in its own `.css` file per format (paired with
  the `.html` by basename, e.g. `sales_invoice.html` + `sales_invoice.css`), copied
  into the Print Format's dedicated `css` field — **not** inlined via a `<style>` tag
  inside the `.html` file (that was the original approach; moved out per Bry's
  request). `sales_invoice.html`/`surat_jalan.html` are each **fully
  self-contained** otherwise — no shared `_shared.html` include. An earlier version
  factored the common header/customer/signature markup and CSS into a shared macro
  file imported via `{% from "bp/templates/print_formats/_shared.html" import ... %}`
  (this exact `"bp/templates/..."` addressing form does work from a Print Format's
  DB-stored `html` field, proven the same way `bp/storefront/app_shell.py` addresses
  `bp/templates/includes/app_shell.html` — keep that technique in mind if a shared
  include is ever reintroduced for a third format, though note it would need to be a
  `.html` partial imported via Jinja `{% from %}`, not a `.css` file, since the `css`
  field has no template-include mechanism of its own — it's copied verbatim). Removed
  per Bry's request — each format's markup is now readable/editable on its own, at the
  cost of duplicating the CSS and header/customer/signature markup between the two
  file pairs. When editing shared concerns (e.g. the CSS hardening in §3), change all
  four files (both `.html` and both `.css`).
- **Decision (2026-07-21, reverses the previous "custom Python helpers" approach):**
  no custom Python backs these print formats — deliberately **pure Jinja/HTML**, using
  only `frappe.*` functions already exposed to print templates by core
  (`frappe.get_cached_doc`, `frappe.db.get_value`, `frappe.get_all`, `frappe.utils.*`,
  `frappe.get_fullname` — all confirmed available directly, see §4). An earlier
  version put the company-address/warehouse-code/note/stamp logic in
  `bp/bp/utils/print_formats.py`, exposed via the `jinja.methods` hook. Bry asked for
  that to be undone: the concern was that a minor production tweak (e.g. adjusting the
  warehouse-code fallback) would require editing Python + redeploying, instead of
  being adjustable directly in the Print Format's HTML field in the Desk UI. The
  trade-off is verbosity — the company-header/warehouse-code resolution is now a
  ~30-line block of `{% set %}`/`{% if %}`/`{% for %}` at the top of each `.html`
  file instead of one function call — but every bit of logic is now editable from the
  UI with zero deploy. `bp/bp/utils/` and the `jinja` hook in `hooks.py` were deleted
  entirely (nothing else used them). See §3 for a real bug this surfaced (Jinja's
  `{% for %}` loop scoping) and the fix pattern (`namespace()`).
- Related existing features to keep in mind when touching invoice print formats:
  print-once lives in the **warehouse print queue** since HT-171 (meeting Mulyadi
  15 Okt, Bry 2026-10-17). AR clicks Sales Invoice > Print > **Send to Warehouse** and
  picks a format from BP Settings > Warehouse Print Formats (`print_lock_formats`:
  "Sales Invoice", "Surat Jalan"); each send is one `BP Warehouse Print` row that the
  **BP Admin Gudang** role prints exactly once (`bp/warehouse_print.py`, PDF rendered
  with `frappe.flags.ignore_print_permissions` because that role has no Sales Invoice
  access). AR may send again any number of times; a printed row reopens only through
  Reset by a BP Settings > Print Lock Reset Roles user, with a reason. Every Sent /
  Printed / Blocked / Reset lands in `BP Invoice Print Log` (`warehouse_print` column).
  Printing from the Sales Invoice itself is always free: the Enforce Print Once switch
  and the invoice-level Reset Print Lock were removed (Bry 2026-10-17). The gate in
  `bp/bp/overrides/sales_invoice.py` only logs and counts direct prints of the listed
  formats; it never blocks.
- Dev workflow when iterating on a print format (2026-11-07): edit the `html` / `css` of the Print Format in the
  UI on dev, `bench --site bp.localhost clear-cache`, then preview via the doctype's Print view (or
  `/printview?doctype=<...>&name=<...>&format=<...>`). For a fast inner loop without a
  browser, `bench --site bp.localhost execute frappe.get_print --kwargs
  '{"doctype":"...","name":"...","print_format":"..."}'` renders server-side and
  prints the full HTML (or the real Jinja traceback on error) straight to the
  terminal.

## 2. Formatting Rules & Constraints

### Global
- Names of the two goods-out prints (Bry 2026-11-03, swapped by `swap_surat_jalan_delivery_order_names`): the
  no-price Sales Invoice print (`delivery_order.html`) is **"Surat Jalan"**; the Delivery Note print
  (`surat_jalan_sementara.html`) is **"Delivery Order"**. Use `SPECS` in that patch to refresh them from the templates.
- Company header address on every custom print format is the Address named
  `<company>-Office` (`PT. Bestindo Persada-Office`), never the document's
  `company_address` (ERPNext fills that with the preferred shipping / primary address).
  `doc.company_address` is only a fallback when the Office address does not exist
  (Bry 2026-11-02). The Purchase Order "Send To" line is a different thing and still
  uses the document's `shipping_address`.
- Every rule that styles a generic tag we also use (`table`, `th`, `td`) — not just
  our own `bp-`/panel class names — must be written at least as specific as
  `.print-format th`/`.print-format td`, and must carry `!important` if the property
  is one any built-in Print Style sets with `!important`. See §3 for why (the site's
  default Print Style is concatenated into every print format's CSS with no opt-out),
  and the concrete case that motivated this (`Modern` style stripping our table
  header borders/background).
- Print format CSS must force `color: #000 !important` on itself and all descendants
  (`.bp-legacy-format, .bp-legacy-format * { color: #000 !important; }` pattern) when
  recreating a plain black-on-white legacy layout — Frappe's base print stylesheet
  sets `color: #74808b` on table headers (and similar muted tones elsewhere), which
  otherwise wins the cascade over a same-or-lower-specificity override.
- Page size is **A4** site-wide via `Print Settings.pdf_page_size` (already the
  default on `bp.localhost` — no need to set it per print format). PDF generator is
  already **`chrome`** site-wide too (not wkhtmltopdf) — modern CSS (flexbox/grid)
  works fine here, see §4's wkhtmltopdf caveat doesn't apply on this site.
- Layout style (confirmed with Bry, 2026-07-21): recreate the legacy sheet as a stack
  of section panels (`.bp-panel`: company info, doc info, customer+warehouse-code,
  totals, signature), not one outer box around the whole page. Base font size ~13px
  to match the legacy print size.
- Header row structure, latest (2026-07-21, second revision — supersedes the "two
  side-by-side panels" version of this bullet): `.bp-header-row` is a 2-column flex
  row. **Column 1** (`.bp-header-col`, a flex column) stacks two rows: the company
  panel (`bp-panel bp-panel-company`) then the customer+warehouse-code+Order-by panel
  (`bp-panel bp-customer-panel`) directly below it. **Column 2** is a single panel
  (`bp-panel bp-panel-docinfo`) holding the doc heading/info table, stretched via
  flexbox to match column 1's combined height. Only `.bp-panel-company` carries a
  border (`right + bottom`, `border-top`/`border-left: none` — open at the page's
  top-left corner); `.bp-panel-docinfo` and `.bp-customer-panel` are borderless
  (`.bp-panel` itself carries no border by default — only `.bp-panel-company` opts
  in). The customer block and "Order by" line are one combined container (an inner
  `.bp-customer-row` flex div for customer-text + warehouse-code, then `.bp-order-by`
  below it, both inside the same `.bp-customer-panel`), not two separate divs.
- Items table: borders only its header row (`th`) plus a `border-bottom` on the
  **last body row** (`.items-table tbody tr:last-child td`) as a closing rule; other
  body rows stay borderless.
- Footer row: `.bp-note` and `.bp-totals-box` are both fixed to `width: 50%` (via
  `flex: 0 0 50%` inside the `.bp-footer-panel` flex row) — an even split, not
  content-driven sizing (no `gap`, since the two 50%s already fill the row exactly).
  `.bp-totals-box` gets its own `border-bottom` as a closing rule, and its `.bp-num`
  cells are right-aligned (same rule family as the items table's `.bp-num`, just
  scoped to `.bp-totals-box` too since it's a separate table).
- Signature block: columns 2 ("Delivered by,") and 3 (company name / "Admin") each
  get a `<br>` after the label text and another `<br>` at the top of their
  `.bp-signature-line` div, so their signature line sits at the same vertical
  position as column 1's ("Received in Good<br>conditions by," is naturally two
  lines; 2 and 3 are one line, so without the `<br>`s their signature lines would
  sit higher than column 1's). This was first added by Bry directly in the Desk UI
  on the "Sales Invoice" format — mirrored into the repo file and into "Delivery
  Order" for consistency between the two.
- **Process rule (2026-11-07):** there is no repo copy any more, so no one-directional overwrite. The risk now is
  dev and prod drifting: before editing a format on dev, make sure dev holds prod's current copy (restore, or
  compare `html` / `css` with the latest file in the prod snapshot), and apply the finished change to prod by hand
  with Bry's confirmation. (Historic: on 2026-07-21 a Desk edit of the signature-line `<br>` was lost when the
  upsert patch re-ran, which is why the patch was dropped.)

### Per print format

#### Invoice / Surat Jalan / Retur Penjualan (Sales Invoice)
- **2026-10-17:** "Delivery Order" renamed to **"Surat Jalan"** (files `surat_jalan.html/.css`, patch
  `rename_delivery_order_print_format` renames the record, updates BP Settings > Print Lock Formats, re-syncs both).
  Heading "SURAT JALAN" (legacy said "DELIVERY ORDER").
- **2026-10-17:** "Sales Invoice" renamed to **"Invoice"** (file stays `sales_invoice.html/.css`; patch
  `rename_sales_invoice_print_format_to_invoice` moves links and the default print format).
- **Number on the print (2026-10-17, HT-169):** names since 17 Oct carry a dashed prefix (`INV-A26100001`,
  `SR-A26100001`, `ND-26100001`, `AR-NC-...`). Invoice prints a name with a `-` as is and adds `INV-` to an older
  name without one (`A26100002` -> `INV-A26100002`). Surat Jalan prints `SJ-` + the name without `INV-`.
- **Retur Penjualan (2026-10-17):** Sales Invoice return with goods, same continuous form as Invoice. Layout from the
  legacy PrtSaReForm (bp-trd.mdb, form FmSaleRetu): heading RETUR PENJUALAN, No / Date / Hal, Received From,
  Note = `remarks` (legacy SalRetNt; "No Remarks" not printed), columns NO / DESCRIPTION / QTY / PRICE (`rate`) /
  AMOUNT, TOTAL = `doc.total` (Disc / Grand Total only when they differ), signatures Customer by / Received by /
  Approved by / company + Admin. ERP return lines are negative: every figure prints through `|abs`. Default print
  of a return with goods via `bp/public/js/sales_invoice.js` (see §3, sticky print format).
- **Description wraps (Bry 2026-10-29, replaces "one row per line" of 2026-10-17):** `bp_item_line(row.description
  or row.item_name)` joins the description parts (item name, then the legacy brand/code line) with a space and drops
  the legacy placeholder words made only of `-`/`=` (`==== A-06` -> `A-06`, `- -` -> nothing). Only the `td.bp-desc-1`
  cell wraps (`white-space: normal`); other body cells stay `nowrap`. No app code: the template turns every item into
  a dict with its height `bp_px` (as the Payment Note does) = 5 px + 14.3 px x ceil(joined length / N), then calls
  `bp_paginate(_lines, page_px, last_page_px)`. N is a little under what the column holds (about 6.6 px per
  character), so a word wrap never needs more lines than counted: Invoice 30, Delivery Order 41, Retur Penjualan 46,
  Surat Jalan Sementara 41. Re-derive N after changing a DESCRIPTION column width. Purchase Order, Penerimaan Barang
  (+ Harga) and Mutasi Barang (+ Harga) are not changed: prod already prints their description over several lines
  (`item_desc` macro), a newer version than the repo files.
- **Document remark (Bry 2026-10-29):** Sales Invoice `remarks` ("Remarks" on the form, legacy Memo `DeliOrde.DONotesx`)
  prints under the footer note on both Invoice and Delivery Order (`.bp-remark`, 11 px, left column). ERPNext fills
  "No Remarks" when empty, so the template treats that text as empty. Lines are HTML-escaped; the room bp_paginate keeps
  for the last sheet shrinks by 14 px per remark line (explicit lines, wrap guessed at 70 characters). Legacy check
  (`bp-trd.mdb`, 2026-10-29): PrtInvForm/PrtInvFormC/PrtDOSForm print DONotesx (text box under the note), PrtDOForm
  does not and its REMARK column is an empty box; 1,757 of 6,647 DOs since 1 Sep 2026 carried a memo ("ANTAR HARI
  INI", "JEMPUT GUDANG", names).
- **Remark font (Bry 2026-11-04):** `.bp-remark` on the Invoice is 12 px (was 11; Delivery Order unchanged). The remark
  height budget follows: wrap 70 -> 64 characters, first line 12.5 px and every next 15 px, `_last_px` base 183 -> 184 (at
  183 the 10 rows + 1 remark line case moved its last row to a second sheet by 0.5 px). Checked by PDF page count (10 rows
  + 1 line, 9 + 2, 8 + a 2-line wrap, 5 + none: one sheet each); not measured on paper. On prod since 2026-11-04 (backup `prod_print_backup_20261104_110558.json`; prod's Invoice
  copy equalled the repo apart from these lines, so the repo files went as they are).
- **Item table font 13 px (Bry 2026-11-04, was 12; Invoice only, bp-note stays 12):** a row is now 5 + 14.3 = 19.3 px
  (`bp_px` was 5 + 12.1, stale since the 11 -> 12 change of 2026-11-03). Measured on the dev PDF with the guards off: 12
  one-line rows plus the totals fit one sheet, 13 spill the totals onto a second PDF page. Guards: `_last_px` 173 -> 200
  (no remark; 10 rows + totals, about 2 rows of safety), 184 -> 211 less the remark; full sheets `page_px` 339 -> 366 (last
  sheet + 166 footer room); chars per line for the wrap count 52 -> 43. Check by comparing sheets in the HTML with
  pages in the PDF (equal for 7-22 rows, remark cases, 62-character names). On prod since 2026-11-04. Not measured on
  paper; if the LQ-310 print shows the footer crowded, lower `_last_px` first.
- **Remark 13 px + unit conversion in DESCRIPTION (Bry 2026-11-04, Invoice only, on prod since 2026-11-04):** `.bp-remark` 12 -> 13 px
  (wrap 64 -> 59 characters, first line 13.5 px and next 16.25, `_last_px` with a remark 211 - those). The DESCRIPTION cell
  prints ` (<conversion_factor> <stock_uom>)` after `item_name` when the item row's conversion factor is not 1 (`%g`:
  `(24 PACK)`, `(0.5 PCS)`; the UOM is dropped if the row has no `stock_uom`; the UOM part was added the same day and
  is on prod too); the suffix is counted in the wrap length (`bp_sfx` on the line dict). Delivery Order has neither yet.
- Footer note: `doc.terms`, else the company's `default_selling_terms` ("Informasi Rekening" = legacy DONotesx text).
- **Paper (Bry 2026-10-17): continuous form 9.5 x 5.5 in on dot-matrix printers, Sales Invoice document only**
  (both formats here; PO, Penerimaan Barang, Mutasi Barang, Payment Note, Journal Voucher stay A4). `@page` is
  241.3 x 139.7 mm, margins top 5, right 40, bottom 6, left 17 mm; `.print-format { page-width; page-height; margin-* }`
  gives Get PDF the same size. **Content block is 184 mm, not 227 mm (Bry 2026-10-27):** the Epson LQ-310 prints only
  8 in (203 mm) across the form, and where that window starts moves a few mm with how the form sits on the tractors.
  Observed: window ends at 204 mm of the old content (right side cut at 7 mm margin), next print the window started
  7 mm in (left side cut). 17 mm left / 40 mm right (184 mm) keeps the block inside the part common to three prints (page x 14-204 mm). Sales Invoice columns (no 4.5,
  desc 33.5, qty 5, uom 6, price 13.5, % 12.5, discount 11, net 14.5) are sized for it; check a worst-case row after
  any change. Confirmed on paper (LQ-310, prod, INV-B26100006, 2026-10-27): NET AMOUNT, totals and the signature company name all print. Use mm: Frappe `convert_uom` raises KeyError 0 for `in` values (v16.50), which breaks Get PDF.
- **One sheet per page, drawn by the template.** Chrome does not repeat a `<thead>` this tall (our header is ~1/3
  of the page), so the legacy "header on every page" is done in Jinja: `bp_paginate(doc.items, one_line,
  page_px, last_page_px)` (`bp/utils/print_layout.py`, Jinja method) returns the lines per sheet; each
  `.bp-sheet` has the full header with `Page : x / N`, the last also totals and signatures (`.bp-end`). Values now:
  Sales Invoice 285 / 130, Surat Jalan 285 / 150 with `one_line=True` (CSS px; a row is ~19.3 px: 14 per page,
  6-7 on the last). Re-measure them after changing fonts, header or footer (render 30+ line invoice to PDF, check
  every page). An underestimate spills a line onto an extra sheet, nothing is cut.
- Printing on the PC: the Windows printer needs a 9.5 x 5.5 in paper size, chosen in Chrome's print dialog with
  scale 100% and headers/footers off.
- Standard ERPNext Sales Invoice print formats are disabled on bp.localhost (db_set `disabled`, kept by migrate).
- **2026-10-17 (HT-42):** both formats print a Code 128 barcode of `doc.name` (not the INV-/SJ- number) under the
  document number: `code128_svg(doc.name, module_mm=barcode_module_mm, height_mm=9)`, a bp Jinja method
  (`bp/utils/barcode.py`), pure Python, no extra pip package; digit runs use set C. Scanned back in on the Invoice
  Kembali form. `barcode_module_mm` = 0.4233 (1/60 inch: whole printer dots at 120/180/360 dpi, ~75 mm wide for
  SINV-A26100001); never scale the image with CSS. A smaller size only after the paper test
  (`bp-dev/print-test/2026-10-17-uji-barcode-dot-matrix.pdf`, sizes A-D, scanner + phone camera).
- **2026-11-04 (Invoice):** `barcode_module_mm` back to 0.4233 (3 dots at 180 dpi, about 70 mm wide for INV-C26110001).
  The 2-dot test of 2026-11-01 (0.2822, 47 mm) was too tight, the scanner could not read it. The Invoice change is on
  prod too (2026-11-04).
- **2026-11-05 (Surat Jalan = `delivery_order.*`):** matched to the Invoice on what is not different by nature: margin left
  14 mm (was 16; the columns NO. to UOM now have the Invoice's exact widths on the 191.3 mm block, REMARK takes the rest),
  item font 13 px, note 12 px, remark 13 px, 14.3 px per text line (43 characters per line), barcode 0.4233 mm, the
  `(24 PACK)` suffix, page limits 200 / 211 - remark lines / full sheets 366. Measured on the dev PDF with the guards off:
  one sheet holds 12 one-line rows (13 spill), 11 with a one-line remark, 10 with two, 9 with three; the guard allows
  10 / 9 / 8. Remark wraps at about 80 characters (note is 70 % wide, 50 % on the Invoice), not measured. On prod
  since 2026-11-05, not measured on paper.
- **2026-11-05 (Penerimaan Barang / Penerimaan Barang Harga):** DESCRIPTION as on the Invoice: `item_name` only (no
  brand/model second line, no `bp_item_line`) plus `(factor stock_uom)` when `conversion_factor` is not 1. Lines are dicts
  with `bp_px` = 5 + 14.3 per wrapped line (40 characters per line with prices, 55 without), passed to
  `bp_paginate(_lines, page_px=795, last_page_px=679)`; the description wraps (CSS `td.bp-desc-1` white-space normal in the
  repo copy). Checked on dev: 35 / 36 / 76 / 77 rows give the same sheet counts as before (1 / 2 / 2 / 3). On prod since 2026-11-05: the
  prod copy is built from prod's html/css plus only this change (prod uses the `item_desc` macro, not `bp_item_line`).
- These two formats are no longer pure Jinja: they call the bp Jinja methods `code128_svg` and `bp_paginate`
  (hooks `jinja.methods`). Both are plain functions with unit tests (`bp/utils/test_barcode.py`,
  `test_print_layout.py`); the rest stays editable in the Desk.
Two Custom HTML/Jinja print formats on the **Sales Invoice** doctype (this client
does not use a separate Delivery Note doc — delivery and invoicing both happen off
one Sales Invoice record, printed two different ways). Recreates the client's legacy
paper layouts (see `legacy_print_format/*.png`). Templates:
`bp/bp/templates/print_formats/{sales_invoice,surat_jalan}.{html,css}` (each
`.html`+`.css` pair self-contained, no shared include, no Python helper — see §1);
installed by `bp/bp/patches/v1_0/create_do_invoice_print_formats.py`.

- Company header (name/address/phone/fax) is pulled from `doc.company_address` when
  set, falling back to the Company's own `is_your_company_address` Address — inline
  Jinja at the top of each `.html` file (the `_addr_ns`/`company_address` block) —
  most existing invoices predate `company_address` being populated, so the fallback
  is the common path, not an edge case.
- The legacy "GD" 2-letter code near the top of the customer block is the invoice's
  **Warehouse** (`doc.set_warehouse`, falling back to the first item row's
  `warehouse`) — preferring `Warehouse.custom_nama_warehouse` if set, else the
  warehouse name with its `" - <company abbr>"` suffix stripped (e.g. `"A - BP"` →
  `"A"`). Inline Jinja, the `_wh_ns`/`warehouse_code` block.
- The legacy "Log No" line was **dropped** — no equivalent field, not needed.
- The legacy "Order by : DO+INV" line is backed by a real field,
  `Sales Invoice.custom_order_by` (free-text Data, optional, inserted after `po_no`) —
  not static text, since order-by can vary per transaction (DO-only / INV-only /
  combined). Added via `bp/bp/patches/v1_0/add_sales_invoice_order_by_field.py`.
- "Term" prints `doc.payment_terms_template` as-is (no "(Credit)"/"(Cash)" suffix
  logic) — blank if no template is set.
- The footer note ("Barang telah diterima...") is `Company.custom_catatan_do__invoice`
  — a **Company-level** field, not per-invoice, fetched via `doc.company` (the
  `invoice_note` line, one `frappe.db.get_value` call). It's blank until Bry fills it
  in on the Company record — this print format doesn't fabricate default text for it.
- The bottom-right "printed by / at" stamp uses the existing print-lock audit fields
  (`bp_last_printed_by` / `bp_last_printed_at`) — inline Jinja, the `print_stamp`
  block using `frappe.get_fullname` + `frappe.utils.format_datetime`. `_gate` also
  writes the fields onto the doc being rendered, so a counted print (button, Download
  PDF, bulk incl. "Background Print") carries its own user and time, like the legacy
  `CurrentUser() & Date() & Time()` box. A render that is not logged (preview, email,
  a format outside BP Settings > Warehouse Print Formats) with no earlier print shows
  the current user and time. A warehouse-queue print sets both fields to
  the warehouse admin and the current time just before rendering, so the warehouse
  copy carries its own printer and time. Since direct printing is never blocked, the
  stamp can be previewed on any printed invoice.
- Company `Address.phone`/`fax` can only hold Frappe's strict phone format (digits,
  space, `+ _ - , . * # ( )` only, ≤20 chars — see §3) — the legacy text's second
  "hunting line" number and the `(Hunting)` annotation aren't representable there.
  Currently stores just the primary number for phone/fax; ask Bry if the hunting-line
  detail needs preserving some other way before treating this as final.

#### Buying, stock and accounting documents (2026-10-17)
Installed by `bp/patches/v1_0/create_document_print_formats.py`; the first format per doctype in its `FORMATS` list
is set as the Default Print Format (property setter). Same header style as Sales Invoice (company block in Times,
heading underlined, boxed column header row, borderless body). Each `.html`/`.css` pair is self-contained.

| Format | Doctype | Legacy print | Notes |
|---|---|---|---|
| Purchase Order (default) | Purchase Order | PrtPOForm | Supplier phone/fax from `supplier_address`, Attn = `contact_display`, Send To = shipping address line1/line2/city in one line (else warehouse code). AMOUNT = qty x list price (gross); Netto = `grand_total`, Gross/Discount lines only when there is a discount. Signatures Supplier Confirmation / MANAGER / PURCHASING |
| Penerimaan Barang (default) / Penerimaan Barang Harga | Purchase Invoice | PrtRDOForm | Legacy hid prices unless "Cetak Harga": the default has no prices. Also prints DO Supp. (`bill_no`) and the PO numbers of the lines. Note = `custom_note` only (`remarks` holds ERPNext's auto text). Discount = (list price - rate) x qty |
| Mutasi Barang (default) / Mutasi Barang Harga | Stock Entry | PrtStockMut*, PrtStockMutRelForm*, PrtStockMutSetForm | Title by type: MUTASI BARANG (Masuk/Keluar, Status IN/OUT), PEMINDAHAN BARANG (Relokasi, Lokasi "X ke Y"), MUTASI BARANG SET (Rakit Set, rows grouped Barang : Masuk / Keluar). No. = `custom_legacy_no` (Ref. = name) else name. Migrated rows have `basic_amount` 0, so AMOUNT = qty x `basic_rate` |
| Payment Note | Payment Entry | PrtRNForm / PrtPNForm | Title Receiving Note (Receive) / Payment Note (Pay) / Transfer Note (Internal Transfer: one line, From / To accounts in the bottom block); bottom block pinned to the page foot (`min-height: 262mm`). Deductions: Pay adds them to Paid With (paid = allocated + deductions); Receive takes them off the bank lines from the last one backwards (received + deductions = allocated), so both totals stay equal as in the legacy Receiving Note (2026-10-21) |
| Payment Entry | Payment Entry | - | The document as ERP holds it, not the Access note (Bry, 2026-11-04): ERP labels and sections (Payment Type, Account Paid From / To, Paid / Received Amount, Payment References, Payment Deductions or Loss, Advance Taxes and Charges, Total Allocated / Unallocated Amount, In Words); empty sections are left out, a Supplier Invoice No / Exchange Rate column appears only when a row has one. Shares only the header, fonts and the bottom block (Note = `custom_note`, three signature boxes) with the legacy prints. Default Print Format of Payment Entry since 2026-11-04 (on prod the same day, written by REST: Print Format record + the `Payment Entry-main-default_print_format` Property Setter, previous value Payment Note); Payment Note stays in the Print dialog. Rows are built as dicts with `bp_px` and the first row of a section carries its heading and column heading height. Draft / Cancelled shows a Status line in the header. Patch `create_payment_entry_print_format` |
| Journal Voucher (default) | Journal Entry | - | One layout for every entry: No., Account (+ party), Description, Debit, Credit. The Receiving/Payment Note and Cash Receiving/Payment Note modes were dropped (Bry, 2026-10-21) |

- The two variants of Penerimaan Barang and Mutasi Barang are separate files with the same layout and a
  `show_price` flag at the top; keep them in step when editing.
- Standard print formats of these doctypes are still enabled (only Sales Invoice's were disabled).
- **Description on one row (Bry, 2026-10-21):** Purchase Order, Penerimaan Barang (+ Harga) and Mutasi Barang
  (+ Harga) print DESCRIPTION through `bp_item_line` like the Sales Invoice (see "One row per line"): body cells
  `nowrap`, ellipsis when too long; `bp_paginate(..., one_line=True)` counts each line as one row.
- **Penerimaan Barang (+ Harga), Bry 2026-11-04:** the `Lokasi` value prints as `Warehouse <code>` (`Warehouse A`).
  Note, totals and signatures sit at the bottom of the last sheet, as on the legacy print: the last `.bp-legacy-format`
  gets `bp-sheet-last` (flex column, `min-height: 262mm`) and the footer + signature block are wrapped in `.bp-bottom`
  (`margin-top: auto`). 262 mm = A4 297 mm - 10 mm margins x 2 - 15 mm; 270 mm already spilled the name under the
  signature onto a second page (Chrome PDF, margins 10 mm). Re-check the page count after changing margins or fonts.
  The table's closing rule on the last sheet is the top border of `.bp-bottom` (full width, above Note), not a line
  under the last row; earlier sheets keep the line under their last row.
  **On prod since 2026-11-04** (script `bp-dev/scripts/2026-11-04-push-penerimaan-barang-print-to-prod.py`, backup
  `prod_print_backup_20261104_*.json`), but prod's copy is NOT the repo copy: prod still has the `item_desc` macro
  (multi-line description, `chars_per_line`) and the old company address; the repo has `bp_item_line` (one row) and the
  `-Office` address, not shipped yet. Only the two changes above were added to prod's own html/css.
- **Due Date (Bry 2026-11-04):** Penerimaan Barang (+ Harga) print `Due Date` (`doc.due_date`, dd-MMM-yy) as a row
  under `Date` in the document info block. The row adds ~17 px of header, so `bp_paginate` budgets went from
  812 / 696 to 795 / 679 (a 36-line invoice spilled its signature name onto an extra page with the old numbers).
  On prod since 2026-11-04 (backup `prod_print_backup_20261104_105911.json`), built from prod's own copy like the
  changes above.
- **Purchase Order, Bry 2026-11-04:** same bottom footer / signature rule as Penerimaan Barang (`bp-sheet-last`,
  `.bp-bottom`, rule above the note; same CSS block). DESCRIPTION column 37 -> 40 %, taken from PRICE 13 -> 12 % and
  AMOUNT 17 -> 15 % (DISCOUNT stays 10 %: at 9 % the header touched the border). On prod since 2026-11-04 (backup
  `prod_print_backup_20261104_002426.json`), built from prod's own copy like Penerimaan Barang (multi-line `item_desc`,
  `chars_per_line` 37 -> 40 for the wider column); the repo copy still has `bp_item_line` and the `-Office` address.

## 3. Technical Lessons

- **2026-10-17 — The print page keeps the format picked last, even for another document.**
  `PrintView.set_default_print_format` (frappe `printing/page/print/print.js`) returns early when the
  selector still holds a format valid for the doctype, so `frm.meta.default_print_format` is read only on
  the first visit. A per-document default (Retur Penjualan for returns, Invoice otherwise) therefore needs
  both: set `frm.meta.default_print_format` on refresh, and wrap `set_default_print_format` for Sales
  Invoice (`bp.sales_invoice.patch_print_view`). `frappe.ui.form.PrintView` exists only after the print page
  was opened once; before that the selector is empty and Frappe applies the default itself.

- **2026-07-21 — Print Format selector was invisible on the Print Preview page.**
  Cause: our own `desk_overrides.bundle.js` auto-collapses `.layout-side-section` on
  every desk route change (meant to start form/list pages with the sidebar closed).
  Frappe core's Print Preview page (`frappe.pages["print"]`, route `["print", ...]`)
  renders its Print Format / Letter Head / Language selectors *inside that same
  sidebar* (`this.page.sidebar` in `print.js`) — so the global collapse rule was
  hiding the format switcher along with navigation, and the print toolbar has no
  visible toggle button to bring it back. Fix: exclude `route[0] === "print"` from
  the auto-collapse in `bp/public/js/desk_overrides.bundle.js`, then `bench build
  --app bp`. Lesson: any future "hide/collapse sidebar globally" logic must
  special-case the print route, since `.layout-side-section` isn't purely navigation
  there.

- **2026-07-21 — Jinja `{% set %}` inside a `{% for %}` loop does not propagate to the
  outer scope** (unlike Python's loop variables, which leak into the enclosing
  function scope freely). This broke the company-address and warehouse-code fallback
  logic the first time they were inlined as plain Jinja: e.g.
  ```
  {% set company_address = None %}
  {% for _addr_name in _addr_links %}
    {% if not company_address and ... %}{% set company_address = ... %}{% endif %}
  {% endfor %}
  {# company_address is still None here, even when the {% set %} above ran #}
  ```
  Symptom: the company address/contact lines and the warehouse code silently
  rendered blank (no error — the template runs fine, the variable just never
  updates), only noticeable by comparing the rendered PDF against the expected
  layout. `{% if %}`/`{% else %}` blocks do **not** have this problem (only `{% for
  %}` and macro bodies introduce a new scope) — the bug only hit the two fallback
  paths that used a loop. Fix: wrap the mutated value in a `namespace()` object and
  assign to its attribute instead of a bare name:
  ```
  {% set ns = namespace(value=None) %}
  {% for x in items %}
    {% if not ns.value and ... %}{% set ns.value = ... %}{% endif %}
  {% endfor %}
  {# ns.value correctly holds whatever was set inside the loop #}
  ```
  Lesson: any future Jinja block in these templates that needs to "find something in
  a loop and use it afterward" must use `namespace()`, never a bare `{% set %}` inside
  the loop — this is a standing risk now that the print formats are pure Jinja with no
  Python backing them (see §1's "no custom Python" decision).
- **2026-07-21 — `jinja.methods` hook functions are bare template globals, not
  `frappe.<method>()`** (kept for reference — this app no longer uses this hook,
  see §1, but the mechanics are still correct if it's ever reintroduced for something
  else). Registering `jinja = {"methods": ["bp.utils.print_formats"]}`
  in `hooks.py` (module-path form: exposes every function in that module by name —
  confirmed in `frappe/utils/jinja.py:get_jinja_hooks()`) makes those functions
  available as plain top-level template names (`{{ bp_warehouse_code(doc) }}`), added
  directly to `jenv.globals`. They are **not** attached to the `frappe` object that
  templates also get from `get_safe_globals()` (that object is a separate, curated
  proxy with things like `frappe.utils`, `frappe._`, `frappe.form_dict` — unrelated to
  the jinja hook). Calling `frappe.bp_warehouse_code(doc)` fails at render time with
  `AttributeError: module has no attribute 'bp_warehouse_code'` (via
  `safe_exec.py`'s `default_function`), surfaced by Frappe as
  `frappe.exceptions.PrintFormatError: Error in print format on line N: module has no
  attribute '<name>'`. Fix: call hook-exposed functions bare, e.g. `bp_warehouse_code(doc)`.
- **2026-07-21 — the site's default Print Style leaks into every print format's CSS,
  and it isn't always harmless.** Confirmed by reading a working reference format
  ("Custom Invoice" / module Accounts on a different bench+site, `benchv15` /
  `atlanticsea.local:8004`) and then reproducing the effect here: Frappe concatenates,
  for **every** print format regardless of type — `standard.css` (core) + the site's
  currently-selected `Print Settings > Print Style` doc + this format's own CSS — with
  no per-format opt-out (`frappe.www.printview.get_print_style`). `bp.localhost`'s
  active style is `Redesign`, which is where the grey `th` color from the very first
  version of this format came from (`.print-format th { color: #74808b; ...
  border-bottom-width: 1px !important }`). Checked the other 3 built-in styles too —
  `Modern` is worse: `.print-format th { background-color: #eee !important;
  border-bottom: 0px !important }` would silently strip our items-table header
  border/turn it grey if that style were ever selected, `!important` beats higher
  specificity outright regardless of source order. Reproduced this live: temporarily
  flipped `Print Settings.print_style` to `Modern` via direct DB update, re-rendered,
  confirmed the header border/background broke, hardened `.items-table th` (`border`,
  `background: #fff`, `padding`, `font-weight` all `!important` now), re-rendered
  clean under `Modern`, then reverted `print_style` back to `Redesign`. Lesson: any
  rule targeting a bare `table`/`th`/`td` (not just our own `bp-`-prefixed classes)
  needs `!important` at equal-or-higher specificity than `.print-format th`/`td`, or
  its look silently depends on whatever Print Style happens to be configured
  site-wide — don't rely on it staying `Redesign`.
- **2026-07-21 — `Address.phone`/`fax` reject "compound" contact text.** Both are
  fieldtype `Phone`/`Data`, but `phone` (not `fax`) is validated against
  `PHONE_NUMBER_PATTERN = re.compile(r"([0-9\ \+\_\-\,\.\*\#\(\)]){1,20}$")` in
  `frappe/utils/__init__.py` — digits, space, `+ _ - , . * #`, parens only, ≤20 chars
  total. A legacy value like `"(0778) 743 7488 / 7480501 (Hunting)"` (has a slash,
  letters, and is 35 chars) throws `frappe.exceptions.InvalidPhoneNumberError` on
  `doc.insert()`/`.save()`. There's no clean way to store a compound multi-number +
  annotation string in this field — either simplify to one valid number, or add a
  separate free-text custom field if the extra detail must be preserved.

### Previewing a format outside the Desk (2026-11-04)

- All rules in the `.css` files are scoped `.print-format ...`. `frappe.www.printview.get_html_and_style` returns the
  inner HTML only, without that wrapper, so a preview built from it shows serif text and no borders until it is
  wrapped in `<div class="print-format">` (`frappe.get_print` already includes it). Not a defect of the format.
- Chrome headless defaults to Letter with its own margins: add `@page { size: A4; margin: 10mm }` (what the Print
  Format's margins give in Get PDF) or every sheet spills onto a second page because of `min-height: 262mm`.
- Prod check without a real print: `GET /api/method/frappe.www.printview.get_html_and_style?doc=...&name=...&print_format=...`
  (read only), then wrap and print as above. A Print Format that must reach prod without a code deploy: `POST
  /api/resource/Print Format` with the same fields as `upsert` in `create_do_invoice_print_formats.py`, then `PUT` the
  `<DocType>-main-default_print_format` Property Setter once the preview is good.

---

## 4. Reference — Standard Frappe Print Format Mechanics

Baseline behavior, not project-specific — kept here so it doesn't need re-explaining
each session. Don't add to this section unless standard Frappe behavior itself is
being documented as *newly confirmed*; project quirks go in §3 instead.

- Jinja context: `doc` (the document being printed), `letter_head`, `no_letterhead`,
  `print_settings`.
- Formatting helpers: `frappe.utils.fmt_money(doc.grand_total, currency=doc.currency)`,
  `frappe.format_value(doc.field, df)`, `frappe.utils.formatdate(doc.posting_date)`.
- Child tables: `{% for row in doc.items %} ... {% endfor %}`.
- Custom Python helpers can be exposed to templates via `jinja.methods` /
  `jinja.filters` in `hooks.py` — they land as **bare template globals**
  (`{{ my_helper(doc) }}`), not under `frappe.` — see the 2026-07-21 entry in §3 for
  the exact mechanics and the error you get if you call it wrong.
- CSS lives in the Print Format's own `css` field, scoped to the print container. Use
  `@media print` for print-only rules; `page-break-inside: avoid` on table rows to
  stop rows splitting mid-page; the `.page-break` class forces a page break.
- Long tables need real `<table><thead><tbody>` markup (not divs) so headers repeat
  per printed page.
- PDF rendering engine defaults to **wkhtmltopdf** — weaker CSS support than a browser
  (flexbox/grid can behave oddly). Always verify the actual generated PDF, not just
  the on-screen preview.
- **v16 note:** the `Print Format` doctype has a `pdf_generator` field with two
  options — `wkhtmltopdf` (default) and `chrome`. `chrome` renders via headless
  Chrome and has much better modern CSS support (flexbox/grid work as expected) —
  worth switching to if a layout is fighting wkhtmltopdf's quirks. Field lives on the
  Print Format doc itself (`apps/frappe/frappe/printing/doctype/print_format/print_format.json`).
- Barcode/QR: `frappe.utils.barcode_generator` or the `get_barcode` jinja method.
- Reusable macros available in
  `apps/frappe/frappe/templates/print_formats/standard_macros.html` (core's default
  "Standard" format is built from these): `render_field`, `render_table`,
  `render_field_with_label`, `render_text_field`, `render_image`,
  `render_geolocation`, `print_value`, `get_width`, `get_align_class`, `add_header`.
  Import with `{% from "print_formats/standard_macros.html" import render_table %}`
  (adjust path per Frappe's template loader) rather than reimplementing field/table
  rendering by hand.
- Standard core print formats worth reading before building a custom one for the same
  doctype (all `Print Format Type = Jinja`, `custom_format = 1`, `standard = Yes`):
  - Sales Invoice → `apps/erpnext/erpnext/accounts/print_format/sales_invoice_standard/`
  - Purchase Invoice → `apps/erpnext/erpnext/accounts/print_format/purchase_invoice_standard/`
  - Sales Order → `apps/erpnext/erpnext/selling/print_format/sales_order_standard/`
  - Quotation → `apps/erpnext/erpnext/selling/print_format/quotation_standard/`
  - POS Invoice → `apps/erpnext/erpnext/accounts/print_format/pos_invoice_standard/`
  - Credit Note → `apps/erpnext/erpnext/accounts/print_format/credit_note/`
  Each is a JSON fixture — the template is in its `html` key, styles inline in a
  `<style>` block within that same HTML (Print Format's separate `css` field is often
  left empty on these, styling is done inline instead).

## Quotation (A4, 2026-10-30)

- Print format **Quotation** on doctype Quotation, rebuilt from the legacy quotation program (`HicomQuo.mdb`, report
  `PrtQuotForm`, front-end `Hicom Access/Hicom/BP/BPBatam`; still in daily use: 3,612 quotations, last 30 Oct 2026).
  Files `bp/templates/print_formats/quotation.{html,css}`, created by `bp/patches/v1_0/create_quotation_print_format.py`
  (A4 pages drawn by the template like Purchase Order: header and Page x / N on every sheet, totals, note and
  signatures on the last).
- Legacy field to Quotation: F O B = `incoterm` + `named_place`; Payment = `payment_terms_template`; Validity =
  `valid_till` printed as days from the date plus the date; Attn = `contact_display`; Telp / Fax = `contact_mobile`
  or the customer address phone / fax; DISC = gross minus amount per line; offered by = `owner` name and the user's
  `mobile_no` (legacy OffName / OffHP / OffTitle; no title). The legacy DELIVERY column (QuotationDt.Delivery,
  17% of lines filled) is left out (Bry 2026-10-30). The format hides the Print / Get PDF banner of the print page
  (`.action-banner, .print-hide { display: none }`, not only in @media print). Customer, Attn, Telp and Fax are
  label | colon | value cells so the colons line up.
- Closing note: the document's Terms, except when it is the company's default selling terms (that is the invoice bank
  account note); then the legacy sentence "We hope that the above price will meet to your requirement ...".
- Description lines: item name, then brand/model; words made only of "-" or "=" (legacy placeholders) are dropped.
  `striptags` squeezes white space, so line ends are marked with `|||` before it.
- Test PDFs: `bp-dev/print-test/2026-10-30-quotation-*.pdf` (1 sheet, and 34 lines over 3 sheets).
