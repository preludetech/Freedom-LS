# QA report: extract_panels_framework-3-standalone-backend

Seventeen tests ran across three viewports. All seventeen passed and none failed. No bugs were found. The run re-checked the educator interface panels (learners, cohorts, audit log) after the PR 254 review fixes: bulk register runs, run requester and site scoping, CSV export and formula escaping, and the audit log layout at tablet width.

| Viewport | Pass | Fail |
|---|---|---|
| Desktop (1920x1080) | 11 | 0 |
| Mobile (375x812) | 4 | 0 |
| Tablet (768x1024) | 2 | 0 |

## Methodology

- Playwright MCP at 1920x1080, 375x812 and 768x1024. Screenshots were collected into this spec directory's `screenshots/` folder, and every referenced image exists beside this report. None was over 1 MB, so none was compressed.
- No frontend QA plan exists in the spec dir. `2. plan.md` says nothing a browser renders changes. The previous `qa_report.md` was passed as the plan. The user chose to re-run, so cases were re-derived from `1. spec.md` and weighted toward the PR 254 review fixes landed since the last QA: the site resolver's exceptions propagate and a non-Site result raises ImproperlyConfigured, the "no site" 422 before the bulk preview, `requested_by` recorded as the user with anonymous runs refused, W001 by subclass, W002, and the widened bulk-run scoping guard.
- Pre-step rebase: the branch already contained origin/main. Another process had just rebased it and was pushing it, so this run rebased nothing. That rebuild left the dev DB empty, so the first load of `/` returned 500 until `sdd:qa-data-helper` seeded it.
- Not driven in the browser, and why:
  - The "no site" 422 before the bulk preview. `settings_dev` pins `FORCE_SITE_NAME='DemoDev'`, so every dev request resolves a site. Unit tests in `panel_framework/tests/test_bulk_actions.py` cover it.
  - Anonymous run refusal. The panels need a login, so no anonymous user reaches a bulk action.
  - The resolver's ImproperlyConfigured and exception propagation, W001, W002 and the scoping guard. These are startup, check or test-time behaviour with no browser surface.
  - The background-task path over `BULK_BACKGROUND_THRESHOLD=250` rows.
- The collapsed Django debug toolbar tab shows at the right edge in the screenshots, as intended by the screenshot prep (collapsed, not open).

## Diff scoping

Class: **FULL**.

Changed files that triggered it:

- `freedom_ls/panel_framework/tests/standalone_templates/*.html` (16, test-only)
- `freedom_ls/panel_framework/{app_settings,apps,bulk_actions,bulk_runs,checks,config,csv_safety,field_display,housekeeping,models,sites,tables,views}.py`
- `freedom_ls/panel_framework/migrations/0002_bulk_action_run_site_has_no_reverse_accessor.py`
- `freedom_ls/educator_interface/views.py`
- `freedom_ls/qa_helpers/management/commands/qa_create_bulk_operations_scenario.py`
- `config/settings_base.py`, `pyproject.toml`, `uv.lock`, `.github/workflows/tests.yml`
- docs, plugin skills and tests

Skipped: nothing. Rule 1 fired on the test-only `.html` stand-ins, so the mobile and tablet passes focus on the panel pages whose server code changed.

## Smoke gate

Outcome: **pass**. Pages loaded: `/` and `/educator/organisations/northside/learners`.

The first load of `/` returned 500 before seeding: `FORCE_SITE_NAME` "DemoDev" matched no Site in the rebuilt-empty DB. Seeding (see Data changes) fixed it before the gate ran.

## Test results

