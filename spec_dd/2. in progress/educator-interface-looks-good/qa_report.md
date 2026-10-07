# Frontend QA report: educator interface looks good

- Run date: 2026-10-07
- Branch: educator-interface-looks-good
- Dev server port: 8332
- Logged in as: demodev@email.com (plus a single-org educator, Quinn Okafor, and a learner where noted)

## Methodology

- Playwright MCP, driven by hand.
- Desktop at 1442 (plan width) and at 1920x1080, 1280 and 1024.
- Phone at 392x812. This is the plan width and was used instead of 375.
- Tablet at 768x1024.
- Screenshots were collected into `screenshots/` beside this report. Every image referenced here exists there. The folder also holds a few `.yml` snapshot files and `.log` console files that were moved along with the screenshots.
- Seed: `qa_create_educator_looks_good_seed` was re-run (it is idempotent). The qa-data-helper agent added a single-org educator (Quinn Okafor) with a new, uncommitted command, `freedom_ls/qa_helpers/management/commands/qa_create_single_org_educator.py`.

## Diff scoping

Class: FULL. Templates, static JS and CSS changed, so desktop, mobile and tablet all ran. Nothing was skipped.

Changed files that drove the classification:

- `freedom_ls/panel_framework/templates/**`
- `freedom_ls/educator_interface/templates/**`
- `freedom_ls/base/templates/**`
- `freedom_ls/*/static/**/*.js`
- `freedom_ls/themes/first_class/static/themes/first_class/theme.css`
- `tailwind.components.css`
- plus .py and spec files

## Smoke gate

Pass. Pages checked: `/` and `/educator/organisations/demodev/learners`. No failure URL or reason.

