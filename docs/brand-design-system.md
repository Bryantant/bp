# Bestindo Brand Design System (Reference)

> Extracted from the live client site **https://bestindocleaning.com/** on 2026-07-20 by inspecting rendered pages, computed CSS, and asset URLs directly in a browser.
>
> **Purpose:** this document captures the *brand identity* (colors, type, logo, UI motifs) of the existing Bestindo landing page so it can be reapplied consistently to a **new, separate ERPNext-based e-commerce site**. The e-commerce site is a different product with different content/IA than the landing page — only the visual brand identity below should carry over (see [Application Guidance](#application-guidance-for-the-new-erpnext-e-commerce-site) at the end).

## 1. Source & Tech Stack Observed

- Company: **PT. Bestindo Persada** — distributor of commercial/industrial cleaning equipment and consumables (est. 29 Nov 2005).
- Pages inspected: Home, Products, Brands, Catalog, About Us.
- Framework: **Bootstrap 5** (confirmed via `--bs-*` CSS custom properties on `:root`).
- Icon libraries: Font Awesome 5.10.0, Bootstrap Icons 1.4.1.
- Fonts loaded via Google Fonts: `Open Sans` (400, 500) and `Poppins` (200, 600, 700).
- Brands distributed (shown on Brands page): Helbet, Clenso Home Care, Livi, Vienklen, Janex, 3M, Cyclone, FalconPro.

## 2. Logo

- File: `https://bestindocleaning.com/gbr/bestindo.png`
- Wordmark **"Bestindo"** in a bold, rounded, hand-lettered/casual script style — red/orange lettering with a blue swoosh underline beneath the text. The dot on the "i" is styled as a red accent dot.
- Favicon: `https://bestindocleaning.com/gbr/favicon.ico`
- Feel: friendly, approachable, slightly playful — contrasts with the more corporate navy/blue used everywhere else, giving the brand a "trusted but not stiff" tone.

## 3. Color Palette

Colors below are the actual Bootstrap theme overrides pulled from computed `:root` custom properties, plus colors sampled from rendered elements (not defaults — this site overrides Bootstrap's stock palette).

| Role | Hex | RGB | Where used |
|---|---|---|---|
| **Primary (brand blue)** | `#2C6498` | `rgb(44, 100, 152)` | Buttons (`.btn`), "back to top" FAB, header/hero background band, link accents |
| **Secondary (body text gray)** | `#656565` | `rgb(101, 101, 101)` | Default body copy, nav text |
| **Light** | `#F4F8F1` | `rgb(244, 248, 241)` | Soft off-white/mint section backgrounds (alternating section bg) |
| **Dark** | `#1C2900` | — | Deep near-black olive, reserved dark tone (available as `--bs-dark` override; not heavily visible in observed pages) |
| **White** | `#FFFFFF` | `rgb(255, 255, 255)` | Dominant page background, card backgrounds |
| **WhatsApp CTA green** | `#008000` | `rgb(0, 128, 0)` | Floating WhatsApp contact button (bottom-right, all pages) |
| Bootstrap defaults kept as-is | `#198754` success, `#dc3545` danger, `#ffc107` warning, `#0dcaf0` info | — | Standard Bootstrap utility colors, not brand-specific |

**Palette character:** a confident corporate/industrial **navy blue** as the dominant brand color (buttons, CTAs, header bands), set against generous **white space**, with the red/orange logo as the only warm accent. This reads as trustworthy, clean, and technical — appropriate for a B2B equipment distributor.

## 4. Typography

| Use | Font | Weights loaded | Observed size/line-height |
|---|---|---|---|
| Headings (h1–h3) | **Poppins** | 200 (light), 600 (semibold), 700 (bold) | H1 hero: `56px / 700 / line-height 67.2px` (1.2 ratio) |
| Body copy, nav, buttons | **Open Sans** | 400 (regular), 500 (medium) | Base: `16px / 400 / line-height 24px` (1.5 ratio); nav links `20px / 400` |
| Buttons | Open Sans | 500 | `16px`, padding `8px 24px`, `border-radius: 5px` |

**Pairing logic:** geometric sans **Poppins** for display/heading weight (bold, confident, modern) + humanist sans **Open Sans** for readable body text — a very common, safe corporate pairing. Headings skew bold/heavy; body stays light/regular for contrast.

## 5. Layout & UI Components

- **Framework:** Bootstrap 5 grid/utilities (`container-fluid`, `.navbar`, `.btn`, `.card`-like product tiles).
- **Navbar:** logo left, horizontal nav links right (Home / Products / Brands / Catalog / Blogs / About Us), collapses to a hamburger icon below ~tablet width. Nav sits on a solid brand-blue band on interior pages; transparent-over-hero on the homepage.
- **Buttons:** solid brand-blue fill, white text, `5px` border-radius, medium font-weight — no heavy shadows or gradients, flat/modern style.
- **Cards (product/brand tiles):** white background, thin border, subtle shadow, generous internal padding, image on top, bold product/brand name below, brand/category name as a smaller blue sub-label.
- **Floating action buttons (persistent, bottom-right, all pages):**
  - WhatsApp contact button — green pill/circle with WhatsApp icon.
  - "Back to top" circular button — brand blue with white up-arrow icon.
- **Hero banners:** full-width photographic banner (real interior photography — modern office/lounge space, concrete walls, potted plants, wood furniture) with a large white page-title overlay (e.g. "About Us", "Catalog") and a soft diagonal white-to-transparent gradient scrim for text legibility. Same hero photo is reused across interior pages (About Us, Catalog) for visual consistency.
- **Geometric accent motif:** diagonal/angled shapes and diagonal image "frames" appear as decorative elements (e.g. the Catalog page product-grid graphic uses diagonal navy/light-blue stripes with product photos inset in angled frames). This diagonal-cut motif is a recurring brand signature, not just a one-off.
- **Product photography style:** clean, evenly lit product shots, isolated on white/transparent backgrounds, no lifestyle staging — a straightforward technical-catalog look.

## 6. Iconography

- Font Awesome 5.10 + Bootstrap Icons 1.4.1 — simple line/solid icons, no custom icon set observed.

## 7. Voice & Tone

- Tagline: **"Your One Stop Cleaning Solution."**
- Copy is short, benefit-first in English for UI chrome, with longer descriptive paragraphs in **Bahasa Indonesia** for company/about content — a bilingual B2B distributor voice: plain, professional, service-oriented ("berdedikasi untuk menyediakan produk-produk berkualitas...").

---

## Application Guidance for the New ERPNext E-commerce Site

The new site is a **separate, simple e-commerce storefront** — not a redesign of the landing page, and not tied to its content or IA. Carry over **brand identity only**:

**Reuse directly:**
- Primary brand blue `#2C6498` as the primary/CTA color; keep white as the dominant background.
- Poppins for headings / Open Sans for body — same pairing, same weight contrast (bold display, regular body).
- The Bestindo logo mark as-is for header/footer branding.
- Flat, `5px`-radius buttons in brand blue with white text.
- Clean, isolated product photography style (no busy lifestyle backgrounds) for product listing/detail pages — this matches how e-commerce product images are typically presented anyway.
- Optionally, the diagonal/angled geometric accent as a subtle section-divider or banner motif to keep a visual thread back to the parent brand, used sparingly (e.g. category banners), not as literal reused imagery.

**Do not carry over:**
- The landing page's specific hero photography (office/lounge interior) — it's tied to that page's messaging, not to the e-commerce product.
- Landing-page-specific IA (Products/Brands/Catalog/Blogs/About Us nav) — the e-commerce site needs its own IA (Shop/Categories/Cart/Checkout/Account/Orders), even though it can keep the same header/footer chrome styling.
- WhatsApp-first contact pattern — fine to keep as a support channel, but shouldn't replace a proper e-commerce cart/checkout flow.

**For ERPNext/Frappe implementation:** translate the palette and type scale into the site's theme CSS (custom SCSS variables or a theme override in the `bp` app's `public/` assets) rather than hardcoding colors inline, so the storefront can share one source of truth with any future desk-side theming.
