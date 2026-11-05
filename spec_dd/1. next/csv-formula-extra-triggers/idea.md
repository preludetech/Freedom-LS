# Idea: wider spreadsheet-formula escaping for CSV exports

## What

`escape_csv_formula` in `freedom_ls/base/csv_safety.py` prefixes a cell with `'` when it starts with
one of `=`, `+`, `-`, `@`, tab or carriage return. Spreadsheets also act on a cell that starts with a
line feed, and some treat the full-width forms `＝` (U+FF1D), `＋` (U+FF0B), `－` (U+FF0D) and `＠`
(U+FF20) as their ASCII twins. Add those to the triggers so every FLS CSV export neutralises them.

## Why

Every CSV export in FLS goes through this helper: the admin export in
`site_aware_models.admin_exports` and the panel-framework table export. Cells in those exports carry
text that visitors and learners typed, so a gap in the trigger list is a formula-injection gap in
every export at once. First-Class-LMS closed it locally for its lead CSV by wrapping the helper.

## Reference implementation

First-Class-LMS, `apps/admin_dashboard/lead_csv.py` (`EXTRA_FORMULA_TRIGGERS`,
`escape_visitor_text`), which checks the extra characters and then defers to `escape_csv_formula`.
The project would delete its wrapper once FLS covers them.

## Settled

- The change belongs in `freedom_ls/base/csv_safety.py`, so every export picks it up without changes
  of its own.

Found during `/fls-dev:update_concrete_projects` (pull-in from First-Class-LMS, 2026-11-04).