| Test id | Viewport | Status | Screenshot | Notes |
|---|---|---|---|---|
| 0.smoke-home | desktop | pass | [link](screenshots/page-2026-11-19T04-02-37-290Z.png) | Dashboard renders as demodev after seeding; branch badge names this branch. Also the per-run capture check: the default-named file landed in qa-screenshots/ with no bytes returned. |
| 0.smoke-learners | desktop | pass | [link](screenshots/page-2026-11-19T04-02-47-714Z.png) | Learners panel list: 66 learners, 10 per page (7 pages), search, status filter, Export CSV, row checkboxes; sidebar column beside content. The formula-named learner renders as plain text. |
| 1.csv-export | desktop | pass | — | Export CSV on Northside learners downloads learners-2026-11-19.csv: UTF-8 BOM present, header plus 66 rows. Exercises the framework's own csv_safety copy. |
| 5.csv-formula-escaping | desktop | pass | — | Learner "=1+2 @SUM(A1)" exports as "'=1+2 @SUM(A1)": escape_csv_formula prefixes a quote. |
| 2.bulk-confirm | desktop | pass | [link](screenshots/page-2026-11-19T04-03-20-297Z.png) | Selecting 3 learners shows the selection bar. Register for a course opens the confirm dialog (512px, centred) with submit disabled until a course is picked, then reads "Register 3 learners for Course Pub?". The preview passed the new no-site check (site resolved via get_cached_site), so no 422. |
| 2.bulk-run | desktop | pass | [link](screenshots/page-2026-11-19T04-03-30-520Z.png) | Confirm POSTs `__actions/register_for_course` (200). Result dialog reads "3 learners changed."; rows refresh with Course Pub 0%. RecordedBulkAction.execute resolved the site and recorded the run with no PermissionDenied. |
| 3.date-format | desktop | pass | [link](screenshots/page-2026-11-19T04-03-38-385Z.png) | Audit log WHEN renders "19 Nov 2026, 04:03" (DATETIME_DISPLAY_FORMAT "j M Y, H:i"). WHO for the bulk-run entries is demodev@email.com. Per-object entries with no run summary are the previous run's B1, already filed (see General notes). |
| 2.bulk-run-cohorts | desktop | pass | [link](screenshots/page-2026-11-19T04-03-52-882Z.png) | Cohorts panel: Cohort C > Register for a course > Course Hid; preview "Register 1 cohort for Course Hid?"; result "1 cohort changed."; row now lists Course Hid; date column "19 Nov 2026, 04:01". |
| 4.run-requester | desktop | pass | — | Both browser-made runs (learners 149a7f75, cohorts 24d25f2e) have requested_by = accounts.User pk 10 (the requester as the user) and site = DemoDev pk 3, read back by sdd:qa-data-helper. |
| 4.run-status-scoping | desktop | pass | — | As demodev on DemoDev, GET learners/__runs/<id> with HX-Request: own run 149a7f75 returns 200 "3 learners changed."; the Bloom-site copy 5216fb1f returns 404 "This is no longer available"; an unknown id returns 404. BulkActionRun.objects.for_request scopes by the resolved site. Run at the 375 viewport; the check is viewport-independent. |
| 6.console | desktop | pass | — | Console errors were all expected: the pre-seed 500 on `/`, a favicon.ico 404 (predates this branch), and the two deliberate `__runs` 404s. |
| 0.smoke-learners | mobile | pass | [link](screenshots/page-2026-11-19T04-04-16-935Z.png) | Learners panel becomes stacked cards with Filter, Sort and Export CSV; nav collapses behind a menu button; formula-named learner renders as plain text. |
| 2.bulk-confirm | mobile | pass | [link](screenshots/page-2026-11-19T04-05-21-290Z.png) | Selection bar wraps its actions inside the card (1 selected, Select all 66, Clear). Confirm dialog is a full-width bottom sheet; title "Register 1 learner for Course Pub?" wraps; field and both buttons are inside the viewport. The shot page-2026-11-19T04-04-53-258Z.png is superseded: it was taken after a QA-side locator timeout (it picked a hidden duplicate checkbox) and shows the unchanged list. |
| 2.bulk-run | mobile | pass | [link](screenshots/page-2026-11-19T04-05-28-787Z.png) | Registering Bulk 04 for Course Pub returns "1 learner changed." in a bottom sheet. |
| 3.date-format | mobile | pass | [link](screenshots/page-2026-11-19T04-05-34-434Z.png) | Audit log cards: When "19 Nov 2026, 04:05", Who demodev@email.com in full, Target with avatar; the cohort run shows as "Cohort registered for course". |
| 3.audit-who-column | tablet | pass | [link](screenshots/page-2026-11-19T04-05-54-086Z.png) | Regression check of last run's B2 fix (9aed5ad93). At 768 WHO and TARGET are 192px; the actor reads "demodev@ema…" with an ellipsis and System shows in full. The table (938px) scrolls inside its 718px wrapper with no page-level overflow. Dates read "19 Nov 2026, 04:05". |
| 2.bulk-confirm | tablet | pass | [link](screenshots/page-2026-11-19T04-06-04-388Z.png) | At 768 the learners panel shows cards. The confirm dialog is centred at 512px wide with title "Register 2 learners for Course Hid?", and the field and both buttons are inside it. Confirm returned "2 learners changed.". |

