# Repo surface research — input for `/system_qa` command design

This document maps the FLS surface area, recent spec patterns, existing QA tooling, and likely regression hot-spots so the `/system_qa` command author can scope and structure the new flow correctly. All paths are absolute.

---

## 1. Surface-area inventory

### 1.1 Top-level URLconf — entry points

`/home/sheena/workspace/lms/freedom-ls-worktrees/main/config/urls.py`

```
path("health/", health_check)                     # ops only — skip in QA
path(ADMIN_URL, admin.site.urls)                   # Django admin (Unfold)
path("educator/", include("educator_interface.urls"))
path("accounts/", include("allauth.urls"))         # signup, login, password reset, email confirm
path("accounts/", include("accounts.urls"))        # profile, legal docs, complete-registration
path("", include("student_interface.urls"))        # student-facing root
# DEBUG-only:
path("__reload__/", include("django_browser_reload.urls"))
path("qa/", include("qa_helpers.urls"))            # toast playground (QA-TEMP)
+ debug_toolbar_urls()
```

Two large prefixes that matter for QA: `accounts/*` (auth + onboarding) and `educator/*` (educator panel framework). The student site lives at root.

### 1.2 Student interface (`freedom_ls/student_interface/`)

URLconf: `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/student_interface/urls.py`

| URL | View | Page identity |
|---|---|---|
| `/` | `home` | Dashboard / landing — `home.html`, partials drive Your Courses / Recommended / Learning History |
| `/courses/` | `all_courses` | Course catalogue — `all_courses.html` |
| `/courses/<slug>/` | `course_home` | Course landing with TOC + register button |
| `/courses/<slug>/register/` | `register_for_course` | POST — creates `UserCourseRegistration`, deletes any matching `RecommendedCourse`, redirects |
| `/courses/<slug>/<index>/` | `view_course_item` | Topic OR Form viewer; enforces hard-deadline lockout |
| `/courses/<slug>/<index>/start_form` | `form_start` | Creates `FormProgress`, redirects to first page |
| `/courses/<slug>/<index>/fill_form/<page>` | `form_fill_page` | Multi-page form filling |
| `/courses/<slug>/<index>/complete` | `course_form_complete` | Form result page — quiz scores, retry / continue |
| `/courses/<slug>/finish/` | `course_finish` | End-of-course celebration; fires `course.completed` webhook |
| `/partials/courses/` | `partial_list_courses` | HTMX dashboard partial |
| `/partials/courses/<slug>/toc` | `partial_course_toc` | TOC partial (the one bug-fixed by `bugfix-cant-expand-toc-on-course-page`) |

Templates: `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/student_interface/templates/student_interface/` — `home.html`, `all_courses.html`, `_course_base.html` (shared shell), `course_home.html`, `course_topic.html`, `course_form.html`, `course_form_page.html`, `course_form_complete.html`, `course_finish.html`, `partials/{course_list,course_minimal_toc,form_progress_scores}.html`.

### 1.3 Educator interface (`freedom_ls/educator_interface/`)

URLconf: catch-all `re_path(r"^(?P<path_string>.*)$", views.interface)` — entire UI dispatched through `panel_framework_view` in `freedom_ls/panel_framework/views.py`. The `interface_config` dict in `educator_interface/views.py` registers three top-level list views via `ListViewConfig`:

- `cohorts/` → `CohortConfig` → `CohortDataTable`, `CohortInstanceView` with tabs `course_progress` and `details`.
  - `details` panels: `CohortDetailsPanel` (editable), `CourseRegistrationsPanel`, `CohortStudentsPanel`.
  - `course_progress`: `CohortCourseProgressPanel` (independent column + student paginators, deadlines, overrides).
- `users/` → `UserConfig` → `UserDataTable` (search by first/last/email — only panel with `search_fields`), `UserInstanceView` panels `details`, `cohorts`.
- `courses/` → `CourseConfig` → `CourseDataTable`, `CourseInstanceView` panels `details`, `cohorts`, `students`.

Templates under `freedom_ls/educator_interface/templates/educator_interface/`: `interface.html`, `partials/{panel_container,list_view,instance_details_panel,course_progress_panel}.html`.

