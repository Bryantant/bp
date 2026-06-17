# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`bp` is the custom Frappe/ERPNext **v16** app for the **`bp.localhost`** site. Its purpose is to hold all customizations specific to that site — custom DocTypes, client/server scripts, workspaces, desk overrides, print formats, scheduled tasks, and overrides that apply only to `bp.localhost`.

The bench is at `/Users/bryantantonio/Dev/benchv16`. The bench-level CLAUDE.md at `/Users/bryantantonio/Dev/benchv16/CLAUDE.md` is the authoritative guide for running services, bench commands, and cross-app conventions — read it first.

**Target site:** `bp.localhost` — served on **port 8104** (`http://bp.localhost:8104`). Use `--site bp.localhost` for all `bench` commands. Developer mode is enabled on this site.

**Apps installed on bp.localhost** (in load order): frappe, erpnext, **bp**.

## What's in this app

This is no longer a bare scaffold. Current customizations:

- **DocTypes** (`bp/bp/doctype/`): `bp_settings`, `bp_print_lock_reset_role`, `bp_invoice_print_log` — supporting an invoice print-lock feature.
- **Workspace** (`bp/bp/workspace/setup/`): a "Setup" workspace grouping Master and Trading shortcuts.
- **Workspace Sidebar** (`bp/workspace_sidebar/setup.json`) and **Desktop Icon** (`bp/desktop_icon/setup.json`): a custom "Setup" sidebar/icon for the same links.
- **Desk overrides** (`bp/public/js/desk_overrides.bundle.js`): hides Help/About/Frappe Support from the desk menu and starts the sidebar collapsed on form/list pages. Loaded as a bundle via `app_include_js` in `hooks.py`.
- **Boot extension** (`bp/boot.py`): `boot_session` relabels app titles in the desk sidebar (e.g. ERPNext → "Hicom System") via the `extend_bootinfo` hook — no core files touched.

## App Structure

```
bp/                       # Python package (app root)
  hooks.py                # Frappe entry point — events, scheduled tasks, includes, overrides
  boot.py                 # extend_bootinfo: boot_session() relabels sidebar app titles
  modules.txt             # Declares the single module: "BP"
  patches.txt             # One-time migration patches
  bp/                     # Inner package (module-level code)
    doctype/              # Custom DocTypes (JSON + controller .py)
    workspace/            # Desk workspace definitions (setup/setup.json)
    page/                 # Custom desk pages
  desktop_icon/           # Desktop Icon fixture (setup.json)
  workspace_sidebar/      # Workspace Sidebar fixture (setup.json)
  config/                 # Desktop icon / module config
  patches/                # Patch scripts
  public/                 # Static assets (JS, CSS, images)
    js/desk_overrides.bundle.js   # bundled desk JS, loaded via app_include_js
  templates/              # Jinja page templates
```

> **Note on `.bundle.js`:** Frappe's build pipeline compiles `*.bundle.js` files. `app_include_js` references the bundle by basename (`desk_overrides.bundle.js`), not by `/assets/...` path. The built output lives in `dist/` (gitignored). Run `bench build --app bp` after editing bundle sources.

## Commands

```bash
# Run tests for this app
bench --site bp.localhost run-tests --app bp

# Run a single test file
bench --site bp.localhost run-tests --app bp --doctype <test_file_name>

# Lint and format (manual)
cd apps/bp && pre-commit run --all-files

# Set up pre-commit (one-time per dev machine)
cd apps/bp && pre-commit install

# Sync schema after modifying DocType JSON
bench --site bp.localhost migrate

# Rebuild JS/CSS assets (after editing *.bundle.js or CSS)
bench build --app bp

# Clear cache (always after Server Script changes; migrate does NOT clear it)
bench --site bp.localhost clear-cache
```

## Code Style

- **Python**: ruff with `line-length = 110`, tab indentation, `quote-style = "double"`. Target Python 3.10+.
- **JavaScript/SCSS**: prettier + eslint (quiet mode). Prettier uses defaults for JS/Vue/SCSS.
- Pre-commit enforces all of the above on every commit.

## Adding Features

When wiring up new functionality, the touch points in order are:

1. **DocType** — create via Frappe UI or JSON in `bp/bp/doctype/<doctype>/`; run `bench migrate` after.
2. **hooks.py** — register `doc_events`, `scheduler_events`, `doctype_js`, `override_doctype_class`, `extend_bootinfo`, etc.
3. **public/js/** — client-side scripts. Desk-wide JS goes in `desk_overrides.bundle.js` (loaded via `app_include_js`); rebuild with `bench build --app bp`.
4. **patches/** — for one-time data migrations; register in `patches.txt`.