## Design check

no design states tested

## Bugs

No bugs found.

## Layout probe

The probe's configured `header` region selector matched nothing on every page. It does not match this shell, so it is not a flag.

| Test id | Viewport | URL | Screenshot | Result |
|---|---|---|---|---|
| 0.smoke-home | desktop | / | [link](screenshots/page-2026-11-19T04-02-37-290Z.png) | clean |
| 0.smoke-learners | desktop | /educator/organisations/northside/learners | [link](screenshots/page-2026-11-19T04-02-47-714Z.png) | clean |
| 2.bulk-confirm | desktop | /educator/organisations/northside/learners | [link](screenshots/page-2026-11-19T04-03-20-297Z.png) | clean |
| 2.bulk-run | desktop | /educator/organisations/northside/learners | [link](screenshots/page-2026-11-19T04-03-30-520Z.png) | clean |
| 3.date-format | desktop | /educator/organisations/northside/audit-log | [link](screenshots/page-2026-11-19T04-03-38-385Z.png) | clean |
| 2.bulk-run-cohorts | desktop | /educator/organisations/northside/cohorts | [link](screenshots/page-2026-11-19T04-03-52-882Z.png) | clean |
| 0.smoke-learners | mobile | /educator/organisations/northside/learners | [link](screenshots/page-2026-11-19T04-04-16-935Z.png) | clean |
| 2.bulk-confirm-selection | mobile | /educator/organisations/northside/learners | [link](screenshots/page-2026-11-19T04-05-14-437Z.png) | clean |
| 2.bulk-confirm | mobile | /educator/organisations/northside/learners | [link](screenshots/page-2026-11-19T04-05-21-290Z.png) | clean |
| 2.bulk-run | mobile | /educator/organisations/northside/learners | [link](screenshots/page-2026-11-19T04-05-28-787Z.png) | clean |
| 3.date-format | mobile | /educator/organisations/northside/audit-log | [link](screenshots/page-2026-11-19T04-05-34-434Z.png) | clean |
| 3.audit-who-column | tablet | /educator/organisations/northside/audit-log | [link](screenshots/page-2026-11-19T04-05-54-086Z.png) | clean |
| 2.bulk-confirm | tablet | /educator/organisations/northside/learners | [link](screenshots/page-2026-11-19T04-06-04-388Z.png) | clean |

## Data changes

| Via | What changed |
|---|---|
| sdd:qa-data-helper | Seeded the empty per-branch dev DB (recreated by the other process's post-rebase rebuild): migrate (content_engine 0012 pending), `create_demo_data --yes`, `content_save demo_content DemoDev`, `qa_create_dev_org_baseline`, `qa_create_educator_interface_seed`, `qa_create_bulk_operations_scenario` (all `--site-name DemoDev`). Sites DemoDev, Bloom, Prelude, Wrend and Demo were created. |
| sdd:qa-data-helper | Renamed User 185 (bulk60@qa.test, Northside) to "=1+2 @SUM(A1)" for the CSV formula-escaping check. |
| sdd:qa-data-helper | Created BulkActionRun 5216fb1f-ce6d-481a-a395-db196b57ec47 on the Bloom site (copy of DemoDev run 149a7f75..., requested_by User 10) for the cross-site run-status check. |

## Bug status

No bugs were found, so there is nothing to track.

## General notes

- The audit log still writes per-object entries with no `bulk_action.completed` summary or shared run_id. That is the previous run's B1, closed as WONTFIX for this spec and filed as `spec_dd/1. next/bulk-run-audit-summary/idea.md`. It was observed again and not re-filed.
- The favicon.ico 404 predates this branch.
- The Bloom-site BulkActionRun copy is a test artefact created only for the cross-site status check.

status: ok · reason: report rendered, 0 bugs documented, screenshots verified