QA implication: only `UserDataTable` declares `search_fields`. The `educator-experience-bug-fix` qa_report explicitly notes Cohort/Course list/registration panels have **no** sort headers or search box (intentional). A QA explorer must know this — don't keep flagging "missing controls".

### 1.4 Auth / accounts (`freedom_ls/accounts/`)

URLconf: `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/accounts/urls.py` plus bundled allauth.

| URL | Surface |
|---|---|
| `/accounts/signup/` | allauth signup, customised by `SiteAwareSignupForm` (first/last name, T&C/Privacy clickwrap) |
| `/accounts/login/`, `/logout/`, `/password/reset/...`, `/confirm-email/` | Standard allauth flows |
| `/accounts/profile/` | `edit_profile` |
| `/accounts/legal/<doc_type>/` | Loads markdown from git via `legal_docs.py` (path-traversal hardened) |
| `/accounts/complete-registration/` | `complete_registration_view` — runs after email verify if `additional_registration_forms` configured |

`accounts/middleware.py` redirects users with incomplete registration to `complete-registration/` with explicit exemptions for legal docs and logout. Site-awareness via `accounts.allauth_account_adapter`.

### 1.5 Student management & progress

`freedom_ls/student_management/` — models: `Cohort`, `CohortMembership`, `CohortCourseRegistration`, `CohortDeadline`, `UserCohortDeadlineOverride`, `UserCourseRegistration`, `RecommendedCourse`. No views — surfaced through educator panels and student dashboard partials.

`freedom_ls/student_progress/` — models: `CourseProgress`, `TopicProgress`, `FormProgress`. Drives quiz scoring (`FormStrategy.QUIZ`, `quiz_pass_percentage`), course completion timing, last-accessed timestamps. No URLs.

### 1.6 Content engine (`freedom_ls/content_engine/`)

`Course`, `CoursePart`, `Topic`, `Form`, `FormPage`, `FormQuestion`, etc. Markdown rendering via `freedom_ls/markdown_rendering/`, cotton components in `content_engine/templates/cotton/`. Direct content-preview URLs are commented out in `config/urls.py`, so QA won't hit them.

### 1.7 Cross-cutting / shared chrome

Base templates at `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/base/templates/`:
- `_base.html` — root layout (htmx, alpine, tailwind, csrf headers, posthog, debug-branch-badge)
- `_base_interface.html` — sidebar shell used by both student course pages and the educator interface (`x-data="sidebarComponent"`, mobile drawer, backdrop, content grid)
- `partials/`: `header_bar.html`, `header_bar_user_menu.html`, `messages.html`, `_toast.html`, `login_prompt.html`, `logout_button.html`
- `cotton/`: `button.html`, `dropdown-menu.html`, `modal.html`, `picture.html` (referenced — actually in content_engine), `pagination.html`, `data-table.html`, `loading-indicator.html`, `markdown-container.html`, `chip.html`, `page.html`, `scroll-table-labels.html`, `data-table-cells/*`
- `account/signup.html` (allauth template override), `allauth/layouts/base.html`

### 1.8 Admin

Django admin at `${DJANGO_ADMIN_URL}` (default `admin/`), themed with Unfold + `SiteAwareModelAdmin`. The existing `do_qa.md` **explicitly skips mobile/tablet QA for admin**; the new command should do the same.

### 1.9 Major user flows a human QA would walk

1. Sign up (allauth + name capture + T&C) → email verify → optional `complete-registration` → land on dashboard.
2. Login / logout for an existing student.
3. Browse catalogue → register for a course → land on course home.
4. Take a topic: navigate index, mark complete, advance.
5. Take a form / quiz: multi-page form, submit, scores, retry-or-continue, deadline lockout for hard deadlines.
6. Finish a course: trigger completion → confirm `course.completed` webhook artifact.
7. Dashboard rendering states: empty / current-only / history-only / recs-only / mixed.
8. Sidebar / TOC: expand-collapse persistence across navigation, mobile drawer, tablet overlap.
9. Educator: cohort list → cohort details (Details + Course Progress tabs) → student detail → user detail.
10. Educator: course list → course details (cohort + direct registrations).
11. Educator: data-table sort, search (Users only), HTMX pagination preserving query params, big-cohort course-progress grid pagination.
12. Educator: deadlines + overrides on course-progress grid.
13. Toasts / messages: Django message → bottom-right; HTMX 200 + 422 OOB delivery; auto-dismiss vs persistent error; stacking + cap of 5.
14. Legal docs: `/accounts/legal/terms/`, `/accounts/legal/privacy/`.
15. Profile edit.
16. Password reset end-to-end including incomplete-registration users.

