# QA report: extract_panels_framework-5-package-and-install

Result: all tests passed. No bugs.

## Methodology

Screenshots were collected into `spec_dd/2. in progress/extract_panels_framework-5-package-and-install/screenshots/`. Every image referenced below exists beside this report. The run did not abort at the smoke gate, so every step ran. The test plan is `3. frontend_qa.md`. Desktop, mobile (375) and tablet (768) viewports were used.

## Diff scoping

Class: **FULL**. Changed files that triggered it:

- `freedom_ls/panel_framework/**` (removed; templates, static and css now come from the installed django-panel-framework package)
- `freedom_ls/base/templates/cotton/*` (unchanged overrides)
- `config/urls.py`
- `config/settings_base.py`
- `pyproject.toml`
- `uv.lock`
- `package.json`

Nothing was skipped. Desktop, mobile and tablet passes all ran.

## Smoke gate

Outcome: **pass**. Pages loaded: `/` and `/educator/organisations/demodev/dashboard`.

## Design check

No design states tested. No test named a design screenshot, so the design check did not apply.

## Layout probe

| Test id | Viewport | URL | Screenshot | Result |
|---|---|---|---|---|
| 1.1a | desktop | see test record | ![](screenshots/page-2026-11-27T10-51-20-857Z.png) | clean |
| 1.1b | desktop | see test record | ![](screenshots/page-2026-11-27T10-51-37-466Z.png) | clean |
| 1.1c | desktop | see test record | ![](screenshots/page-2026-11-27T10-51-51-257Z.png) | clean |
| 1.1d | desktop | see test record | ![](screenshots/page-2026-11-27T10-52-38-552Z.png) | clean |
| 1.1e | desktop | see test record | ![](screenshots/page-2026-11-27T10-54-01-549Z.png) | clean |
| 1.1g | desktop | see test record | ![](screenshots/page-2026-11-27T10-54-40-033Z.png) | clean |
| 1.1k | desktop | see test record | ![](screenshots/page-2026-11-27T10-56-09-899Z.png) | clean |
| 1.1-all | mobile | see test record | no screenshot | clean |
| 1.1-all | tablet | see test record | no screenshot | clean |

## Data changes

| What changed | Command | Files written |
|---|---|---|
| Seeded the fresh per-branch dev DB: DemoDev site, demo users and cohorts, then demo content | `create_demo_data --yes`, then `content_save demo_content DemoDev` | none |

## Bug status

No bugs recorded, so there are no rows.

| Bug | Status |
|---|---|
| none | n/a |

## Test results

All tests passed.