## Results

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 1.2 | desktop | pass | Switcher, nav labels, active item and user block match; sidebar rule runs to the footer (second screenshot). | ![](screenshots/page-2026-10-07T06-07-08-220Z.png) ![](screenshots/page-2026-10-07T06-07-39-628Z.png) |
| 1.3 | desktop | pass | Nav clicks swap main without reload; URL and active style follow. | none |
| 1.4 | desktop | pass | Cohort page sidebar stays flat, Cohorts marked, no expand control. | ![](screenshots/page-2026-10-07T06-08-33-194Z.png) |
| 6.2 | desktop | pass | Back link, Edit/Delete level with title, tabs, stacked cards, flush table. | ![](screenshots/page-2026-10-07T06-08-33-194Z.png) |
| 1.5 | desktop | pass | Popover lists all orgs; long name wraps in list and truncates on trigger. Popover sits ~48px right of the trigger edge (see notes). | ![](screenshots/page-2026-10-07T06-09-49-133Z.png) ![](screenshots/page-2026-10-07T06-10-19-867Z.png) |
| 1.6 | desktop | pass | Tab order and focus rings correct; Enter, arrows, Escape work and focus returns to trigger. | ![](screenshots/element-2026-10-07T06-10-44-078Z.png) |
| 1.7 | desktop | pass | At 1024 sidebar docked 256px, no overflow; cohort header does not wrap. | ![](screenshots/page-2026-10-07T06-10-57-278Z.png) |
| 1.9 | desktop | pass | First Tab lands on the site header logo link. | none |
| 3.2 | desktop | **fail** | Card, search, rows, pager match. Sortable header labels are primary blue rgb(43,108,176), not muted. Last Name sort icon shrinks when the label wraps (B1, B4). | ![](screenshots/page-2026-10-07T06-11-17-905Z.png) |
| 3.3 | desktop | pass | Search filters without reload; clearing restores 10 rows. | none |
| 3.4 | desktop | pass | Sort icon, order, "Sorted by" text and page reset work; second click descends. | none |
| 3.5 | desktop | pass | Pager changes rows without reload; URL carries `learners-page=`. | none |
| 3.6 | desktop | pass | Row hover tint; cohort link opens cohort detail. | ![](screenshots/page-2026-10-07T06-12-25-132Z.png) |
| 3.6a | desktop | pass | Name link navigates; eye opens quick panel without navigating. Same on cohorts list. | ![](screenshots/page-2026-10-07T06-12-36-212Z.png) |
| 3.6b | desktop | pass | Name link and quick-view are separate Tab stops with rings. | none |
| 3.7 | desktop | pass | Single centred muted "Nothing to see" row, no pager. | ![](screenshots/page-2026-10-07T06-13-42-228Z.png) |
| 3.8 | desktop | pass | Cohorts and courses share the card shape; second-org data scoped correctly; notifications pager keeps btn-sm. | ![](screenshots/page-notifications-pager.png) |
| 3.9 | tablet | pass | 768: table layout, no page horizontal scroll, search 288px. | ![](screenshots/page-2026-10-07T06-14-39-778Z.png) |
| 9.1-9.5 | desktop | pass | Quick panel docks right under the header, 1px left rule, no shadow; close, open-full-page and focus return work; page layout unchanged on open/close. | ![](screenshots/page-2026-10-07T06-12-36-212Z.png) |
| 5.2 | desktop | pass | Learner detail: back link, title band, 3-column Details grid, edge-to-edge cohorts table. | ![](screenshots/page-2026-10-07T06-15-11-528Z.png) |
| 5.3 | desktop | pass | Cohort link opens cohort; back link returns without reload. | none |
| 5.4 | desktop | pass | 40+ character email wraps inside its cell. | ![](screenshots/page-2026-10-07T06-15-11-528Z.png) |
| 6.2a | desktop | pass | Learners tab swaps only the region; URL `/__tabs/learners`; reload and Back behave. | none |
| 6.3 | desktop | pass | Rename updates card and h1; duplicate shows inline error with dialog open. Tab title keeps old name until reload; URL becomes `/__tabs/details`. | ![](screenshots/page-edit-duplicate.png) |
| 6.4 | desktop | pass | Learners tab sort, page and search swap only that table; URL carries state. | ![](screenshots/page-cohort-learners-tab.png) |
| 6.5 | desktop | pass | Delete confirmation on QA Created Cohort; Cancel leaves cohort intact. | ![](screenshots/page-delete-confirm-desktop.png) |
| 7.2 | desktop | pass | Centred dialog, Name field only, Cancel then Create Cohort right-aligned. | ![](screenshots/page-create-desktop.png) |
| 7.3 | desktop | pass | Close paths work; dirty Escape/X show "Discard changes?" in place of the form; backdrop click keeps the form open. | ![](screenshots/page-discard-desktop.png) |
| 7.4 | desktop | pass | Empty submit blocked by native validation; duplicate shows inline error. | none |
| 7.5 | desktop | pass | Created cohort redirects to its page, listed once, duplicate rejected. | none |
| 7.9 | desktop | pass | Refusal dialog for QA Looks Cohort has only Cancel; backdrop click closes. | ![](screenshots/page-delete-dialog-desktop.png) |
| 1.5-single-org | desktop | pass | Single-org educator: same bordered shell, no caret, not a button. | ![](screenshots/page-single-org-named-user.png) |
| 1.8 | desktop | pass | User block correct for both a user with no name and a named user; gear opens `/accounts/profile/`. | ![](screenshots/page-single-org-named-user.png) |
| 2.2 | mobile | **fail** | Layout matches, but the toggle shows a chevron, not a menu icon (B2). | ![](screenshots/page-mobile-learners.png) |
| 2.3 | mobile | pass | Bottom sheet over dimmed page with correct contents and order. | ![](screenshots/page-mobile-navsheet.png) |
| 2.4-2.7 | mobile | pass | Sheet close, navigation, inline switcher, Escape and backdrop all work. | ![](screenshots/page-mobile-switcher-open.png) |
| 2.8 | mobile | pass | 40-char org name truncates, no overflow. | ![](screenshots/page-mobile-longorg.png) |
| 4.2 | mobile | **fail** | List layout matches; secondary line has bold full-contrast last name (B3). | ![](screenshots/page-mobile-learners.png) |
| 4.3 | mobile | pass | Long name/email row wraps, no horizontal scroll. | ![](screenshots/page-mobile-longrow.png) |
| 4.4 | mobile | pass | Filter & sort sheet matches; options sit in a bordered fieldset the design does not draw. | ![](screenshots/page-mobile-sortsheet.png) |
| 4.5-4.9 | mobile | pass | Sort, Reset, Cancel, pager and sheet separation all work. | ![](screenshots/page-mobile-pager.png) |
| 4.10 | mobile | pass | JS off: sort form inline and works via full page load; renders above the rows, not below the list as the plan says. | ![](screenshots/page-mobile-nojs-top.png) |
| 5.5-5.6 | mobile | pass | Learner detail: back link beside toggle, 2-column Details, cohort rows with chevrons. | ![](screenshots/page-mobile-learner-detail.png) |
| 6.6-6.7 | mobile | pass | Cohort detail fits, no overflow; Learners tab sort opens the sheet, not navigation. | ![](screenshots/page-mobile-cohort-detail.png) |
| 7.6-7.9 | mobile | pass | Bottom sheet create/delete/refusal; short-height header stays visible; resize to 1442 gives the centred card. | ![](screenshots/page-mobile-create.png) |
| 9.6 | mobile | pass | 1000: 480px drawer; 392: bottom sheet; non-modal, Escape returns focus. | ![](screenshots/page-quickview-392.png) |
| 2.9 | mobile | pass | Player outline toggle and sheet work at 392; docked outline at 1442. | ![](screenshots/page-player-outline-392.png) |
| 8.1 | desktop | pass | No dark mode in either theme; page stays fully light under a dark preference. | ![](screenshots/page-dark-learners.png) |
| 8.2 | desktop | pass | Contrast checked on default build; muted text 7.53:1, sortable th link 5.42:1; first_class muted about 5.4:1. | none |
| 8.3 | mobile | pass | Touch targets 44x48 or 44x44; the Cohorts expand control no longer exists. | none |
| 8.4 | mobile | pass | Focus rings present; focus stays inside the modal sheets. | none |
| 8.5 | mobile | pass | Transitions 0.2s; none under reduced motion. | none |
| 8.6 | mobile | pass | Learner course list, course page and player render at 392 and 1442; notifications pager uses btn-sm. | ![](screenshots/page-learner-courses-392.png) |
| 8.7 | desktop | pass | `/panel-framework/components/` returns 200, no breakage. | ![](screenshots/page-components.png) |
| 8.8 | desktop | pass | Only expected 422 console errors, plus one cross-origin block on a learner course page. | none |
| 8.9 | desktop | pass | Canvas colour checked on default and first_class builds; first_class left in place. | ![](screenshots/page-fc-learners.png) |
| 8.10 | desktop | **fail** | first_class design pass at 1442 and 392 matches except the misses under 3.2, 2.2 and 4.2. | ![](screenshots/page-fc-learners.png) |
| tablet-nav-cohort-dialog | tablet | pass | Mobile navigation and bottom sheet; cohort page fits; Edit opens as a centred 512px card. Toggle shows the same chevron (B2). | ![](screenshots/page-tablet-cohort.png) |
| 3.9-tablet-table | tablet | **fail** | No page scroll, but the Last Name sort icon is squeezed to a dot (B4). | ![](screenshots/page-2026-10-07T06-14-39-778Z.png) |