---

## 2. Recent spec patterns

Listing of `/home/sheena/workspace/lms/freedom-ls-worktrees/main/spec_dd/3. done/` sorted newest first (top 16):

| # | Directory | Area | qa_report? | One-line |
|---|---|---|---|---|
| 1 | `2026-05-06_07:52_toasts-bottom-viewport` | shared chrome / messages / HTMX | YES | Toasts moved to bottom-right; OOB delivery, auto-dismiss, stacking cap, accessibility live regions |
| 2 | `2026-05-05_21:18_fix-fouc-and-empty-sections` | shared chrome / dashboard | YES | Global `[x-cloak]` rule + hide empty Recommended/History sections |
| 3 | `2026-05-05_17:24_layout-spacing-cleanup` | shared chrome / `_base.html`, page wrapper | YES | Top-down spacing fixes; touches base layout + course content shell |
| 4 | `2026-05-05_13:11_course-page-small-fixes` | student/course UI | YES | Next/Prev arrows, finish-page button removal |
| 5 | `2026-05-05_10:10_educator-experience-bug-fix` | educator/panel framework | YES | Recursive-table bug + numbered pagination + course-progress dual paginator |
| 6 | `2026-05-05_08:18_better-registration` | accounts / signup / legal | YES | First/last name fields, clickwrap T&C, LegalConsent capture, complete-registration middleware |
| 7 | `2026-05-03_09:07_testing-best-practice-phase-4-e2e-hardening` | tests only | YES | Playwright E2E hardening |
| 8 | `2026-05-02_20:59_testing-best-practice-phase-3-strengthen-view-assertions` | tests only | NO | Pure test-suite refactor |
| 9 | `2026-05-02_20:11_testing-best-practice-phase-3-factories-sweep` | tests only | NO | factory_boy sweep |
| 10 | `2026-05-02_19:32_testing-best-practice-phase-3-parametrize-and-remove-tautologies` | tests only | NO | Parametrize tests |
| 11 | `2026-05-02_18:13_testing-best-practice-phase-3-cleanup-flaky-and-redundant-tests` | tests only | NO | Cleanup |
| 12 | `2026-04-29_09:05_testing-best-practice-phase-2-tooling-quick-wins` | tooling | NO | Tooling-only |
| 13 | `2026-04-28_07:25_testing-best-practice` | tests planning | NO | Parent test-quality spec |
| 14 | `2026-04-24_12:38_bugfix-cant-expand-toc-on-course-page` | student/course UI / Alpine | YES | TOC `toggleExpanded` Alpine init bug + persistence across nav |
| 15 | `2026-04-24_09:16_educator-interface-better-nav` | educator / breadcrumbs / sidebar | YES | Breadcrumbs + sidebar nav redesign |
| 16 | `2026-04-06 20:18 premailer-fix` | backend / email | NO (backend only) | premailer SyntaxWarning fix |

Stats over those 16:
- **9 / 16 have `qa_report.md`** — every UI-touching spec has one; 7 backend/test-only specs do not.
- **UI vs backend split**: ~9 UI/UX specs, 6 test/tooling, 1 backend.
- **Hottest areas in last ~2 weeks**: shared chrome / `_base.html` / sidebar / messages / dashboard partials (specs 1, 2, 3) and the educator panel framework + data-table (5, 15). Anything missed there compounds.
- **Each per-spec QA** runs strictly against `3. frontend_qa.md` for that branch, scoped to its own deltas. None retest unrelated surfaces — exactly the gap `/system_qa` plugs.