| Test | Viewport | Result | Notes | Screenshot |
|---|---|---|---|---|
| 0.1 | desktop | pass | No pending migrations, no NodeNotFoundError. Tailwind build ok. Both css paths point into the installed `panel_framework` package. `freedom_ls/panel_framework` is gone. | none |
| 0.2 | desktop | pass | The fresh DB had no DemoDev site, so demo data was seeded (see Data changes). Cohort 2025.03.04 holds 50 learners. | none |
| 1.1a | desktop | pass | Educator dashboard: panels are cards, no `panel-btn`, FLS icon names, no console error. Also confirmed screenshot capture lands in `screenshots/`. | ![](screenshots/page-2026-11-27T10-51-20-857Z.png) |
| 1.1b | desktop | pass | Cohorts list styled: table, status pills, toolbar, `btn btn-primary` buttons. | ![](screenshots/page-2026-11-27T10-51-37-466Z.png) |
| 1.1c | desktop | pass | Search plus Show inactive: filter chip and Clear all render as pills. | ![](screenshots/page-2026-11-27T10-51-51-257Z.png) |
| 1.1d | desktop | pass | Ran on the Learners list (see plan corrections). Three rows selected, selection bar slid in. Cohort learners tab is shown separately. | ![](screenshots/page-2026-11-27T10-52-38-552Z.png) ![](screenshots/page-2026-11-27T10-52-24-159Z.png) |
| 1.1d-menu | desktop | pass | Selection bar More menu opens with three actions. | ![](screenshots/page-2026-11-27T10-52-46-628Z.png) |
| 1.1e | desktop | pass | Learners page 2: "Showing 11-20 of 50", numbered pager. | ![](screenshots/page-2026-11-27T10-54-01-549Z.png) |
| 1.1f | desktop | pass | At 1920 sorting is by column header links (Sort button hidden by design). Sort menu checked at 768. | ![](screenshots/page-2026-11-27T10-59-11-610Z.png) |
| 1.1g | desktop | pass | Learner page renders panels, status chip and FLS `btn` row buttons. | ![](screenshots/page-2026-11-27T10-54-40-033Z.png) |
| 1.1h | desktop | pass | Quick view of Cohort 2025.04.06 opens as a side panel, page behind undimmed. | ![](screenshots/page-2026-11-27T10-54-54-453Z.png) |
| 1.1i | desktop | pass | Empty create-cohort submit: 422, dialog stays open, error callout plus field error. The only console error is the browser's network log of that 422. | ![](screenshots/page-2026-11-27T10-55-14-776Z.png) |
| 1.1j | desktop | pass | Cohort Settings > Deactivate: centred confirm, dimmed backdrop, "Reason (optional)" field. Bulk deactivate confirm has no reason field (see plan corrections). | ![](screenshots/page-2026-11-27T10-55-59-881Z.png) ![](screenshots/page-2026-11-27T10-55-28-939Z.png) |
| 1.1k | desktop | pass | `/accounts/` personal details renders and edits inline. Add email dialog opens centred with `btn` classes. | ![](screenshots/page-2026-11-27T10-56-09-899Z.png) ![](screenshots/page-2026-11-27T10-56-19-056Z.png) |
| 1.3.1 | desktop | pass | Learners list bulk Add to cohort on three rows: "3 learners changed.", table refreshed. One BulkActionRun row in `panel_framework_bulkactionrun`. | ![](screenshots/page-2026-11-27T10-53-13-362Z.png) |
| 1.3.2 | desktop | pass | Same bulk action again: "Nothing to change: all 3 selected learners will be skipped.", confirm disabled, no server error. | ![](screenshots/page-2026-11-27T10-53-52-637Z.png) |
| 1.3.3 | desktop | pass | Empty create submit returns 422, dialog stays open with the errors. | ![](screenshots/page-2026-11-27T10-55-14-776Z.png) |
| 1.3.4 | desktop | pass | Escape closes the quick view and focus returns to its trigger. | ![](screenshots/page-2026-11-27T10-54-54-453Z.png) |
| 1.3.5 | desktop | pass | Sorted and filtered, then reloaded: URL kept `learners-sort` and `learners-cohort`, same three rows. | ![](screenshots/page-2026-11-27T10-54-29-921Z.png) |
| 2.1 | desktop | pass | `/panel-framework/components/` returns 200 inside FLS chrome, 7 tables and example dialogs styled, no console error. | ![](screenshots/page-2026-11-27T10-56-27-557Z.png) |
| 2.2 | desktop | pass | Logged out, the reference URL redirects to `/admin/login/?next=/panel-framework/components/`. | none |
| 2.3 | desktop | pass | `/panel-framework/does-not-exist/` returns 404 (technical 404 under DEBUG, see general notes). | none |
| 3.1 | desktop | pass | Table check prints "False True". | none |
| 3.2 | desktop | pass | `showmigrations`: panel_framework 0001_initial and educator_interface 0001-0004 all applied. | none |
| 3.3 | desktop | pass | `/admin/` loads. A user's permissions list holds 440 options: none for `freedom_ls_panel_framework`, four for "Panel framework \| bulk action run". Only console error is the known RelatedObjectLookups.js unload policy entry. | none |
| 1.1-all | mobile | pass | Six pages at 375: no horizontal overflow, no layout flags, no `panel-btn`, tables as cards, nav toggle beside heading. | ![](screenshots/page-2026-11-27T10-58-47-087Z.png) |
| 1.1e | mobile | pass | Learners footer shows Previous and Next. | none |
| 1.1f | mobile | pass | Filter sheet opens as a full-width bottom sheet, 16px rounded top corners, pill status chips. | ![](screenshots/page-2026-11-27T10-58-18-328Z.png) |
| 1.1d | mobile | pass | Three cards selected, selection bar sticks under the header while scrolling. | ![](screenshots/page-2026-11-27T10-58-28-246Z.png) |
| 1.1i | mobile | pass | Create cohort dialog is a bottom sheet with rounded top, footer buttons fit. | ![](screenshots/page-2026-11-27T10-58-39-141Z.png) |
| 1.1-all | tablet | pass | Same six pages at 768: no overflow, no layout flags, no `panel-btn`, numbered pager. | none |
| 1.1f | tablet | pass | Sort menu open, toolbar on one row. | ![](screenshots/page-2026-11-27T10-59-11-610Z.png) |
| 1.1i | tablet | pass | Create cohort dialog centred (128-640 of 768) with dimmed backdrop. | none |

## General notes

### Plan corrections (not bugs)

The test plan had two wrong assumptions. Neither is a defect in the branch.

1. The plan put selection and bulk actions on a cohort's learners table. They are on the Learners and Cohorts lists, so tests 1.1d and 1.3.1 to 1.3.2 ran there.
2. The plan expected a reason field on every deactivate confirm. Only the single-record Deactivate action asks for a reason. Bulk deactivate confirms carry none.

### Observations unrelated to this branch

- The admin login title reads "Log in | None".
- Under DEBUG, an unknown URL shows Django's technical 404, not FLS's branded 404.

### Not tested

Nothing was skipped.

status: ok · reason: report rendered, 0 bugs documented
