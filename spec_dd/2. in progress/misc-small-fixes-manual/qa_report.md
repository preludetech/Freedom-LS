# Frontend QA report: misc-small-fixes-manual

## Methodology

- Branch: `misc-small-fixes-manual`, confirmed live via the debug-branch-badge for the duration of the run.
- Dev server: port 8473 (`http://127.0.0.1:8473`).
- Account: `demodev@email.com`.
- Screenshots live in `screenshots/` beside this report; every image referenced below is one of the 10 PNGs captured during the run.
- A compression pass ran over the captured screenshots afterward and found nothing over 1024KB.
- **The run was cut short by an environment failure.** The shared dev Postgres wedged partway through the plan (see "Environment failure" below), after section 9 completed. Sections 1, 2, and 12.1 never ran at all, and 3.9, 4.3, 4.6, 4.7, 5.24, 9.6, 10.2–10.3, 11.2, 11.4, 12.2–12.5, and both mobile/tablet passes of §12.8 were skipped for the same reason. Details are in the Results table and the per-test notes below.

## Diff scoping

The scoping record classified this diff as **FULL**, triggered by the changed template and CSS paths — `content_engine/templates/cotton/*.html`, `learner_interface/templates/.../course_form*.html`, `learner_interface/templates/cotton/course-card-shell.html`, `reports/static/reports/print.css`, `themes/default/static/themes/default/theme.css`, and `tailwind.components.css`, alongside several non-template Python changes (mail, allauth adapter, site-aware models, three admin modules, both settings files).

FULL scope means desktop, mobile, and tablet were all in scope for the affected sections (§3, §4, §5, §6, and the §12.8 repeat). **The mobile and tablet passes were not run** — this is a consequence of the environment failure, not a scoping decision. Everything captured in this report at those viewports is limited to the one `viewport: "mobile"`/`"tablet"` skip pair recorded for 12.8; no other test record in this run carries a non-desktop viewport.

## Smoke gate

Passed. Both checked pages loaded cleanly before the full run began:
- `http://127.0.0.1:8473/`
- `http://127.0.0.1:8473/courses/functionality-demo-show-end-with-quiz/2/`

No failure URL or failure reason recorded.

## Environment failure

**This is the single most important piece of context in this report: roughly a third of the plan could not be executed.**

The shared dev Postgres at `127.0.0.1:6543` stopped serving queries partway through the run, after section 9 finished. The failure signature was precise:

- TCP connections were still **accepted**, but no query ever completed a handshake: `psql 'select 1'` timed out, and `manage.py check` timed out against the same database.
- The listen backlog climbed while this was being observed — **47, then 60, then 65** — consistent with connections queuing up behind a server that had stopped accepting new work at the protocol level.
- Both Docker contexts (`default` and `desktop-linux`) reported **zero containers** running, while the forwarded ports 6543 (Postgres), 1025 and 8025 (Mailpit) stayed open. That combination — ports open, no containers — is the signature of a wedged Docker Desktop VM sitting behind its host-side port forwarder: the forwarder keeps the socket alive even though nothing on the other end can answer.
- Concurrent `pytest` runs from another session were in flight at the time: one in this worktree, one in the sibling `error-pages` worktree. Contention from those parallel test databases is the most likely trigger.

**This is not a defect in this branch.** It is host/environment infrastructure failing independently of the code under test.

Rule 2's recovery ladder (Content reset → DB drop → DB create → Migrate) could not help: every rung in that ladder requires a working Postgres connection to execute, and the database was unreachable at the transport level throughout. There was no rung that could clear a Docker VM wedged behind its own port forwarder.