Filename conventions for the scanner:
- Sort by directory name — `YYYY-MM-DD_HH:MM_*` is reliable. One legacy dir uses spaces (`2026-04-06 20:18 premailer-fix`); be tolerant.
- A dir is "UI-touching" if it contains `3. frontend_qa.md` or any `screenshots/` content.
- A spec was "already QAed for its own delta" if `qa_report.md` exists alongside.

---

## 3. Existing QA reports — patterns

Read in full: `2026-05-06_07:52_toasts-bottom-viewport/qa_report.md`, `2026-05-05_21:18_fix-fouc-and-empty-sections/qa_report.md`, `2026-05-05_10:10_educator-experience-bug-fix/qa_report.md`, `2026-05-05_08:18_better-registration/qa_report.md`, `2026-04-24_12:38_bugfix-cant-expand-toc-on-course-page/qa_report.md`.

### 3.1 Standard structure

Every report opens with:
```
**Branch:** <branch>
**Date:** <ISO>
**Site:** DemoDev
**Tooling:** Playwright MCP, dev server on port <PORT>
```
Then a markdown results table listing each test ID with PASS / FAIL / PARTIAL / N/A. Then "Detailed observations" / per-test sections. Then "Tangential observations". Then "Setup / Coverage notes". `/system_qa` should keep this skeleton.

### 3.2 Verdict vocabulary in use

`PASS`, `FAIL`, `PARTIAL`, `N/A`, `NOT EXECUTED`. No numeric severity; bugs described inline by behavioural impact. The toast report demoted a FAIL to PASS after re-verification with curl — re-verification before locking in a FAIL is an implicit norm.

### 3.3 Screenshots

Pattern `screenshots/<viewport>_<test-id>_<short-desc>.png` (viewport ∈ `desktop|mobile|tablet`). Inline `![alt](screenshots/<file>)` so they render. The toast report keeps a separate `qa-artifacts/` for raw measurement images.

`fls-claude-plugin/scripts/compress_screenshots.py` runs after capture to keep PNGs under the 1024 KB pre-commit cap, falling back to JPEG (q=85→70→50), then scaling (0.75→0.5→0.35). Run from the spec directory before generating the report — links assume images already fit.

### 3.4 What a "good" finding looks like

From `educator-experience-bug-fix` Test 1:
> Sorted the Students panel column three times in a row (asc → desc → asc). After every click, the page contained exactly one `<h2>Students</h2>`, one search input, and the same student-table-shaped DOM. No nested panel chrome, no duplicate search box, no nested table.

From `toasts-bottom-viewport` Test 17: includes a 5-row `top/bottom/h/gap` table for the stacked toasts.

Hallmarks: explicit DOM IDs/classes; numeric measurements where layout matters; user-visible verdict spelled out; one screenshot per discrete state.

A non-finding (PARTIAL/N/A) is justified by why it couldn't be exercised — e.g. "Playwright MCP does not expose the DevTools `Emulate CSS media feature` toggle", "Requires real notched iOS device", "panel does not expose sortable columns or a search box".

### 3.5 Bug pattern in those 5 reports

- `toasts`: 1 PARTIAL (mid-stack dismiss animation siblings snap rather than animate). 2 cosmetic tangentials.
- `fouc-and-empty-sections`: 0 bugs. Tangentials: DJDT overlay, runserver background lifecycle.
- `educator-experience-bug-fix`: 0 bugs (3 caveats where panels lack the controls the plan named). Tangentials: DJDT overlap on mobile.
- `better-registration`: 0 bugs. Tangentials include **a real cross-spec issue** ("Mobile completion view: success toast overlaps the page heading") — exactly the kind of cross-cutting wobble `/system_qa` should re-flag — plus `mypy pre-commit hook crashes`.
- `bugfix-cant-expand-toc-on-course-page`: 0 bugs after re-run; `localStorage` key behaviour with concrete values.

Severity skews PASS — per-spec QA runs against a branch implemented to a plan; most issues are caught in code review. **The interesting findings tend to live in Tangential observations** — exactly what `/system_qa` should chase.

### 3.6 What the per-spec QA does NOT cover (the gap)

