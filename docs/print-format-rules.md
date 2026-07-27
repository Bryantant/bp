---
summary: Rules, constraints, and lessons learned for building/adjusting Print Formats in the bp app
purpose: Single source of truth so print format work stays consistent across sessions
scope: Custom Print Formats (HTML/CSS/Jinja) for bp.localhost — layout rules, Bry's constraints, Frappe/wkhtmltopdf quirks discovered while building them
status: living document — keep it current, do not let it go stale
---

# Print Format Rules — bp app

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

Cross-reference: general (non-print) Frappe/ERPNext lessons for this environment live
in `/Users/bryantantonio/Dev/benchv15/MD/dev-notes/ERPNEXT_DEV_LESSONS.md` — put
print-format-specific stuff here instead, so it's easy to find when working in `bp`.

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
- **Decision (2026-07-21, supersedes the old "add to fixtures" guidance below this
  bullet):** print formats are created/synced via an idempotent **patch**, not
  `fixtures`. This app has already moved off fixtures for custom-field-style
  customization in favor of `create_custom_fields(...)`-style patches (only
  `Client Script` remains fixture-tracked in `hooks.py`) — creating Print Formats the
  same way is more consistent, and avoids fixtures silently pulling in *every* print
  format on the site. Pattern: keep the actual HTML and CSS as real, reviewable repo
  files under `bp/bp/templates/print_formats/*.html` + `*.css` (one `.css` per
  `.html`, same basename — see the next bullet for why they're separate files), and
  have a patch (e.g. `bp/bp/patches/v1_0/create_do_invoice_print_formats.py`) read
  each with `frappe.read_file(frappe.get_app_path("bp", "templates", "print_formats",
  "<file>"))` (raw text, **not** `frappe.render_template` — the `.html` is itself a
  Jinja template meant to render later at print time, not now) and upsert them into
  the `Print Format` doc's `html` and `css` fields respectively. Re-run the patch
  (`bench --site bp.localhost execute bp.patches.v1_0.<module>.execute`) after editing
  either file to re-sync the DB copy — `bench migrate` alone won't re-run an
  already-applied patch.
- **Decision (2026-07-21):** CSS lives in its own `.css` file per format (paired with
  the `.html` by basename, e.g. `sales_invoice.html` + `sales_invoice.css`), copied
  into the Print Format's dedicated `css` field — **not** inlined via a `<style>` tag
  inside the `.html` file (that was the original approach; moved out per Bry's
  request). `sales_invoice.html`/`delivery_order.html` are each **fully
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
  `bp_invoice_print_log` and `bp_print_lock_reset_role` doctypes implement a
  print-lock feature on invoices — a custom Sales Invoice print format needs to stay
  compatible with that behavior (see `bp/bp/doctype/bp_invoice_print_log/` and
  `bp/bp/overrides/sales_invoice.py`). The lock is shared per-document, not
  per-print-format — printing *any* format for a Sales Invoice consumes the same
  once-only allowance (confirmed intentional, not something to "fix" by default).
- Dev workflow when iterating on a print format: edit the template file(s) under
  `bp/bp/templates/print_formats/`, re-run the upsert patch, `bench --site
  bp.localhost clear-cache`, then preview via the doctype's Print view (or
  `/printview?doctype=<...>&name=<...>&format=<...>`). For a fast inner loop without a
  browser, `bench --site bp.localhost execute frappe.get_print --kwargs
  '{"doctype":"...","name":"...","print_format":"..."}'` renders server-side and
  prints the full HTML (or the real Jinja traceback on error) straight to the
  terminal.

## 2. Formatting Rules & Constraints

### Global
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
- **Process rule:** the upsert patch is one-directional — it overwrites the DB's
  `html` field from the repo file, never the other way around. If a change is made
  directly in the Desk UI (Print Format Builder / HTML field) instead of in
  `bp/bp/templates/print_formats/*.html`, it will be **silently lost** the next time
  the patch runs (`bench migrate` on a fresh site, a manual re-run after an unrelated
  template edit, etc.). This happened once already (2026-07-21, the signature-line
  `<br>` fix above) — always check the live DB content against the repo file
  (`SELECT html FROM \`tabPrint Format\` WHERE name='...'`, unescape, `diff` against
  the repo file) before editing further if there's any chance of a Desk-side change
  in between sessions.

### Per print format

#### Sales Invoice / Delivery Order
Two Custom HTML/Jinja print formats on the **Sales Invoice** doctype (this client
does not use a separate Delivery Note doc — delivery and invoicing both happen off
one Sales Invoice record, printed two different ways). Recreates the client's legacy
paper layouts (see `legacy_print_format/*.png`). Templates:
`bp/bp/templates/print_formats/{sales_invoice,delivery_order}.{html,css}` (each
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
  block using `frappe.get_fullname` + `frappe.utils.format_datetime` — blank until the
  invoice has actually been printed once. Because the print-lock blocks
  *re-rendering* an already-printed invoice in **any** format (see §1), you can't
  preview this stamp on a real already-printed invoice without an Accounts
  Manager/System Manager resetting that invoice's lock first
  (`bp.overrides.sales_invoice.reset_print_lock`) — this was verified by
  unit-testing `format_datetime`/`get_fullname` directly rather than forcing a reset
  on a real record.
- Company `Address.phone`/`fax` can only hold Frappe's strict phone format (digits,
  space, `+ _ - , . * # ( )` only, ≤20 chars — see §3) — the legacy text's second
  "hunting line" number and the `(Hunting)` annotation aren't representable there.
  Currently stores just the primary number for phone/fax; ask Bry if the hunting-line
  detail needs preserving some other way before treating this as final.

## 3. Technical Lessons

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
