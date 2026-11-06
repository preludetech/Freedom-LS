---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: sdd-chain-throwaway-plain

Adds two pure display helpers. Nothing in FLS calls them yet, and no model, template, setting or
package changed.

- `freedom_ls.health.durations.format_duration(seconds)` returns hours and zero-padded minutes,
  e.g. `3720` → `1h 02m`. Leftover seconds are dropped, not rounded.
- `freedom_ls.form_engine.score_display.format_score(earned, possible)` returns
  `earned / possible`, e.g. `(7, 10)` → `7 / 10`.

Both raise `ValueError` for negative input.

## Breaking changes

None

## Manual steps

None. No action needed.