## Design check

| Test | Viewport | This run | Design | Result |
|---|---|---|---|---|
| 1.2-design | desktop | ![](screenshots/page-2026-10-07T06-07-08-220Z.png) | ![](design_screenshots/sidebar__264.png) | pass |
| 6.2-design | desktop | ![](screenshots/page-2026-10-07T06-08-33-194Z.png) | ![](design_screenshots/educator-cohorts-and-admin__05-cohort-detail.png) | pass |
| 3.2-design | desktop | ![](screenshots/page-2026-10-07T06-11-17-905Z.png) | ![](design_screenshots/educator-learners__02-learners-table.png) | fail: table header labels are bold mono uppercase but the sortable ones are primary-coloured link text, not muted |
| 5.2-design | desktop | ![](screenshots/page-2026-10-07T06-15-11-528Z.png) | ![](design_screenshots/educator-learners__03-learner-detail.png) | pass |
| 7.2-design | desktop | ![](screenshots/page-create-desktop.png) | ![](design_screenshots/educator-cohorts-and-admin__07-create-cohort-modal.png) | pass |
| 2.2-design | mobile | ![](screenshots/page-mobile-learners.png) | ![](design_screenshots/educator-mobile-dashboard__m01-dashboard.png) | fail: the navigation toggle shows a chevron (menu_open maps to chevron-right), not a menu icon |
| 2.3-design | mobile | ![](screenshots/page-mobile-navsheet.png) | ![](design_screenshots/educator-mobile-dashboard__m02-navigation-drawer.png) | pass |
| 4.2-design | mobile | ![](screenshots/page-mobile-learners.png) | ![](design_screenshots/educator-mobile-learners__m03-learners-list.png) | fail: muted secondary line; the last name in the secondary line is bold and full-contrast |
| 4.4-design | mobile | ![](screenshots/page-mobile-sortsheet.png) | ![](design_screenshots/educator-mobile-learners__m04-filter-and-sort-sheet.png) | pass |
| 5.5-design | mobile | ![](screenshots/page-mobile-learner-detail.png) | ![](design_screenshots/educator-mobile-learners__m05-learner-detail.png) | pass |
| 6.6-design | mobile | ![](screenshots/page-mobile-cohort-detail.png) | ![](design_screenshots/educator-mobile-cohorts-and-admin__m08-cohort-detail.png) | pass |
| 7.6-design | mobile | ![](screenshots/page-mobile-create.png) | ![](design_screenshots/educator-mobile-cohorts-and-admin__m10-create-cohort.png) | pass |

## B1: Sortable table header labels use the primary link colour instead of muted

Manifestations:

- 3.2 (desktop)
- 3.2-design (desktop)
- 8.10 (desktop, first_class build)

![](screenshots/page-2026-10-07T06-11-17-905Z.png)
![](screenshots/page-fc-learners.png)

