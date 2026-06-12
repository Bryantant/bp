# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`bp` is the custom Frappe/ERPNext v15 app for the **`bp.localhost`** site. Its purpose is to hold all customizations specific to that site — custom DocTypes, client/server scripts, print formats, scheduled tasks, and overrides that apply only to `bp.localhost`.

The bench is at `/Users/bryantantonio/Dev/benchv15`. The bench-level CLAUDE.md at `/Users/bryantantonio/Dev/benchv15/.claude/CLAUDE.md` is the authoritative guide for running services, bench commands, and cross-app conventions — read it first.

**Target site:** `bp.localhost` — runs on **port 8002** (`http://bp.localhost:8002`). Use `--site bp.localhost` for all `bench` commands.

**Apps installed on bp.localhost** (in load order): frappe, erpnext, atlantic_report, posawesome, hicom_feature_manager, hicom_custom_app, employee_self_service, hrms, bonana_custom_app, iib, print_designer, **bp**, frappe_assistant_core.

This app is currently a fresh scaffold. No custom DocTypes, server scripts, or client scripts have been added yet. All hooks in `bp/hooks.py` are commented out.

## App Structure

```
bp/              # Python package (app root)
  hooks.py       # Frappe entry point — wire up events, scheduled tasks, overrides here
  modules.txt    # Declares the single module: "BP"
  patches.txt    # One-time migration patches (empty)
  bp/            # Inner package (module-level code lives here)
  config/        # Desktop icon / module config
  patches/       # Patch scripts
  public/        # Static assets (JS, CSS, images)
  templates/     # Jinja page templates
```

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

# Clear cache
bench --site bp.localhost clear-cache
```

## Code Style

- **Python**: ruff with `line-length = 110`, tab indentation, `quote-style = "double"`. Target Python 3.10+.
- **JavaScript/SCSS**: prettier + eslint (quiet mode). Prettier uses defaults for JS/Vue/SCSS.
- Pre-commit enforces all of the above on every commit.

## Adding Features

When wiring up new functionality, the touch points in order are:

1. **DocType** — create via Frappe UI or JSON in `bp/bp/<module>/<doctype>/`; run `bench migrate` after.
2. **hooks.py** — register `doc_events`, `scheduler_events`, `doctype_js`, `override_doctype_class`, etc.
3. **public/js/** — client-side scripts loaded via `doctype_js` or `app_include_js` in hooks.
4. **patches/** — for one-time data migrations; register in `patches.txt`.