- Anything outside the spec's own `3. frontend_qa.md`.
- Surfaces touched by *other* recent specs.
- Multi-spec interaction: spec A touching `_base.html` + spec B touching `partials/messages.html` may not collide individually but together can break.
- States needing data the per-spec plan didn't ask for.

---

## 4. Existing helpers / scripts / agents

### 4.1 `fls-claude-plugin/commands/sdd/do_qa.md`

Read in full at `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/commands/sdd/do_qa.md`. Reusable mechanics:

- **Step 1**: clean prior `qa_report.md` and `screenshots/` from current dir.
- **Steps 2–3**: kill stale runserver via `kill_runserver.sh $PORT`; find port via `find_available_port.sh`; `uv run python manage.py runserver $PORT`.
- **Step 4**: navigate to `/`, verify `#debug-branch-badge` matches the current branch — guards against PORT collisions where another worktree's server bound first. Critical in multi-worktree environments.
- **Step 5**: optional login using credentials from `.claude/fls/config.md`.
- **Steps 6–8**: walk plan at desktop (1920×1080), mobile (375×812), tablet (768×1024). Naming `<viewport>_<test-id>_<desc>.png`. Skip mobile/tablet for django admin.
- **Step 9**: `uv run --with pillow python ${CLAUDE_PLUGIN_ROOT}/scripts/compress_screenshots.py`.
- **Step 10**: write `qa_report.md` next to the test plan; per error: title, screenshots, expected vs actual.
- **Step 11**: kill the runserver.
- **Step 12**: invoke `update_todo` helper at `fls-claude-plugin/commands/sdd/protected/update_todo.md`.

The "never create test data yourself / always delegate to qa-data-helper" rule is firm — replicate it.

The Playwright MCP requirement is firm — abort with diagnostic if MCP unavailable. Replicate.

### 4.2 `fls-claude-plugin/agents/qa-data-helper.md`

Tools: `Glob, Grep, Read, WebFetch, WebSearch, Bash`. Model: opus. Persistent memory at `.claude/agent-memory/qa-data-factory/`.

Contract:
- Always factory_boy, never raw `Model.create(...)`.
- Discovers existing factories first (`tests/`, `factories.py`, `conftest.py`, `qa_helpers/`).
- Prefers a Django **management command** under `qa_helpers/management/commands/` for reusable scenarios.
- Reports back: emails, passwords (`testpass123` convention), entity names, counts, URLs.
- Respects multi-tenant — every created object on the right `Site`.

Call this agent the same way `do_qa.md` does — with an explicit data-shape brief.

### 4.3 Plugin scripts (`fls-claude-plugin/scripts/`)

- `find_available_port.sh` — picks a port in 8000–8999 not currently bound.
- `kill_runserver.sh` — kills the PID listening on a given port.
- `compress_screenshots.py` — PNG → optimised PNG → JPEG cascade; ceiling 3000 px dimension.
- `db_clear.sh`, `db_recreate.sh`, `dev_db_init.sh`, `dev_db_delete.sh` — destructive; **DO NOT** use during QA.
- `fetch_pr_comments.sh`, `generate_app_map.py`, `install_dev.sh` — unrelated.
- `hooks/` — `post-edit-bandit.sh`, `ruff_fix.sh`, `security-guard.sh` (lint hooks; irrelevant at runtime).

### 4.4 `freedom_ls/qa_helpers/` Django app

Path: `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/qa_helpers/`. Already wired in via `config/urls.py` (DEBUG-only).

Contents:
- `urls.py` — DEBUG-only `/qa/` routes. Currently a toast playground (`toasts/full/`, `toasts/htmx-success/`, `toasts/htmx-error/`, `toasts/playground/`). Marked QA-TEMP.
- `toast_views.py` — emits `messages.success/error` and renders `partials/messages.html` in OOB mode, deliberately reproducing the original double-OOB regression so middleware stays honest.
- `templates/qa_helpers/toast_playground.html`.
- `delete_gitignore_emails.sh` — clears the file-backed email backend at `gitignore/emails/`.
- `management/commands/`:
  - `qa_add_course_items_for_pagination.py` — idempotent, DemoDev-scoped; stuffs a course so the column paginator on the course-progress grid has >1 page.
  - `qa_complete_form.py`
  - `qa_create_cohort_progress.py`
  - `qa_create_deadline_overrides.py`
  - `qa_create_empty_student_cohort.py`
  - `qa_create_large_cohort.py`
  - `qa_create_soft_deadline.py`