Expected: every table header label is bold mono uppercase and muted (the th's text-muted), sortable ones included, per the 3.2 checklist and the plan (the th is "already muted"; the sortable link only gains no-underline).

Actual: the sortable header `<a>` in `cotton/data-table.html` inherits the global link colour: rgb(43,108,176) on the default build and #283593 on first_class. Non-sortable headers are muted rgb(74,85,104) / #5F6B7F.

## B2: Educator navigation toggle shows a chevron instead of a menu icon

Manifestations:

- 2.2 (mobile)
- 2.2-design (mobile)
- tablet-nav-cohort-dialog (tablet)

![](screenshots/page-mobile-learners.png)
![](screenshots/page-tablet-cohort.png)

Expected: the content-header navigation toggle shows a menu (hamburger) icon, per the 2.2 checklist and the plan's icon table ("Menu icon (content header toggle)").

Actual: `educator_interface/interface.html` sets `panel_toggle_icon` to `<c-icon name="menu_open">`. `menu_open` maps to chevron-right in three of the four icon sets (list in the fourth), so a chevron is drawn.

## B3: Mobile learner row secondary line is not muted (last name bold, full contrast)

Manifestations:

- 4.2 (mobile)
- 4.2-design (mobile)

![](screenshots/page-mobile-learners.png)

Expected: each mobile row has a bold name line and a muted secondary line, per the 4.2 checklist and design m03.

Actual: the secondary line begins with the last name in bold (700), full-contrast text rgb(26,35,50). Only the trailing registered-courses text is muted.

## B4: Sort icon in a sortable header shrinks when its label wraps

Manifestations:

- 3.2 (desktop, at 1442)
- 1.7 (desktop, at 1024)
- 3.9-tablet-table (tablet, at 768)

![](screenshots/page-2026-10-07T06-14-39-778Z.png)
![](screenshots/page-2026-10-07T06-10-57-278Z.png)

Expected: each sortable header keeps its full-size (size-4) sort icon at every width.

Actual: when "Last Name" wraps onto two lines, the inline-flex link squeezes the icon to a few pixels. Visible at 1442, 1024 and 768.

## Bug status

| Bug | Status |
|---|---|
| B1 | **FIXED** (commit: b472bc79) — Sortable table header labels use the primary link colour instead of muted |
| B2 | **FIXED** (commit: 9d69dc9c) — Educator navigation toggle shows a chevron instead of a menu icon |
| B3 | **FIXED** (commit: e7518eed) — Mobile learner row secondary line is not muted |
| B4 | **UNRESOLVED** — Sort icon in a sortable header shrinks when its label wraps (reason: fix budget exhausted this run) |

Each fix was re-checked in the browser after its commit: B1 on the learners table and the cohort Learners tab (labels now #5F6B7F, hover still primary, sorting works); B2 at 392 and 768 (hamburger `menu` icon, 44x48, opens the sheet); B3 at 392 (secondary-line last name muted and normal weight; desktop cells and card primary names unchanged). The B2 fixer's full suite had one Playwright failure, `test_modal_form_htmx` (submit buttons disabled while pending); it passes when run alone, so it is a load-related flake, not caused by the fix. The fixers' test runs logged the browser session out twice; the tester logged back in.

## General notes

- Theme: `FLS_THEME` on runserver only changes Django settings. The stylesheet is compiled by `npm run tailwind_build`, and the existing build was the default theme, so most look checks ran on the default build. The tester rebuilt with the default theme and then first_class, re-ran surfaces (8.9) and the design pass (8.10) on first_class, and left the first_class build in place. Test plan §0.5 should say to rebuild Tailwind with `FLS_THEME=first_class`.
- No dark mode exists in either theme, so 8.1 only confirms nothing breaks under a dark preference.
- The organisation switcher popover on desktop opens ~48px right of the trigger's left edge, overlapping the nav column (cosmetic, not on a checklist).
- Switching organisation from a list page keeps the current section (by design: the switcher's hx-get keeps the path). Test 1.5 expects the cohorts list only because it runs from a cohort page.
- After an in-place cohort rename the browser tab title keeps the old name until reload, and the URL becomes `/__tabs/details`.
- With JavaScript off, the sort form renders under the toolbar above the rows, not below the list as test 4.10 says. The plan notes this noscript block is unchanged on this branch.
- The learners table's first row (demodev@email.com, no first name) has no name link or quick-view button, so that learner cannot be opened from the list.
- The mobile sort sheet's options sit in a bordered fieldset box the design does not draw.
- QA Looks Cohort cannot be deleted (31 course progress records), so the ordinary delete confirmation was exercised on a cohort created during 7.5. Both cohorts the run created (QA Created Cohort, QA Mobile Enter Cohort) were deleted through the UI afterwards.
- The only console errors were expected 422 validation responses, plus one cross-origin resource blocked on a learner course page.

status: ok · reason: 4 bugs — 3 fixed, 1 unresolved; report rendered, screenshots verified