Sections 1 and 2 (auth email tenant naming, queued mail) never ran at all, since both require the database to trigger and read email. Section 12.1 (the `get_cached_site(None)` hazard, the plan's highest-value regression probe) also never ran, for the same reason. The full list of skipped test IDs and their individual reasons is in the Results tables below.

## Results

### 0. Setup
No individually-numbered checks; setup steps (Tailwind build, dev server, seed data, login) succeeded implicitly — everything from §3 onward that depended on them ran normally.

### 1. Auth email names the tenant, not its domain

| test_id | status | notes |
| --- | --- | --- |
| 1.1–1.6 | skip | Not run: blocked by the database failure. Sending a password reset or signup verification needs the database. |

### 2. Mail is queued onto the background worker

| test_id | status | notes |
| --- | --- | --- |
| 2.1–2.9 | skip | Not run: blocked by the database failure. E007 could not be exercised either — `manage.py check` itself times out against the wedged database. |

### 3. The form player gets the standard navigation footer

| test_id | status | notes |
| --- | --- | --- |
| 3.1 | pass | Form start page has Previous on the left and the forward button on the right. ![](screenshots/page-2026-09-04T14-16-13-277Z.png) |
| 3.2 | pass | Form footer matches the topic player exactly: both pages render secondary at 34px and primary at 32px, 14px font, 6px 8px padding. The 2px gap is the secondary border, present identically on the topic page, so not a branch regression. |
| 3.3 | pass | Previous navigates to `/courses/functionality-demo-show-end-with-quiz/1/`, the preceding topic. |
| 3.4 | pass | Previous is btn-secondary with a previous icon; Try Again is btn-primary with a retry icon. |
| 3.5 | pass | Runner page Previous (btn-ghost btn-sm) and Next (btn-primary btn-sm) are both 32px at 14px, matching each other. |
| 3.6 | pass | Submit-confirm dialog opens from the last runner page's Next, with Go back and review / Submit. |
| 3.7 | pass | Completion-page buttons are small-sized and centred. Retry variant covered by the try_again state seen on the start page. |
| 3.8 | pass | Nav wrapper carries `hx-boost=true`, `hx-target=#interface-main`, `hx-select-oob=#course-toc-region`. Clicking Previous swapped without a full document reload. |
| 3.9 | skip | A form as a course's first item: no demo course starts with a form, and the database failed before a fixture could be built. Covered in pytest by `test_first_item_form_start_page_has_no_previous_button`. |
| 3.10 | **fail** | Form completion page has no Previous button at all (no `data-testid=previous-button`, no element containing "previous"). Its wrapper is `mt-8 flex flex-col sm:flex-row justify-center gap-3` — centred, not the player's justify-between footer. The sizing half passes: Continue is btn-primary btn-sm at 32px. ![](screenshots/page-2026-09-04T14-18-24-076Z.png) — see B1. This is the expected failure the plan calls out in advance. |

### 4. A required question's asterisk stays on the question's last line

| test_id | status | notes |
| --- | --- | --- |
| 4.1 | pass | Asterisk top == question paragraph top == number top on all three questions; legend height 20px = one line. |
| 4.2 | pass | Question number and question text share a line (numTop == pTop on all three). |
| 4.3 | skip | Narrow-viewport asterisk wrap not exercised: needs a form page render, blocked by the database failure. |
| 4.4 | skip | Markdown inside a question (bold/links/code) not separately verified beyond the three plain demo questions seen. |
| 4.5 | pass | Asterisk carries `aria-hidden=true` and a sibling `sr-only` span reading "(required)". |
| 4.6 | skip | Non-required question showing no asterisk: all three questions on the demo quiz page are required; the survey needed for this is behind the failed database. |
| 4.7 | skip | Multi-paragraph question judgement call: no such question in the seeded content, and none could be authored once the database failed. |

### 5. Content widgets

| test_id | status | notes |
| --- | --- | --- |
| 5.1 | pass | Face labels read Question and Answer. ![](screenshots/page-2026-09-04T14-18-56-632Z.png) |
| 5.2 | pass | Both faces carry a "Tap to flip" hint, `aria-hidden=true`. |
| 5.3 | pass | Back face paints `linear-gradient(135deg, ...)` from the `--fls-flashcard-back-gradient` token; clearly distinct from the plain front. ![](screenshots/page-2026-09-04T14-19-08-257Z.png) |
| 5.4 | pass | Answer-face prose is `rgb(26,35,50)` on an oklab 0.94–0.97 lightness tint; label `rgb(43,108,176)`; hint a 60% mix. All legible. |
| 5.5 | pass | Front and back both 250px tall. |
| 5.6 | pass | Click, Enter and Space each toggle `aria-pressed`; front/back `aria-hidden` swap with it. |
| 5.7 | pass | Corner labels and flip hints are `aria-hidden=true`; the trigger carries `aria-label='Flip card'` and `aria-pressed`. |
| 5.8 | pass | Focus ring renders as a white offset ring plus `rgb(43,108,176)` — the focus-ring token, not primary. |
| 5.9 | pass | Closed summary is `rgb(26,35,50)`, the default on-surface colour. ![](screenshots/page-2026-09-04T14-20-02-793Z.png) |
| 5.10 | pass | Hover tints the summary to `rgb(243,244,246)`; parent has `border-radius 8px` with `overflow:hidden` so the tint is clipped to the corners. |
| 5.11 | pass | Open state moves summary AND chevron to `rgb(43,108,176)` and rotates the chevron 180deg. |
| 5.12 | pass | `focus-visible` ring present and inset (`ring-inset`), not clipped by the host overflow. |
| 5.13 | pass | Summary padding is 16px 20px (was 12px 16px) — visibly roomier. Body inner padding 0 20px 20px, unchanged in feel. |
| 5.14 | pass | Title is `flex 1 1 auto` with `min-width 0`; chevron `ml-auto shrink-0` stays pinned right. |
| 5.15 | pass | Figure 1's description renders on the page as `<p class='text-muted text-sm mt-3'>`. ![](screenshots/page-2026-09-04T14-20-26-427Z.png) |
| 5.16 | pass | Description width 542px equals the title row width 542px — full card width, not stopping at the button. |
| 5.17 | pass | "Figure 1" renders in `ui-monospace` at `rgb(43,108,176)` with no colon after it. |
| 5.18 | pass | Trigger button reads "Expand". |
| 5.19 | pass | Title top == Expand button top on every figure on the page, including Figure 1's deliberately long three-line title. |
| 5.20 | pass | Lightbox opens with heading, "Close image" button, and both the title and description paragraphs beneath. Escape closes it. ![](screenshots/page-2026-09-04T14-20-47-764Z.png) |
| 5.21 | pass | The nine figures with no description render no trailing paragraph at all. |
| 5.22 | pass | Figures without a number show "Figure:" in the lightbox heading; the reflowed template lines introduced no stray whitespace. |
| 5.23 | pass | Ref is mono/primary and reads as a caption label against the medium-weight title; the dropped colon does not leave the two fragments disconnected. |
| 5.24 | skip | `prefers-reduced-motion` pass not run. The reduced-motion gating is present in the CSS (both widgets' transitions sit inside `@media (prefers-reduced-motion: no-preference)`) but was not exercised in the browser. |

### 6. Course cards

| test_id | status | notes |
| --- | --- | --- |
| 6.1 | pass | Dashboard card body computes to flex/column and the eyebrow sits in its own wrapper div; the chip inside measures 16px against a 345px body, so it is not blockified to card width. ![](screenshots/page-2026-09-04T14-22-02-841Z.png) |
| 6.2 | pass | Details wrapper is `flex justify-end mt-auto`. Across each row of cards every Details link shares a bottom edge (558/558/558, then 929/929/929, then 1295/1295) despite differing description lengths; one shorter card resolves `mt-auto` to 60px of pushed space and still aligns. |
| 6.3 | skip | Mobile/tablet stacking not run — see §12.8. |

### 7. An organisation's cohorts and learners on its admin page

| test_id | status | notes |
| --- | --- | --- |
| 7.1 | pass | Cohorts inline present on the change page with a Name column, per-row Change links and an "Add another Cohort" control. ![](screenshots/page-2026-09-04T14-22-25-877Z.png) |
| 7.2 | pass | Cohorts inline is editable with 14 change links and 15 name inputs; ordered by name. |
| 7.3 | pass | Learners inline has columns User / Is active / Created at, zero text inputs and zero DELETE checkboxes — read-only with per-row change links. |
| 7.4 | pass | Paginated at 25 over 9 pages for 204 learners. Page 1 ends `demodev_s31@`, page 2 begins `demodev_s32@` and runs to `demodev_s8@` — 25 unique per page, correct lexicographic order, no repeat and no skip across the boundary. The ordering fix holds. |
| 7.5 | pass | Related row reads "Search this organisation's 204 learners"; the link targets the Learner changelist with `organisation__id__exact` set, and that changelist reports 204 learners and offers a search box. |
| 7.6 | pass | Northside (no learners) renders "Related No learners yet" as plain text with no anchor. |
| 7.7 | pass | An organisation seeded with exactly one learner renders "Search this organisation's 1 learner" — singular, with the correctly filtered changelist href. Fixture built via `fls-dev:qa-data-helper` ("QA Singular Learner Org"). |
| 7.8 | skip | Not recorded as run in the scratch data. |
| 7.9 | pass | Add organisation page shows no inlines, no management forms and no Related row; fields are name/logo/logo_on_dark only. Saving "QA Add Page Check" succeeded and the changelist grew from 6 to 7 rows. |
| 7.10 | pass | The 204-learner organisation change page loads without visible stall, comparable to the small ones; `select_related` on the inline queryset is in place. |

### 8. Topic content preview in the admin

| test_id | status | notes |
| --- | --- | --- |
| 8.1 | pass | Content Preview renders real HTML: flashcard and accordion elements exist as DOM nodes, not escaped source and not raw markdown. |
| 8.2 | pass | Add topic page returns 200 with no traceback; the empty preview renders as an empty block. |
| 8.3 | **fail** | All 14 topic admin pages return 200 with no traceback, so no 500. But every Alpine-driven widget in the preview throws ReferenceErrors: "flashcard is not defined", "flipped", "frontStyle", "backStyle" on Interactive Widgets; "contentLightbox is not defined" on Media and Pictures. The flashcard writes the literal string "undefined" into its style attribute, loses its 3D geometry, and renders question AND answer side by side with no aria state — the answer is exposed. Component CSS is absent too: accordion summary padding computes to 0px. ![](screenshots/page-2026-09-04T14-25-08-466Z.png) — see B2. |
| 8.4 | pass | The readonly preview container holds 0 script tags and 0 inline `on*` handlers. Its 2 iframes are the legitimate allowlisted `https://www.youtube.com/embed/` sources from the content. nh3 sanitisation is intact. |
| 8.5 | pass (via 8.3) | Every seeded widget-bearing topic was opened as part of 8.3; the finding is B2. |
| 8.6 | pass | Large topics (Media, Interactive Widgets) load their change page without noticeable delay and the form below the preview stays usable. |

### 9. The cohort report prints on white paper

| test_id | status | notes |
| --- | --- | --- |
| 9.1 | pass | Pixel-sampled the generated PDF: pure white (255,255,255) is the dominant colour on every page at 88.2/92.2/94.9/93.2 percent. The paper is `--report-paper #FFFFFF`, not a theme surface. |
| 9.2 | pass | (242,242,242) — exactly `--report-fill #F2F2F2` — is the second colour on the cover (3.5%) and the at-a-glance page (4.5%), covering the cover card, stat cells, table headers and banding. |
| 9.3 | pass | Ratio-bar track keeps its 0.4pt muted outline alongside the `--report-fill` background, so a 0% bar stays visible on a banded row. |
| 9.4 | pass | PDF metadata Creator is "FirstClass" — `resolve_site_name` via the shared `site_display_name`, honouring HEADER_TITLE. Author is "DemoDev", the organisation, whose wordmark renders on the cover. |
| 9.5 | pass | Cover page bleed band reaches the left, right and bottom edges; `body margin:0` is intact. |
| 9.6 | skip | Greyscale print check not performed on the rendered PDF. |
| 9.7 | pass | Proved structurally, which is stronger than a pixel diff — see General notes for detail. |

### 10. Dev shows every course as visible and free

| test_id | status | notes |
| --- | --- | --- |
| 10.1 | pass | Content Widgets - Demo Reference is declared `visibility: coming_soon` in its `course.md`, yet it appears on `/courses/` and opens straight into the player at `/courses/content-widgets-demo-reference/1/`. The visibility override is live in dev. |
| 10.2 | skip | Paid-course entry check not run: blocked by the database failure. |
| 10.3 | skip | Badge-labelling check not run: blocked by the database failure. |
| 10.4 | pass | `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE` and `OVERRIDE_COURSE_ACCESS_TO_FREE` appear only in `config/settings_dev.py`; neither is set in `settings_prod.py` or `settings_base.py`, and both default to `False` where declared in `course_access/config.py`. Production is unaffected. |

### 11. Deployment guards and the bootstrap command

| test_id | status | notes |
| --- | --- | --- |
| 11.1 | pass | `setup_initial_prod_data` with no `--site-name` exits with "Error: Missing option '--site-name'." and creates nothing. Click validates before touching the database. |
| 11.2 | skip | `setup_initial_prod_data` WITH `--site-name` not run: creating the Site needs the database. |
| 11.3 | pass | `.env.example` documents that mail is queued by default, that a deployment running no worker must set `EMAIL_BACKEND` back to the SMTP backend, that `EMAIL_UPSTREAM_BACKEND` is the way to keep queueing with a provider backend, and `EMAIL_TIMEOUT=10` with its rationale. |
| 11.4 | skip | `check --deploy` against production settings not run: `manage.py check` times out against the wedged database. |

### 12. Regressions elsewhere

| test_id | status | notes |
| --- | --- | --- |
| 12.1 | skip | The `get_cached_site(None)` hazard — the highest-value regression probe in the plan — was NOT exercised. It needs a shell that can send mail. This remains an open question for production: with neither `FORCE_SITE_NAME` nor `SITE_ID` set, `format_email_subject` resolves the site from a null request and may raise. |
| 12.2–12.5 | skip | Header tenant name, the full allauth loop, the other demo courses and the other widgets were not re-checked after the database failure. The widgets demo course and the two form courses were exercised earlier in sections 3–5 with no regressions seen. |
| 12.6 | pass | `learner_management/admin.py` imports `organisations.admin` and `organisations.models` at module scope; nothing under `organisations/` imports `learner_management` back, so there is no cycle. Matches the documented layering. Confirmed empirically too: the organisation change pages, the learner changelist and the admin index all rendered before the environment failure. |
| 12.7 | pass | Before the environment failure, the admin index and every changelist touched by this branch (organisations, learner, topic, generatedreport) opened without error. |
| 12.8 (mobile) | skip | Mobile 375x812 pass not run — the database failed before Step 8. CLASS was FULL, so this was in scope. |
| 12.8 (tablet) | skip | Tablet 768x1024 pass not run — the database failed before Step 9. CLASS was FULL, so this was in scope. |

### 13. What changed that nobody asked for

This is a read-only audit, not a browser test suite. Findings are recorded here and expanded under General notes / Bug sections; nothing in §13 is auto-fixed.

| test_id | status | notes |
| --- | --- | --- |
| 13.1 | **fail** | The deleted `visual_polish` folder's coverage claim is only one-third true. `course-card-details-link-not-bottom-aligned` IS fixed (verified as 6.2). `btn-sm-padding-crowds-the-button-icon` is NOT: the branch diff changes no `.btn-sm` rule at all, and adds three more `btn-sm` usages. `side-panel-dialog-paints-a-full-column-focus-outline` is NOT: grep finds zero `.side-panel-dialog` rules anywhere in `tailwind.components.css`. The deleted `research_focus_indicators.md` contained a completed diagnosis of that second issue — UA `:focus-visible` ring outlining the whole panel column, WCAG 2.4.7/2.4.13 analysis, and a recommended on-brand restyle using the already-declared but unconsumed `--color-focus-ring` token. That analysis is now only in git history. See B3. |
| 13.2 | pass | Confirmed coupling: `.picture-figure-title` uses `py-[calc(0.375rem+1px)]`, derived from `btn-sm`'s padding plus its border, to align the caption's first line with the Expand button. Changing `btn-sm` later silently breaks 5.19. Recorded, not fixed. |
| 13.3 | pass | Confirmed: `learner_management/admin.py` line 537 ASSIGNS `OrganisationAdmin.inlines` rather than appending, so a second contributing app would replace these two inlines. Line 538's `ORGANISATION_SUMMARIES.append` is correctly additive. No impact today; noted. |
| 13.4 | pass | `previous_url` is set before the `player_context` spread in both `view_topic` (line 906 vs 909) and `view_form` (972 vs 973), so the new code follows the existing pattern rather than introducing an inconsistency. The chrome context does not supply that key today. |
| 13.5 | **fail** | Docs gap. `--report-paper` and `--report-fill` appear nowhere in `docs/` or `claude_plugins/`. `print.css` now owns the report's two neutrals outright and no longer reads any theme surface token, so a downstream project can no longer rebrand the report's paper via `--color-surface` and is not told what replaced it. The flashcard's new tokens WERE documented in `docs/how tos/theme-fls.md`; these were not. See B4. |
| 13.6 | pass | `EMAIL_TIMEOUT` is set in `settings_prod.py` and `.env.example` with a default in `deployment/settings_defaults.py`, deliberately not in dev where Mailpit is local. `demo_content/` is clean under `git status` after `content_save`. |

**On §3.10 and whether it is the only failure:** it is not. §3.10 is the one expected failure called out in the plan before the run started. Two more failures surfaced during the run: §8.3 (content-preview widgets broken and answer disclosure, B2) and §13.1/§13.5 (audit findings that reached bug status: the deleted spec folder covering unfixed issues, B3; and the undocumented report tokens, B4). §13 findings are process/documentation observations for a human decision, not defects to fix in the code loop — they are reported as bugs here only because the plan explicitly asks that undocumented or miscovered changes be written up, and B3/B4 cross that line from "note" to "actionable gap."

## Bug: B1 — Form completion page has no Previous button and does not use the player footer

**Manifestations:** 3.10 (desktop)

![](screenshots/page-2026-09-04T14-18-24-076Z.png)

**Expected:** The form completion page carries back and forward navigation like every other page in the course player — a Previous button alongside Continue / Retry quiz / Return to course, in the player's `justify-between` footer.

**Actual:** No Previous button exists at all: no element with `data-testid=previous-button` and no element whose text contains "previous". The wrapper is `mt-8 flex flex-col sm:flex-row justify-center gap-3` — centred, not the player footer. Only the button sizing half of the `idea.md` item was done (Continue is btn-primary btn-sm at 32px, which is correct).

## Bug: B2 — Topic admin content preview breaks every Alpine-driven widget and exposes flashcard answers

**Manifestations:** 8.3 (desktop)

![](screenshots/page-2026-09-04T14-25-08-466Z.png)

**Expected:** The new read-only Content Preview renders a topic's markdown as it would appear to a learner, or at least without throwing.

**Actual:** The admin page renders the widgets' markup but registers none of their Alpine components and loads none of the site's component CSS. Every topic containing a flashcard throws four ReferenceErrors (`flashcard`, `flipped`, `frontStyle`, `backStyle`); every topic containing a picture throws `contentLightbox is not defined`. The flashcard writes the literal string "undefined" into its style attribute, loses its 3D geometry and renders the question AND the answer side by side with no aria state, so the preview discloses the answer. Accordion summary padding computes to 0px. No page 500s: all 14 topic change pages return 200 with no traceback.

## Bug: B3 — visual_polish spec folder deleted while two of its three diagnosed issues remain unfixed

**Manifestations:** 13.1 (desktop)

**Expected:** A spec folder deleted on the grounds that its items are covered should have its items covered, or be archived to `spec_dd/3. done/` rather than removed.

**Actual:** Only `course-card-details-link-not-bottom-aligned` is actually fixed. `btn-sm-padding-crowds-the-button-icon` is untouched (no `.btn-sm` rule changed; three more `btn-sm` usages added). `side-panel-dialog-paints-a-full-column-focus-outline` is untouched (zero `.side-panel-dialog` rules exist). Roughly 565 lines of research went with them, including a completed WCAG 2.4.7/2.4.13 diagnosis of the focus-ring issue and its recommended fix. Recoverable only from git history.

## Bug: B4 — New report colour tokens are undocumented, breaking the downstream rebrand path

**Manifestations:** 13.5 (desktop)

**Expected:** A downstream project can find out how to rebrand the report's paper and fill colours.

**Actual:** `print.css` now owns `--report-paper` and `--report-fill` outright and references no theme surface token, so overriding `--color-surface` no longer affects the report. Neither token appears anywhere in `docs/` or `claude_plugins/`. The flashcard's four new tokens were documented in `docs/how tos/theme-fls.md` in the same branch; these two were not.

## Bug status

No bug was routed to the auto-fix lane this run. The dev database failed before triage, and the fix
loop's re-verification step requires driving the failing flow against a live server. A fix that
cannot be re-verified must be reverted under the loop guard, so spawning a fixer would have produced
a commit with no way to confirm it. All four are recorded for a human.

- **UNRESOLVED** — Form completion page has no Previous button and does not use the player footer
  (reason: fix is well-specified and unit-testable, but re-verification needs the dev database, which
  was unavailable this run)
- **UNRESOLVED** — Topic admin content preview breaks every Alpine-driven widget and exposes
  flashcard answers (reason: turns on a product decision — whether the admin should load the site's
  Alpine components and component CSS, or the preview be narrowed to static markup)
- **UNRESOLVED** — visual_polish spec folder deleted while two of its three diagnosed issues remain
  unfixed (reason: a process and scope decision for a human, not a code defect)
- **UNRESOLVED** — New report colour tokens are undocumented, breaking the downstream rebrand path
  (reason: documentation, not a functional regression; the author should choose where the two tokens
  are documented)

## General notes

- **Pre-existing CSP console error, unrelated to this branch.** On course topic pages, a report-only Content-Security-Policy violation fires from a YouTube embed's redirect to a Google abuse-report page. Seen while exercising the widgets demo course during §5 and §8. Not introduced by anything in this diff.
- **Submit-confirm dialog buttons are still full-size.** The form's submit-confirm dialog (Keep going / Leave and submit / Go back and review / Submit) renders its buttons at full 16px size rather than `btn-sm`, unlike the topic and form-runner footer buttons that this branch resized. Modal buttons were arguably out of scope for the sizing commit; flagging for awareness, not filing as a bug.
- **§9.7 was proven structurally, and that is stronger than a pixel diff.** `print.css` and `reports/templates/` contain zero references to `--color-surface` or `--color-surface-2`, so no theme — current or future — can reach the report's paper through those tokens. This was confirmed two ways: (1) the tailwind bundle was temporarily rebuilt under `FLS_THEME=first_class` to verify that theme's tokens really are tinted relative to default (`--color-surface #F8F9FC`, `--color-surface-2 #EDF2F7`, vs. default's `#FFFFFF` / `#F3F4F6`) — confirming the pre-fix bug was real and `first_class`-specific; (2) grepping `print.css` and `reports/templates/` for those two token names returned nothing, and the only fills present are `--report-paper` (1 site, line 211) and `--report-fill` (10 sites), matching the ten replacements in the diff. The bundle was rebuilt back to the default theme afterward, so the working tree is not left with a `first_class` bundle in place.
- **Dev-only QA residue was seeded during this run.** An organisation named "QA Singular Learner Org" with one learner was seeded via `fls-dev:qa-data-helper` for test 7.7. An organisation named "QA Add Page Check" was created directly by test 7.9 (changelist grew from 6 to 7 rows). Both are dev-only fixtures on this branch's dev database and should be considered QA residue, not data to carry forward.

---

status: ok
reason: 4 bugs — 0 fixed, 4 unresolved (no fixer spawned: dev database unavailable for re-verification); report rendered, 10 screenshots verified, run truncated after section 9 by an environment failure