These are the canonical staging points for QA scenarios. Expect qa-data-helper to extend this app.

### 4.5 Demo data baseline

`freedom_ls/student_management/management/commands/create_demo_data.py` seeds the dev DB. The DemoDev site has `demodev_s1@email.com` … `demodev_s10@email.com`, the `demodev@email.com` educator, and four demo courses (e.g. `functionality-demo-course-parts`, `functionality-demo-show-end-with-quiz`, `standard-markdown-demo-finance`). Existing reports refer to these by name. Don't assume specific users have specific progress states without invoking qa-data-helper.

### 4.6 Memory rules to honour

- DemoDev is the canonical QA target (`feedback_use_demodev_site.md`).
- Don't assert on CSS classes — keep findings behavioural ("the heading is obscured", not "tailwind class missing").
- Focus only on the current worktree (`feedback_focus_on_current_worktree.md`).

---

## 5. Test infrastructure

### 5.1 Playwright E2E (pytest-playwright)

Marker: `@pytest.mark.playwright`. Shared fixtures: `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/tests/playwright_fixtures.py`. Conftest: `/home/sheena/workspace/lms/freedom-ls-worktrees/main/conftest.py` re-exports `freedom_ls/conftest.py`.

Existing E2E tests are sparse on purpose (Phase 4 chose "high-value only"):
- `freedom_ls/student_interface/tests/e2e/test_course_toc.py` — TOC course-part expand/collapse on detail pages, `transaction=True`, `reset_local_storage` autouse.

This is **not** a comprehensive smoke suite. The list of E2E tests does NOT define the critical-surface inventory — the spec backlog and qa_reports do. The new command should not lean on these.

### 5.2 Per-app pytest tests

Substantial unit/integration coverage across `accounts/tests/`, `student_interface/tests/`, `educator_interface/tests/`, etc. — strengthened by the Phase-3 testing-best-practice specs. Backend confidence; will not catch HTMX OOB or layout regressions. Treat absence of an E2E for a flow as evidence that flow needs hands-on browser exploration.

### 5.3 Skills the new command should pull from

- `fls:use-playwright` — interactive browsing rules.
- `fls:multi-tenant` — must respect Site context.
- `fls:registration` — knows the signup / consent / complete-registration shape.
- `fls:icon-usage`, `fls:frontend-styling`, `fls:template`, `fls:alpine-js`, `fls:htmx` — for assessing the *quality* of an observed UI rather than re-implementing it.
- `fls:playwright-tests` — only if the command starts emitting durable test code (probably out of scope; system QA is exploratory).

---

## 6. Cross-spec interaction risk — likely regression hot-spots

Cross-referencing the last 16 done specs against shared chrome / template inventory:

### 6.1 `freedom_ls/base/templates/_base.html` and `_base_interface.html`

