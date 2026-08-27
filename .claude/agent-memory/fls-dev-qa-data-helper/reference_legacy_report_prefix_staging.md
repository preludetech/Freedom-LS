# Staging a legacy `reports/` prefix GeneratedReport (pre-rename row)

Asked for during the prod_bucket_setup storage-layout regression QA (Aug 2026).

## Goal

Make one `freedom_ls.reports.GeneratedReport` row look like it was generated BEFORE the
`reports/` -> `cohort_reports/` key-prefix rename: `file.name` starts with `reports/` and the
PDF physically exists ONLY at `MEDIA_ROOT/reports/<pk>-cohort-report.pdf`.

## Recipe

1. `cp media/cohort_reports/<pk>-cohort-report.pdf media/reports/<pk>-cohort-report.pdf`
   (`mkdir -p media/reports` first).
2. `GeneratedReport.objects.filter(pk=<pk>).update(file="reports/<pk>-cohort-report.pdf")`
   — queryset `.update()` on purpose, so no `save()` hooks / re-render side effects fire.
3. `rm media/cohort_reports/<pk>-cohort-report.pdf` (single named file, never `rm -r` or a glob).
   Skipping step 3 makes the test vacuous: the file would still resolve at the new path.

## Gotcha: in dev, ALL storage aliases share MEDIA_ROOT

`config/settings_base.py` (~line 266) declares all six aliases as bare `FileSystemStorage`
with **no OPTIONS/LOCATION**, deliberately, so the test suite's tmp-dir MEDIA_ROOT isolation
covers every alias for free. Consequence for QA:

- `report.file.storage.location == MEDIA_ROOT` (not `MEDIA_ROOT/cohort_reports`).
- So a legacy `reports/...` name still returns `storage.exists() == True` in dev. The only
  thing separating aliases in dev is the **key prefix inside `upload_to`**, not the directory
  root. Do not read "exists: True" as "the rename never happened".
- The `file-storage` skill's phrase "every alias resolves to its own MEDIA_ROOT subtree" is
  about prefixes, not about per-alias `location`.

`GeneratedReport.file.upload_to` is the callable `report_upload_path` (freedom_ls/reports),
which is what emits the current `cohort_reports/` prefix.

## Report-row inventory used (dev DB, this worktree)

- a817018a-… QA Storage Cohort  — left on `cohort_reports/`
- eb5beced-… QA Other Cohort    — left on `cohort_reports/`
- ef4233fa-… QA Storage Cohort  — staged as legacy `reports/`

To undo: copy back to `cohort_reports/`, `.update(file="cohort_reports/…")`, delete the
`reports/` copy. Do not regenerate the report — that would change the pk/filename.
