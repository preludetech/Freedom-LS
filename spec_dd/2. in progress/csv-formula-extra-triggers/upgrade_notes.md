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

# Upgrade notes: csv-formula-extra-triggers

## Breaking changes

None to code: `escape_csv_formula` in `freedom_ls/base/csv_safety.py` keeps its signature, and
`FORMULA_TRIGGERS` keeps its name and its tuple-of-single-character-strings shape.

Exported CSV content changes. `escape_csv_formula` now prefixes `'` in more cases:

- a cell starting with a line feed or a full-width `＝`, `＋`, `－` or `＠`
  (these are now in `FORMULA_TRIGGERS`);
- a trigger that follows leading whitespace (anything `str.isspace()` accepts, such as a space,
  NBSP or the ideographic space);
- a trigger at the start of any line of a multi-line cell (lines split at `\r\n`, `\r` and `\n`),
  where the `'` is inserted at the start of that line.

Every FLS CSV export goes through this helper: the Django admin export (`FormulaSafeCSV` in
`freedom_ls/site_aware_models/admin_exports.py`), the panel-framework table export, and the
learner-import error CSV (`write_error_csv` in `freedom_ls/base/csv_import.py`). A downstream
process that reads FLS CSV exports back in will see the extra `'` marks, including inside
multi-line cells. Code that compares exported cells to the stored values, or strips only a single
leading `'`, needs to account for this.

## Manual steps

No action needed for most projects.

If your project wraps `escape_csv_formula` to add its own extra triggers (line feed, the
full-width operators, or leading whitespace), the wrapper is now redundant: delete it and call
`escape_csv_formula` directly.