Touched by: `layout-spacing-cleanup` (#3), `fix-fouc-and-empty-sections` (#2, added global `[x-cloak]`), `toasts-bottom-viewport` (#1, message rendering inside `<body>`), `educator-interface-better-nav` (sidebar). All push CSS / DOM order / Alpine init into a single template.

Specific risks:
- Global `[x-cloak] { display: none !important; }` regressing — any element forgetting `x-cloak` flashes; any `x-cloak`-bearing element that never has the attribute removed stays invisible.
- Sidebar mobile drawer (`x-data="sidebarComponent"` in `_base_interface.html`) interacts with new spacing rules; any wrapper-padding change can re-introduce the "tablet sidebar overlaps content" tangential.
- Toast `#toast-container` sits inside `<body>` rendered before `<main>`; positioning depends on viewport units + safe-area envs that are easy to miscalibrate alongside spacing changes.

Hooks: compare `partials/header_bar.html` height + first heading position on each major page; force a toast on each layout flavour; resize through three viewports.

### 6.2 `freedom_ls/base/templates/partials/messages.html` + `_toast.html`

Touched by toasts spec; consumed by every full-page render (because `_base.html` includes it unconditionally) and by HTMX OOB swaps everywhere. The `better-registration` qa_report flagged a live, unfixed cross-spec issue: "Mobile completion view: success toast overlaps the page heading."

Hooks: trigger Django messages on at least three different routes (signup confirmation, course registration, profile update) and verify they land in the toast region; verify HTMX 422 paths.

### 6.3 Educator panel framework — `freedom_ls/panel_framework/`

Touched by `educator-interface-better-nav`, `educator-experience-bug-fix`, `educator_interface_basic_functions`. Also exercised by the cohort-course-progress dual-paginator.

Risks:
- Recursive panel-render bug (the bug `educator-experience-bug-fix` solved); regression any time a panel's HTMX target changes.
- HTMX query-param preservation across pagination + sort + search.
- Course-progress grid: independent column / student paginators + deadline / override rendering — a single CT/`object_id` confusion mis-paints the grid silently.

Hooks: large-cohort scenario via `qa_create_large_cohort` + `qa_add_course_items_for_pagination`; interleave page changes on both axes; confirm only one Students/Cohorts/Course Registrations heading at any time.

### 6.4 Auth + middleware

Touched by `better-registration`, plus any spec that overrides `ACCOUNT_FORMS`. Risks:

- `accounts.AppConfig.ready()` race during runserver autoreload (tangential in `better-registration`) where `SiteAwareSignupForm` reverts to default allauth form.
- `complete-registration` middleware redirect loops — must exempt `legal/<doc>/`, `logout/`, `password/reset/...`.
- T&C / privacy clickwrap: missing legal markdown emits W001 system check — verify both docs are committed and reachable.

Hooks: full signup with a fresh email, follow link from `gitignore/emails/`, walk through complete-registration, then verify password reset still works while incomplete.

### 6.5 Student dashboard partials (`student_interface/templates/student_interface/home.html` + `partials/course_list.html`)

Touched by `fix-fouc-and-empty-sections`. Risks:
- Stray "Recommended Courses" heading reappearing for users with no recs.
- `get_current_courses` excludes completed courses → "Your Courses" empty-state for users whose only registration is completed (already pre-existing; must not regress in the other direction).

Hooks: the five user states (empty, current-only, recs-only, history-only, all three).

### 6.6 Course content shell (`_course_base.html` + cotton `picture.html`, `dropdown-menu.html`, `modal.html`)

Touched by `fix-fouc-and-empty-sections`, `course-page-small-fixes`, `bugfix-cant-expand-toc-on-course-page`, `mobile-responsiveness-audit` (older). Risks:
- Picture-zoom modal re-introducing FOUC if a developer forgets `x-cloak`.
- TOC `coursePart_<slug>_<id>` localStorage key shape — any refactor breaks persistence silently.
- Next/Prev navigation buttons (icons + visibility) — behaviour differs at last item / form-complete / failed-quiz states.

Hooks: walk a multi-part course end-to-end with mid-walk reload; reload `/courses/<slug>/1/` repeatedly and screenshot first paint to catch picture-modal flash.

### 6.7 Multi-tenant / Site context

Touched by `bug-FORCE_SITE_NAME-is-ignored-for-existing-sites`, `bugfix-allauth-emails-malformed`, `security-audit`, `outward-webhooks`. Cross-cutting because every model is `SiteAwareModel`.

Hook: confirm `current_site.domain` matches the site under test on every page (the `debug-branch-badge` proves the worktree but not the active Site). Compare admin's "Sites" table vs the rendered `site_title` in `header_bar.html`.

### 6.8 Webhooks

`course.completed` fires from `course_finish`. Any change to `freedom_ls/webhooks/events.py` or webhook URL routing can drop events. Hook: complete a course end-to-end, then check `WebhookEvent` rows via admin or qa-data-helper.

---

## 7. Proposed scoping inputs for the new command

State to read at run time so the test scope adapts:

1. **Recent done specs window** — read all dirs under `spec_dd/3. done/` whose date prefix is within last N days (default 14). Sort newest-first. For each, inspect `1. spec.md`, `3. frontend_qa.md`, `qa_report.md` (pre-existing tangential notes become candidate regressions). Touched files can be inferred from `git log --name-only` between merge points; the `catchup` plugin command may already do something similar.
2. **Cross-cutting inventory** — match touched files against §6 hot-spots and elevate scope.
3. **DemoDev demo content baseline** (§4.5) — re-validate via qa-data-helper rather than assume.
4. **Existing qa_helpers commands** (§4.4) — declare what scenarios are pre-baked.

---

## 8. Things the command MUST NOT do

- Create data via `manage.py shell -c`; always delegate to qa-data-helper.
- Run `db_clear.sh` / `db_recreate.sh` / `dev_db_delete.sh` — destructive.
- Skip the `#debug-branch-badge` branch-name check — silent worktree-bleed is a known failure.
- Exceed the 1024 KB pre-commit limit on any captured screenshot — always run `compress_screenshots.py` first.
- Test against any Site other than DemoDev.
- Read or reference other worktrees.
- Mark a test PARTIAL because data is missing without first invoking qa-data-helper.
- Test CSS classes; restrict findings to user-visible behaviour and DOM structure.
- Hand-write a fix while QA-ing — findings go in the report; remediation is a follow-up spec.

---

## 9. Suggested report skeleton

Mirroring §3 plus a new "scoping rationale" section because exploratory QA must justify what it covered and what it skipped:

```markdown
# System QA Report — <branch> — <date>

**Branch:** ...
**Site:** DemoDev (`http://127.0.0.1:<port>/`)
**Tooling:** Playwright MCP, Django runserver, qa-data-helper
**Window scanned:** spec_dd/3. done/ entries since <ISO date>

## 1. Scoping rationale
- Specs reviewed: ...
- Hot-spots prioritised: ...
- Surfaces deliberately skipped: ...

## 2. Results table
| Area | Test | Result |
| ... | ... | ... |

## 3. Findings
### [Area] — <short title>
- Spec(s) implicated: ...
- Steps observed: ...
- Expected vs actual: ...
- Screenshots:
  ![desktop](screenshots/desktop_<id>_<desc>.png)
  ![mobile](screenshots/mobile_<id>_<desc>.png)

## 4. Tangential observations
... (carried forward across runs)

## 5. Skipped / deferred
... (with reason)

## 6. Setup notes
... (qa-data-helper invocations, port, runserver lifecycle)
```

---

## 10. Quick file-path index for the command author

| Need | Path |
|---|---|
| Existing per-spec QA command (template) | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/commands/sdd/do_qa.md` |
| qa-data-helper agent | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/agents/qa-data-helper.md` |
| Find free port | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/scripts/find_available_port.sh` |
| Kill runserver | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/scripts/kill_runserver.sh` |
| Compress screenshots | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/fls-claude-plugin/scripts/compress_screenshots.py` |
| Recent done specs | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/spec_dd/3. done/` |
| Demo content seed | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/student_management/management/commands/create_demo_data.py` |
| QA helpers app (mgmt cmds) | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/qa_helpers/management/commands/` |
| Toast playground (DEBUG) | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/qa_helpers/toast_views.py` |
| Root URLconf | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/config/urls.py` |
| Student URLs | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/student_interface/urls.py` |
| Educator URLs (catch-all) | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/educator_interface/urls.py` |
| Educator view registry | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/educator_interface/views.py` |
| Account URLs | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/accounts/urls.py` |
| Account middleware | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/accounts/middleware.py` |
| Base layout | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/base/templates/_base.html` |
| Sidebar/interface shell | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/base/templates/_base_interface.html` |
| Header bar | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/base/templates/partials/header_bar.html` |
| Messages / toasts | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/base/templates/partials/messages.html`, `_toast.html` |
| Cotton component library | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/base/templates/cotton/` |
| Playwright fixtures | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/tests/playwright_fixtures.py` |
| Existing E2E test | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/student_interface/tests/e2e/test_course_toc.py` |
| Project conventions | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/CLAUDE.md` |
| The new command's home | `/home/sheena/workspace/lms/freedom-ls-worktrees/main/spec_dd/1. next/system_qa/idea.md` |
