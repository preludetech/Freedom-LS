# Research: consolidating the Playwright tests into flow tests

Scope: the 226 `playwright`-marked tests (189 `def test_` across 52 files; the rest is `parametrize` expansion). Facts only, no implementation steps.

## 1. Inventory

Per-test boilerplate that nearly every file repeats:

- `@pytest.mark.playwright` + `@pytest.mark.django_db(transaction=True)` (or a module `pytestmark`). `live_server` itself forces transactional DB, so the explicit `transaction=True` is redundant but harmless (pytest-django docs: https://pytest-django.readthedocs.io/en/latest/helpers.html).
- `live_server` + `live_server_site` (+ `mock_site_context`): requests rewrite the `Site` domain per test (`freedom_ls/conftest.py:315`).
- Fresh `page` (new BrowserContext) per test; logged-in tests go through `logged_in_page` or `educator_logged_in_page`, which drive the allauth login form per test (`freedom_ls/tests/playwright_fixtures.py:145-201`, `freedom_ls/educator_interface/tests/playwright/conftest.py:17-41`).
- Factories create data inside the test body (CohortFactory, OrganisationFactory, CourseFactory, `_make_stub`, `course_with_single_question_form` + `register_user_for_course`).
- `page.set_viewport_size(...)` inside the test, with viewport constants re-declared in each file (`_PHONE_VIEWPORT`, `_MOBILE_VIEWPORT`, `_DESKTOP_VIEWPORT`, `_TABLET_VIEWPORT` all appear independently in panel_framework and educator_interface files).

Kind column: B = behaviour (JS/HTMX/dialog/focus/history), L = layout/screenshot-style (bounding boxes, overflow, corner radius, colour), M = mixed.

### panel_framework (`freedom_ls/panel_framework/tests/playwright/`, no login; stub routes under `/test-panel/framework/stubs/`, `_make_stub` from `tests/conftest.py`)

| File | Tests | What it exercises | Kind |
|---|---|---|---|
| test_modal_form_htmx.py | 15 | create modal: focus on open, duplicate-name error focus, save / save-and-add-another / Enter, cancel, Esc clean vs dirty, discard confirm, keep editing, backdrop click, double-submit | B |
| test_data_table_panel_htmx.py | 12 | DataTablePanel sort, pagination, search, URL push, back restore, focus after swap, sibling table page param, filter/sort sheet hidden at desktop and phone | B (2 viewport) |
| test_quick_view_htmx.py | 10 | quick view drawer: row click, title, second row, same-row toggle, Esc/focus return, ctrl-click new tab, server error + retry, race cases | B |
| test_quick_view_mobile_htmx.py | 6 | quick view at phone/tablet: page usable, Esc, scroll clear of sheet, breakpoint crossing with no new request, sheet corner radius, tablet square corners | M |
| test_quick_view_layout_htmx.py | 5 | docked drawer pinned, content room, overlay below 1280, mobile sheet full width, print media | L |
| test_modal_layout_htmx.py | 4 | modal centred at desktop, pinned bottom at phone, close button corner, buttons fit | L |
| test_dialog_history_htmx.py | 4 | back after navigating away with modal / quick view open, refetch on reopen, no page error | B |
| test_bulk_actions.py | 4 | header checkbox tristate, selection clears on sort, stub bulk action (JS off and confirm modal) | B |
| test_list_view_refresh_htmx.py | 3 | save-and-add-another refreshes table, keeps page, leaves focus | B |
| test_mobile_cards.py | 3 | phone cards vs table, sheet filter/sort, card checkboxes drive the bulk bar | M |
| test_modal_read_only_htmx.py | 3 | read-only fragment focus, backdrop click closes, padding click does not | B |
| test_modal_delete_htmx.py | 2 | delete modal initial focus, delete navigates to list | B |
| test_instance_title_htmx.py | 2 | title-changed event updates heading; long unbroken title does not widen page | B / L |
| test_sortable_header.py | 2 | sort link colour equals header colour; sort icon size when squeezed | L |
| test_progress_bar_fill.py, test_stat_tile_progress_width.py | 1 each | progress bar computed colour / non-zero width | L |
| test_tab_navigation_htmx.py | 1 | tab switch, back/forward keep URL and tab together | B |
| test_panel_toggle.py | 1 | toggle in heading row, survives navigation (mobile) | M |
| test_table_sheet_no_js.py | 1 | sheet visible on phone with JS off (own `browser.new_context(java_script_enabled=False)`) | B |
| test_component_reference.py | 1 | reference page loads and is tappable on mobile | M |

### educator_interface (`freedom_ls/educator_interface/tests/playwright/`, staff user, login per test, own `conftest.py`)

| File | Tests | What it exercises | Kind |
|---|---|---|---|
| test_sidebar_sheet_dialog_binding.py | 5 | mobile nav button opens navigation not the table filter sheet; first Tab on desktop; reduced motion; widening past lg docks sidebar; rounded top corners | M |
| test_learner_quick_view.py | 5 (+param) | learners list quick view: open, title on reopen, Esc closes only topmost dropdown, learner-changed event refetch, trigger alignment over viewports | M |
| test_create_cohort_dialog_mobile.py | 4 | create cohort dialog at phone: fields/buttons in viewport, cancel keeps form, Esc after widening, dirty Esc discard | M |
| test_quick_view_layout.py | 4 (+3 widths, + viewport param) | docked drawer vs header/table, pagination inside card, clears header after widening, page stays put | L |
| test_organisation_switcher_mobile.py | 4 | switch org from mobile sheet closes sheet and Back is consistent; section link without reload; focus into new content; close returns focus | B |
| test_organisation_switcher.py | 2 | desktop live region retained; keyboard switch focus and announce | B |
| test_denied_experience.py | 2 | grant revoked while create modal open; cohort leaves scope while delete dialog open | B |
| test_edit_modal.py | 1 | edit cohort name closes modal, title updates | B |
| test_delete_modal.py | 1 | delete cohort from page with no failing requests | B |
| test_learners_mobile.py | 1 | learners list no horizontal scroll on phone | L |

### learner_interface (`freedom_ls/learner_interface/tests/playwright/`, learner login per test; course/form factories from `learner_interface/tests/conftest.py`)

| File | Tests | What it exercises | Kind |
|---|---|---|---|
| form_ui_tests.py | 7 | landing page, start + fill + submit, resumption, quiz scores shown, incorrect answers shown/hidden, scores on landing page (CSS-selector style, `networkidle` waits) | B |
| test_course_toc.py | 7 | TOC part expand/collapse, state persists, back closes mobile sheet, mobile sheet height clamp, side drawer width cap, aria announcements | M |
| test_course_card_layout.py | 4 (x viewports) | mixed card grid overflow, click card away from title (course and article), focused link inside card | L / B |
| test_form_submit_navigation_guard.py | 4 | beforeunload guard disarmed / armed; submit navigates to completion | B |
| test_flashcard_overflow.py | 3 | wide answer overflow at mobile; table scrolls; prose click flips card | L / B |
| test_picture_spotlight.py | 3 | closed spotlight inert; background does not scroll when open; long description heading reachable | M |
| test_course_detail_layout.py | 2 | detail page overflow; outline title ellipsis at phone | L |
| test_course_detail_price_stat.py | 2 (+params) | price stays inside stat cell; stacked cells equal width | L |
| test_form_required_validation.py | 2 | submit dialog blocked until required answered; required checkbox group | B |
| test_form_answered_count.py, test_form_exit_submits_page_answers.py, test_form_submit_dialog_focus.py, test_form_option_layout.py | 1 each | answered count; leave-and-submit scores page; submit dialog focus trap; option rows overflow | B,B,B,L |

### Other apps

| File | Tests | What it exercises | Kind |
|---|---|---|---|
| comms/test_notification_bell.py | 11 | bell: open/aria, Esc focus, Enter, badge zeroing in one request, mark all read, keyboard focus, badge refresh, other user's registration, self-registration, 375px sheet, failed reopen retry | B (1 L) |
| comms/test_notification_centre.py | 9 | unread filter, mark read/unread, row click, mark all, pagination + URL, filter survives reload/back, keyboard focus | B |
| blog/test_article_layout.py | 8 | index/article overflow, card click away from title, focused link in card, lightbox, card/picture same row height | L (1 B) |
| referral_tracking/test_referral_code_copy_button.py | 4 | admin change page copy-to-clipboard buttons (needs clipboard permissions) | B |
| referral_tracking/test_admin_detail_mobile.py | 1 | admin detail at mobile | L |
| base/test_toast_dismiss.py | 2 | injected Alpine toast dismiss removes node; stack order (`page.evaluate` DOM injection, not a server flow) | B / L |
| form_engine/test_admin_answers_layout.py | 1 | admin answers layout | L |
| course_applications/test_application_form_flow.py | 2 | applicant fills, attaches file, leaves and returns, submits (already a flow) | B |
| tests/playwright/test_design_screenshots.py | 3 | runs `claude_plugins/sdd/scripts/design_screenshots.py` as a subprocess against static HTML (no `live_server`, no Django DB, tooling test marked `playwright`) | tooling |

### Where several tests drive the same page / candidate flows

These are candidate groupings only; the "replaces" column lists existing tests whose arrange step is identical.

1. **Create modal lifecycle (panel_framework)**: `test_modal_form_htmx.py` (15) + `test_list_view_refresh_htmx.py` (3) + `test_modal_layout_htmx.py` (4) all open the same stub create modal on `/test-panel/framework/stubs/`. One flow: open (focus) -> type -> Esc dirty -> keep editing -> discard -> reopen -> duplicate name -> fix -> save and add another (blank form, table refresh, page kept) -> save (history entry). Replaces ~20 tests. Double-submit and JS-off cases need separate contexts and stay separate.
2. **Data table interaction (panel_framework)**: `test_data_table_panel_htmx.py` (12) + `test_sortable_header.py` + `test_bulk_actions.py` (2 of 4) + `test_tab_navigation_htmx.py`. One flow: sort x3 (no nested panel) -> paginate -> back -> search -> select rows (tristate) -> sort clears selection -> tab switch back/forward. Replaces ~16.
3. **Quick view on desktop (panel_framework)**: `test_quick_view_htmx.py` (10) + `test_dialog_history_htmx.py` (4) share the arrange; the race/error cases (server error + retry, close mid-load) need route interception and are natural separate steps or small separate tests.
4. **Delete / read-only / denied dialogs**: `test_modal_delete_htmx.py` (2), `test_modal_read_only_htmx.py` (3), educator `test_delete_modal.py`, `test_edit_modal.py`, `test_denied_experience.py` (2).
5. **Educator cohort management via panel_framework dialogs** (educator login once): `test_edit_modal.py` + `test_delete_modal.py` + `test_denied_experience.py` + `test_create_cohort_dialog_mobile.py` + `test_learner_quick_view.py` + `test_organisation_switcher*.py`. Candidate: educator logs in, switches org, creates a cohort, edits its name (title updates), opens a learner quick view, deletes the cohort. The three `educator_interface` mobile files (`test_organisation_switcher_mobile.py`, `test_sidebar_sheet_dialog_binding.py`, `test_create_cohort_dialog_mobile.py`) each define their own phone-viewport login fixture over the same mobile sheet.
6. **Learner completes a form** (learner login once): `form_ui_tests.py` (7), `test_form_answered_count.py`, `test_form_required_validation.py` (2), `test_form_submit_dialog_focus.py`, `test_form_submit_navigation_guard.py` (4), `test_form_exit_submits_page_answers.py`; plus `course_applications` flow. Each builds a form course and registers the user (`course_with_single_question_form` + `register_user_for_course`) and logs in. Natural flow: landing -> start -> answered count -> required block -> fill -> Next -> submit dialog focus trap -> submit -> completion -> landing shows scores. Guard-armed / disarmed checks fit inside it as `evaluate` steps.
7. **Course browse (learner)**: `test_course_card_layout.py`, `test_course_detail_layout.py`, `test_course_detail_price_stat.py`, `test_course_toc.py`, `test_flashcard_overflow.py`, `test_picture_spotlight.py`. Flow: grid -> click card -> detail -> TOC expand / persists -> open item (flashcard flip, spotlight).
8. **Notifications (comms)**: `test_notification_bell.py` (11) + `test_notification_centre.py` (9). Flow: other user registers -> badge -> open panel (one request) -> mark all read -> centre page -> filter -> paginate -> back.
9. **Mobile layouts at the QA viewports**: all `L` tests parametrised on viewport (`test_course_card_layout`, `test_course_detail_layout`, `test_course_detail_price_stat`, `test_form_option_layout`, `test_flashcard_overflow`, `blog/test_article_layout`, `educator test_quick_view_layout`, `panel_framework test_quick_view_layout_htmx`, `test_modal_layout_htmx`, `test_learners_mobile`, `test_admin_detail_mobile`, `test_admin_answers_layout`). One test per page that sets viewport in a loop (375x812, 768x1024, 1920x1080, the three viewports used by `frontend_check.md`) and asserts no horizontal overflow. Several already parametrise over exactly those viewports, so each viewport costs a separate test, a fresh context and (where logged in) a separate login.
10. **Staying separate**: `test_table_sheet_no_js.py` and `test_bulk_actions.py::test_stub_bulk_action_js_off` (need `java_script_enabled=False` context); referral copy-button (needs clipboard permission context and admin login); `test_design_screenshots.py` (no app, subprocess).

Screenshot/layout versus behaviour: roughly 55 tests are layout checks (bounding-box, overflow, corner radius, computed colour, print media, pixel widths): all the `*_layout*`, `*_overflow*`, `price_stat`, `progress_bar_fill`, `stat_tile_progress_width`, `sortable_header`, `corners` tests. They assert CSS outcomes that no Django `Client` can see and are the best fit for being collapsed per-page and per-viewport.

## 2. Where the time goes in setup

- **Browser**: session-scoped (pytest-playwright default; `playwright`, `browser`, `browser_type` are session scoped; https://playwright.dev/python/docs/test-runners). Launched once per pytest process. The repo overrides `playwright` in `freedom_ls/tests/playwright_fixtures.py:96-100` only to close DB connections at teardown. Only `test_table_sheet_no_js.py` creates its own context via `browser.new_context(...)`.
- **Context / page**: function scoped (default). A new BrowserContext and Page per test; `reset_local_storage` is autouse and calls `request.getfixturevalue("page")` for every test that mentions `page`/`logged_in_page` (`playwright_fixtures.py:103-142`); the evaluate it does on `about:blank` is documented in its own comment as a no-op. No `browser_context_args` override exists anywhere in the repo.
- **`live_server`**: pytest-django's fixture; thread-backed server with `transactional_db`. Every test is `transaction=True`, so pytest-django flushes the whole database at the end of each test (`TRUNCATE` over all tables). `live_server_site` also does a `Site.save()` per test.
- **Login**: repeated per test through the UI. `logged_in_page` / `educator_logged_in_page` / the per-file `mobile_educator_page` fixtures goto the login URL, fill, click and wait for redirect (`_login_via_ui`, `playwright_fixtures.py:145-164`). Roughly 150 of the tests use a logged-in fixture (the 162 fixture-usage hits above include the fixture definitions). `storage_state` is deliberately not used; the module docstring (`playwright_fixtures.py:26-46`) says a session-scoped login would be invalidated because `transaction=True` flushes the user and session row after every test. This is the reason a flow test is the only route to amortising login given the current DB strategy. Admin-site tests (`referral_tracking`) each build their own admin user fixture, duplicated in two files.
- **Test DB**: created once per session by pytest-django; each test creates its own users, organisations, courses via factories after the previous flush. `panel_framework` additionally creates stub tables once per session (`panel_framework/tests/conftest.py:97-129`) and uses `/test-panel/` routes with no login, so those ~100 tests pay no login cost, only context + flush + factories.
- **xdist**: installed (`pyproject.toml:66`) but opt-in only (`claude_plugins/django-stack/skills/testing/SKILL.md:45` says `uv run pytest -n auto`); not in `addopts`, and CI runs `uv run pytest -m playwright --no-cov` with no `-n`, so the CI browser job is serial. Root `conftest.py:15-17` caps `-n auto` at 4 workers. With xdist, each worker would need its own database and `live_server` port (pytest-django suffixes DB names per worker automatically).
- **pytest-randomly**: installed and active, so order is shuffled every run. Existing tests are therefore already order-independent, which a flow test keeps trivially true.
- **Always-on cost**: `addopts` includes `--tracing=retain-on-failure --screenshot=only-on-failure` (`pyproject.toml:83`), so tracing is recorded for every test and discarded on pass. CI also passes `--no-cov`; locally `--cov --cov-branch` is in addopts.
- **Timeouts**: `timeout = 300` per test (`pyproject.toml:90`); CI job `timeout-minutes: 15` for all playwright tests (`.github/workflows/tests.yml:92`).
- **CI**: the Playwright job reinstalls npm, builds Tailwind and installs Chromium each run; this is fixed cost regardless of test count.
- Some waits are blunt: `form_ui_tests.py` uses `wait_for_load_state("networkidle")` and `wait_for_selector(..., timeout=5000)` per step, and CSS-selector locators contrary to the skill's semantic-locator guidance.

## 3. Best practice from the web, and what it means here

- **pytest-playwright scopes** (https://playwright.dev/python/docs/test-runners): `browser` is session scoped, `context` and `page` are function scoped; `browser_context_args` overrides `new_context()` options (viewport, permissions, storage_state, java_script_enabled) and can be a per-test marker; `--tracing` and `--screenshot` apply to the default fixtures only. Means: browser launch is already amortised; the per-test costs are context creation (cheap), login, factories and the DB flush. A per-flow viewport/permissions setup can use `browser_context_args` or `page.set_viewport_size`; tests that call `browser.new_context()` themselves (e.g. `test_table_sheet_no_js.py`) do not get `--tracing`/`--screenshot` artifacts.
- **Reusing authentication** (https://playwright.dev/python/docs/auth): `context.storage_state()` then `browser.new_context(storage_state=...)`; cookies and localStorage restore, sessionStorage does not; do not commit the state file. Means: the repo's own resource (`claude_plugins/django-stack/resources/playwright-testing.md:129-183`) recommends session `storage_state`, but `playwright_fixtures.py` documents that it cannot work while every test flushes the DB. Consolidating into flows (login once per flow) is the option that needs no change to the DB strategy; `storage_state` would need data that survives the flush (serialized-rollback or a non-transactional approach).
- **Isolation vs long tests** (https://playwright.dev/docs/best-practices): Playwright recommends that "each test should be completely isolated" with own storage, data and cookies, to avoid cascading failures and aid debugging, and allows `beforeEach` for repeated login steps; it gives no guidance on test length, and says a little duplication is acceptable. Means: flow tests deviate from Playwright's default recommendation; the cost is that a flow stops at the first failing step and later steps are not reported, and a failure in step 9 of 12 needs the trace to locate. Mitigation within the tooling: `--tracing=retain-on-failure` already captures a full trace, and `expect` auto-waiting plus step comments localise failure; `pytest.mark` cannot split steps, so a failing early step masks later regressions until fixed.
- **Fewer, longer tests** (Kent C. Dodds, https://kentcdodds.com/blog/write-fewer-longer-tests): argues for one test per user workflow, one Arrange, many Act/Assert steps, because shared nested setup and one-assertion-per-test are outdated; failure localisation is judged manageable because the failing assertion and DOM are shown. He does not discuss setup cost, so the setup-cost argument for this repo is ours, not his; and his context is React Testing Library, not browser tests where each step is orders of magnitude slower. The "testing trophy" framing (favouring integration over unit) is about test type mix, not about long browser flows; it supports moving server-rendered checks out of the browser less than it supports long integrated tests.
- **xdist** (https://playwright.dev/python/docs/test-runners): `pytest --numprocesses auto` runs tests concurrently; too high a worker count causes flakiness. Means: the suite's cost is dominated by serial per-test setup in a single CI process; `-n` on the playwright job is not used today. Fewer flow tests also parallelise coarsely (one slow flow bounds wall time), so flow granularity should leave several flows per worker.
- **pytest-django `live_server`** (https://pytest-django.readthedocs.io/en/latest/helpers.html): runs the server in a background thread, depends on `transactional_db` (different thread, cannot share a transaction), and docs mention `django_db_serialized_rollback` for data created by data migrations. Means: every Playwright test pays a full-table flush; fewer tests means fewer flushes and fewer factory builds. The docs do not mention xdist.

## 4. What should stay a Django-client test versus Playwright

These are observations from the test bodies and docstrings read; each would need a body-level check before moving.

Assertions a `django.test.Client` response (or `RequestFactory` render) could check without a browser:

- Server-rendered text/element presence in `form_ui_tests.py::test_view_form_landing_page` (h1 text, subtitle, start button, "Previous Submissions" heading), `test_quiz_completion_shows_scores`, `test_quiz_shows_incorrect_answers_when_enabled` / `..._not_..._disabled`, `test_completed_quiz_shows_scores_on_landing_page` (scores and incorrect answers are server-rendered), `test_form_resumption` (state is server-side), `test_start_and_fill_form_complete_workflow` (the workflow could be posted via client; the radio / label clicks are the only JS).
- `educator_interface/test_organisation_switcher_mobile.py` states "That the switch serves Org B's content is proven in the fast tests", showing the pattern already in use.
- `test_notification_bell.py::test_a_registration_someone_else_made_shows_in_the_panel` and `test_self_registering_adds_nothing_to_the_panel` (content of the panel for a given user; the bell opening is the JS part).
- `test_notification_centre.py`: unread filter rows, pagination second page, filter survives reload (query-string driven, server rendered).
- `test_course_toc.py::test_part_row_announces_in_progress_over_completed_children` and `..._does_not_announce_chevron_state` (aria attributes in server markup).
- `test_denied_experience.py` (the denial is a 403/410 server decision; the modal swap is the JS part).
- `test_data_table_panel_htmx.py::test_pagination_preserves_sort_param_through_clicks` (links rendered with `stubs-sort` baked in; the test itself waits on the rendered href) and the `nest panel wrappers` assertions if the HTMX partial response is asserted directly (the bug is in what HTMX swaps, so a Client test of the sort-region response is the unit-level equivalent).
- Anything in `test_course_card_layout` / `blog` that is only "clicking the card opens the course": the stretched-link `href` is in server HTML; the click-target geometry is CSS.

Genuinely need a browser: Alpine/HTMX swaps and focus management (`test_modal_form_htmx`, `test_quick_view_htmx`, `test_data_table_panel_htmx` focus tests, notification bell), `<dialog>` modality and Esc/backdrop behaviour, session-history/back behaviour (`test_dialog_history_htmx`, `test_tab_navigation_htmx`, org-switcher Back), beforeunload guard, copy-to-clipboard (referral; the test file itself says the test client cannot do this), JS-disabled behaviour, toast dismissal timing, and every `L` layout test (bounding boxes, overflow, computed style, print media, reduced motion).

## 5. Related commands that drive browsers outside pytest

- `claude_plugins/fls-dev/commands/do_qa.md`: runs a QA plan with Playwright MCP against a `runserver` on a free port, at 1920x1080, 375x812 and 768x1024, takes screenshots, writes `qa_report.md`, and triages bugs into a fixer. It explicitly says "DO NOT write test scripts", and its green-lane test (Step 13) says a Playwright pytest test can prove a fix, so the QA command is a producer of new `playwright`-marked tests via `fls-dev:qa-bugfixer`. Overlap with pytest: it uses the same three viewports as the layout tests and the same pages (listing, detail, educator panels) for visual judgement; it reads semantic correctness and design comparison, which the pytest suite does not cover. Tension: bugfixer-added regression tests are a source of the one-file-per-bug layout of the current suite (docstrings such as "Regression: ..." in `test_form_submit_navigation_guard.py`, `test_picture_spotlight.py`, `test_instance_title_htmx.py`).
- `claude_plugins/fls-dev/commands/protected/frontend_check.md`: after a rebase, smoke visit (navigate, snapshot, console errors; no screenshots) of up to eight pages at the same three viewports; fails on 500/404, traceback, missing nav/primary content, console error, small-viewport nav overflow. Overlaps pytest only loosely (overflow / nav presence at 375 and 768); no pytest test visits pages for console errors or 500s generically.
- `claude_plugins/fls-dev/commands/protected/design_check.md`: full-page screenshots at design widths for comparison against the design; no pytest equivalent.
- `tests/playwright/test_design_screenshots.py` (3 tests): tests `claude_plugins/sdd/scripts/design_screenshots.py` (tooling, subprocess, static HTML; no `live_server`). It carries `@pytest.mark.playwright` so it only runs in the browser CI job, but the idea says tests for tooling (qa helpers) should not be run; this is the one Playwright-marked test of developer tooling. It does not overlap app coverage.
- `claude_plugins/fls-dev/skills/playwright-tests/SKILL.md` only explains the `playwright` marker rationale (downstream exclusion) and defers to `ds:playwright-tests`; it contains no guidance on flow vs per-value tests, on login reuse, or on when to prefer a Client test. `claude_plugins/django-stack/skills/playwright-tests/SKILL.md:35` recommends session `storage_state`, contradicting `playwright_fixtures.py:26-46`. `claude_plugins/django-stack/resources/playwright-testing.md:6` lists "User flows" as the use case. This is a skill/documentation inconsistency for the skills task.

status: ok
