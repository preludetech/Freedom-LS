# Research: codebase footprint of "Fewer, faster Playwright tests"

Question: what in the existing codebase does this work touch, reuse or conflict with?
Sources: files read in this worktree (paths and line numbers below). One external reference, <https://playwright.dev/python/docs/auth>, is named by idea.md and was not fetched.

## Headline findings

1. **No Playwright test has the sign-in form as its subject.** The only places that fill the allauth login form are the fixture helper `_login_via_ui` (`freedom_ls/tests/playwright_fixtures.py:145-164`) and its callers. The `get_by_label("Email")` hits in `course_applications/.../test_application_form_flow.py:249,315,363,397` are the applicant-details step, and `accounts/.../test_profile_picture_flow.py:196` is a profile dialog. So the "sign-in keeps its own tests" rule needs at least one new test: no Playwright test covers the login form today. `accounts/tests/test_allauth_pages.py` exists but is a Client test, not a browser test.
2. **The "session row is flushed" objection in the fixture docstring only bites a session-scoped cache.** A session created *inside* the test, after the user is created, lives in the `django_session` table until that test's end-of-test flush. A function-scoped "create session, add cookie" fixture is therefore compatible with `transaction=True` (`playwright_fixtures.py:29-46` rules out the session-scoped `storage_state`; it says nothing about a per-test cookie).
3. There is already working code that builds a session by hand: `freedom_ls/qa_helpers/management/commands/qa_login_session.py:29-46`.
4. Most of the viewport-loop merging is already done. Many files already loop `QA_VIEWPORTS` inside one flow (`playwright_helpers.py:8-12`, used e.g. at `api_admin/.../test_add_form_layout.py:42,77`, `test_profile_picture_flow.py:228`). What remains is separate tests per viewport or per concern in a few files (see "Repeated page" below).

## Settings that matter

- `pyproject.toml:85` `DJANGO_SETTINGS_MODULE = "config.settings_dev"`. `:92` addopts = `--strict-markers -m 'not ci_only and not weasyprint and not dev_tooling' --disable-socket --allow-hosts=127.0.0.1,::1 --tracing=retain-on-failure --screenshot=only-on-failure --dist loadfile`. `:94` registers the `playwright` marker.
- `--dist loadfile` means xdist keeps one file on one worker. A file's tests run serially, so merging inside a file never changes parallelism; the largest files set the wall-clock floor on a parallel run (`test_messaging_flow` 14 tests, `test_data_table_flow` 14, `test_file_upload_flow` 17 cases).
- `config/settings_base.py:247-252` `PASSWORD_HASHERS` starts with Argon2. A browser login verifies a password with Argon2 per test (spec 1 swaps the hasher; see Collisions).
- No `SESSION_ENGINE` is set, so sessions are database-backed (`django.contrib.sessions`, `SessionMiddleware` at `settings_base.py:181`).
- `config/settings_dev.py:141` `SESSION_COOKIE_NAME = f"sessionid_{_db_name}"`: the cookie name is per worktree and a hand-made cookie must use `settings.SESSION_COOKIE_NAME`, not `"sessionid"`.
- `AUTHENTICATION_BACKENDS` (`settings_base.py:351-356`): Axes, `ModelBackend`, guardian, allauth. A session only stores the backend dotted path; `qa_login_session.py:26` uses `django.contrib.auth.backends.ModelBackend`.
- `ACCOUNT_LOGIN_METHODS = {"email"}`, `ACCOUNT_EMAIL_VERIFICATION = "mandatory"` (`:449-450`), `LOGIN_REDIRECT_URL = "/"` (`:524`). Mandatory verification is enforced at login time by allauth, not by the session, which is why `logged_in_user` creates a verified `EmailAddress` (`playwright_fixtures.py:184-188`). A forced session skips that check, so the `EmailAddress` row is no longer needed for sign-in; keep it only if some page reads it.
- `ACCOUNT_RATE_LIMITS = False` in dev (`settings_dev.py:81`).

## Fixtures and markers

| Name | Where | Notes |
|---|---|---|
| `playwright` (session override) | `freedom_ls/tests/playwright_fixtures.py:96-100` | Closes DB connections before Playwright stops. Re-exported by `freedom_ls/conftest.py:22-27`; the root `conftest.py:17` `del playwright` so it is not registered twice. |
| `reset_local_storage` (autouse) | `playwright_fixtures.py:103-142` | Requests `page` for every test whose fixtures include `page` or `logged_in_page` (`_PAGE_FIXTURE_NAMES`, `:81`). |
| `logged_in_user` | `:171-189` | `UserFactory(password=<synthetic password>)` plus verified `EmailAddress`; depends on `db`, `live_server_site`, `mock_site_context`. |
| `logged_in_page` | `:192-201` | Calls `_login_via_ui`. |
| `_login_via_ui(page, live_server, email, password)` | `:145-164` | Goto `account_login`, fill Email/Password, click "Log in", `expect(page).not_to_have_url(login_url)`. Imported by name from 8 other files (list below). |
| `_LOGGED_IN_PASSWORD` | `:168` | Imported alongside `_login_via_ui`. |
| `educator_user`, `educator_logged_in_page`, `cohort_admin_user`, `cohort_admin_logged_in_page` | `educator_interface/tests/playwright/conftest.py:17-65` | Staff users (`UserFactory(staff=True)`); each page fixture calls `_login_via_ui`. `educator_user` and `cohort_admin_user` are identical apart from name. |
| `live_server_site` | `freedom_ls/conftest.py:325-330` | Sets `site.domain = urlparse(live_server.url).netloc` and saves. |
| `mock_site_context` | `freedom_ls/conftest.py:260-263` | `site_context(site)` for the test thread. |
| `reverse_url` | `freedom_ls/conftest.py:210-223` | Plain function. |
| `logged_in_client` | `freedom_ls/conftest.py:266-275` | Existing precedent: `Client().force_login(user)`. |
| `_reference_css_is_built` (session, autouse) | `panel_framework/tests/playwright/conftest.py:18-26` | Fails the package if `reference.css` is missing. |
| `QA_VIEWPORTS`, `assert_no_horizontal_overflow`, `assert_header_lines_up_with_content`, `assert_no_space_below_field_row`, `contrast_ratio` | `freedom_ls/tests/playwright_helpers.py` | Pure browser measurements (`getBoundingClientRect`, `getComputedStyle`). |
| framework copy of the helpers | `freedom_ls/panel_framework/tests/playwright/helpers.py`, `assertions.py` | `fls-dev` skill says edit both; `test_framework_copies_match_base.py` fails on drift (skill line 17). I did not open that test. |

Markers: every file carries `@pytest.mark.django_db(transaction=True)` (78 occurrences across 48 files, mostly one per file via a module-level or per-test mark; `course_applications` files mark per test: 18, 8, 4). `@pytest.mark.playwright` is the skill's required marker (`django-stack` skill line 24); I did not count its occurrences, so check that every file has it before the audit relies on `-m playwright`.

Why `transaction=True` is unavoidable: `live_server` serves from its own thread and DB connection, so the test's rows must be committed. pytest-django flushes all tables at test end (the docstring's claim, `:35-40`).

## Inventory of Playwright test files

Test counts are `def test_` per file (203 in total; the roadmap's 220 counts parametrized cases: 3 locales, 2 widths, 2 tabs, 2 viewports x2, the `_FAILURES` cases x2, 2 container selectors, the section-smoke list). Login column: **F** = `logged_in_page`-style fixture (form login via fixture), **H** = calls `_login_via_ui` itself, **-** = no sign-in.

| File (under `freedom_ls/`) | Tests | Login | Viewport / layout notes |
|---|---|---|---|
| accounts/tests/playwright/test_profile_picture_flow.py | 3 | F | loops `QA_VIEWPORTS` at :228 |
| api_admin/tests/playwright/test_add_form_layout.py | 3 | H x3 (`:40,52,75`) | one login per test; viewport loops at :42, :77 |
| base/tests/playwright/test_local_time.py | 1 (3 locales) | F | locale param, not viewport |
| base/tests/playwright/test_panel_surface_cascade.py | 2 | - | computed-style checks |
| base/tests/playwright/test_toast_dismiss.py | 1 | F | viewport at 2 places |
| blog/tests/playwright/test_article_flow.py | 1 | - | imports `QA_VIEWPORTS` |
| comms/tests/playwright/test_messaging_flow.py | 14 | F | 26 viewport references; 215s with members flow for 23 tests (timings research) |
| comms/tests/playwright/test_notifications_flow.py | 3 | F | 6 viewport refs |
| course_applications/.../test_application_form_flow.py | 9 | F for 4 learner tests, anonymous for the rest | 7 viewport refs |
| course_applications/.../test_phone_question_flow.py | 4 | F | 4 viewport refs |
| course_applications/.../test_withdraw_and_apply_again.py | 2 | F | |
| educator_interface/.../test_audit_log_flow.py | 4 | F (educator) | |
| .../test_cohort_detail_mobile.py | 2 | H (`:52`) via a phone-sized page fixture | same page (cohort detail) at a phone width in 2 tests |
| .../test_cohort_learner_counts.py | 1 | F | |
| .../test_cohort_management_flow.py | 3 | F | |
| .../test_cohort_report_layout.py | 5 | F | same Report tab in 5 tests (:42, :78, :111, :147, :220), several about sideways scroll and phone width |
| .../test_cohort_settings_staff_flow.py | 1 | F | |
| .../test_course_preview_flow.py | 1 | F | |
| .../test_create_cohort_add_and_add_another.py | 2 | F | |
| .../test_dashboard_attention_layout.py | 1 | F | |
| .../test_deactivate_reactivate.py | 1 | F | |
| .../test_keyboard_flow.py | 8 | F | quick-view and dialogs, one test at a phone (:91) |
| .../test_learner_import_flow.py | 2 | F | |
| .../test_learner_page_flow.py | 7 | F | |
| .../test_learners_list_flow.py | 12 | F | same Learners list in tests at :360, :403, :433, :464, :498, :535 each for one viewport or width |
| .../test_lost_access_flow.py | 4 | F | |
| .../test_members_flow.py | 8 (+1 param x2) | F | `@parametrize("width", [1280, 375])` at :359; 16 viewport refs |
| .../test_mobile_navigation_flow.py | 7 | F | 21 viewport refs; sidebar tests at :202, :250, :291, :322, :356, :398 |
| .../test_organisation_switcher_flow.py | 1 | F | |
| .../test_quick_view_messaging_flow.py | 2 | F | |
| .../test_register_deactivate.py | 1 | F | |
| .../test_section_smoke.py | 1 (parametrized list, from :65) | F | one page per case, checks console errors |
| .../test_touch_targets.py | 2 | F | 44px checks on a phone |
| form_engine/tests/playwright/test_admin_answers_layout.py | 1 | H (`:61`, admin) | |
| learner_interface/.../test_course_browse_flow.py | 12 | F | 36 viewport refs |
| learner_interface/.../test_form_flow.py | 8 | F | 13 viewport refs |
| learner_interface/.../test_organisation_course_flow.py | 3 | F | |
| mail/tests/playwright/test_admin_changelist_mobile.py | 1 | H (`:54`, admin) | phone width |
| messaging_policy/tests/playwright/test_admin_changelist_mobile.py | 2 | H (`:55`, admin) | phone width |
| panel_framework/.../test_component_reference_flow.py | 1 | - | |
| .../test_create_modal_flow.py | 4 | - | |
| .../test_data_table_flow.py | 14 | - | 43 viewport refs |
| .../test_editable_list_flow.py | 5 (+1 param x2) | - | |
| .../test_file_upload_flow.py | 17 (3 param groups) | - | |
| .../test_instance_dialogs_flow.py | 5 (2 param on viewport) | - | viewport parametrize at :177, :247: same page, two viewports as separate tests |
| .../test_quick_view_flow.py | 7 | - | |
| referral_tracking/.../test_referral_admin_flow.py | 2 | H x2 (`:89,126`, admin) | |
| registration_rules/.../test_rule_preview_flow.py | 2 | H x2 (`:49` admin, `:184` learner) | |

Totals from the counts above (approximate, derived from per-file greps, not run): about 147 test functions sign in through the form (fixture or helper); about 56 do not (all of `panel_framework` at roughly 53, plus `blog`, `panel_surface_cascade`, and the anonymous applicant tests). `panel_framework` tests run against a stub shell with no auth, so they gain nothing from a session shortcut. Roughly two thirds of the browser tests are the target population.

Files importing `_login_via_ui` directly (need the shortcut swapped in too): `api_admin/.../test_add_form_layout.py`, `educator_interface/.../conftest.py`, `.../test_cohort_detail_mobile.py`, `form_engine/.../test_admin_answers_layout.py`, `mail/.../test_admin_changelist_mobile.py`, `messaging_policy/.../test_admin_changelist_mobile.py`, `referral_tracking/.../test_referral_admin_flow.py`, `registration_rules/.../test_rule_preview_flow.py`.

Repeated-page candidates for merging (the audit decides; this is only where the greps point):
- `test_cohort_report_layout.py` (5 tests on the Report tab).
- `test_learners_list_flow.py` (6 layout tests on the Learners list at different widths).
- `test_mobile_navigation_flow.py` (6 tests on navigation and sidebar).
- `test_instance_dialogs_flow.py` (two tests parametrized over two viewports each; answers.md says one test loads the data once and resizes, so these become one test per concern).
- `test_members_flow.py:359` (width param).
- `test_cohort_detail_mobile.py` and the two `*_admin_changelist_mobile.py` files (one login per test for a single phone-width page).
- `api_admin/test_add_form_layout.py` (three tests, each logging in).
- `test_section_smoke.py` (one case per section, each a full login).

Sign-in and sign-up subjects: none among the Playwright files. Closest are the anonymous applicant flows in `test_application_form_flow.py` (`:231`, `:302`, `:352`, `:386`) which exercise a claim link that "signs a second browser in" (`:302`): that is an email-link sign-in, which must stay a real browser flow. The test at `:302` is a candidate for the form-based sign-in subject only if the audit finds it covers `adopt_anonymous_applications_on_login` through the form; otherwise a new login-form test is needed.

## How a signed-in session can reach the browser

Mechanism: in a function-scoped fixture, after the user exists, build a session row and add its cookie to the page's context, then goto a page.

Option A, `Client.force_login`:
```
client = Client(); client.force_login(user)
cookie = client.cookies[settings.SESSION_COOKIE_NAME]
page.context.add_cookies([{"name": settings.SESSION_COOKIE_NAME, "value": cookie.value, "url": live_server.url}])
```
`logged_in_client` in `freedom_ls/conftest.py:266-275` already does the first two lines. `force_login` calls `login()`, so it fires `user_logged_in` receivers: `course_applications/receivers.py:153` (adopt anonymous applications; returns early when `request is None or not hasattr(request, "session")`, line 166) and `referral_tracking/signals.py:70` (flush cookie touches; documented as safe with `request=None`, `:80-81`). It also updates `last_login`.

Option B, hand-built `SessionStore` as in `qa_login_session.py:33-37`: sets `SESSION_KEY`, `BACKEND_SESSION_KEY`, `HASH_SESSION_KEY` and calls `store.create()`. No signal fires and `last_login` stays untouched. Hash comes from `user.get_session_auth_hash()`, so it follows the password hash and is unaffected by spec 1 swapping the hasher, as long as the user is created with the hasher active at test time.

Complications checked:
- **Site-aware middleware**: `CurrentSiteMiddleware` (`site_aware_models/middleware.py:10-36`) only publishes the request on a thread local. It does not look at the session. The user lookup is by pk through `AuthenticationMiddleware`. `qa_login_session.py:32` uses `User._base_manager` to bypass site filtering, so a hand-built session must look the user up with the same care when the user is not the one the fixture just created. The fixture's own `user` object is already in hand, so no lookup is needed.
- **Cookie host**: `live_server_site` sets the Site domain to the live server's `host:port` (`conftest.py:325-330`). Pass `url=live_server.url` to `add_cookies` rather than `domain`. Hostname is `localhost` or `127.0.0.1`; `--allow-hosts` already allows `127.0.0.1,::1`. I did not run the suite to confirm which host `live_server.url` uses.
- **Cookie name**: `settings.SESSION_COOKIE_NAME` differs per worktree (`settings_dev.py:141`); production settings add `SESSION_COOKIE_SECURE` (`settings_prod.py:37`) but tests use `settings_dev`.
- **allauth**: login-time rules (mandatory email verification, `ACCOUNT_LOGIN_ON_*`) are not re-checked per request, so a session works without the `EmailAddress` row. `AccountMiddleware` (`settings_base.py:194`) only wraps responses.
- **Axes** (`AxesMiddleware`, `:196`, and `AxesStandaloneBackend`): Axes tracks failed logins and access attempts at the login view. A forced session skips them. Check `AxesStandaloneBackend` is not asked to authenticate on later requests; I did not find evidence it is.
- **Registration completion**: `RegistrationCompletionMiddleware` (`accounts/middleware.py:79-`) redirects non-superusers with incomplete additional registration forms. The form login and a forced session hit the same middleware, so behaviour is unchanged; superusers are exempt (`:93`).
- **Custom user model**: `UserFactory` builds site-aware users; nothing on the session path depends on the model beyond `pk` and `get_session_auth_hash`.
- **`transaction=True` and sessions**: the session row is committed by the test's own connection before the live server reads it, because `transaction=True` runs without a wrapping transaction. It is deleted at the end-of-test flush, which is fine for a per-test fixture. Nothing about the docstring's session-scoped trade-off applies.
- **`logged_in_user` ordering**: the fixture must create the session after `UserFactory`, and `live_server_site` must run first so the Site domain is right when the first request arrives. The existing dependency chain (`:172`) already guarantees both.
- **A `page` created before the cookie is added**: pytest-playwright makes the context per test; add the cookie to `page.context` before the first `goto`. `reset_local_storage` (`:103-142`) evaluates JS on `about:blank` only, so it does not clash.
- **Alternative, `storage_state`**: Playwright's documented approach (<https://playwright.dev/python/docs/auth>) needs the session to outlive a test, which `transaction=True` prevents. A per-test `context.add_cookies` is the same idea at test scope.
- **Fixture-shape unknowns for the spec**: the educator and admin fixtures (`educator_logged_in_page`, `cohort_admin_logged_in_page`, and the six per-file helpers) want one shared role-agnostic fixture, e.g. `sign_in(page, user)`, instead of eight copies. The current docstring (`:59-66`) says to add variants "the moment a second test needs them"; that moment is long past.

## Layout and viewport checks that could leave the browser

Measured in the browser by definition (need real layout): `assert_no_horizontal_overflow` (`scrollWidth <= innerWidth`), header/content alignment, `_SPACE_BELOW_LAST_CHILD`, contrast via canvas, 44px touch targets, tab strip in view, sticky bar covering a card. These cannot move to a Client test.

Candidates that check markup or server decisions rather than layout, and so could be a Client or template test (the audit must confirm each; I have not read these test bodies):
- `test_section_smoke.py` "section loads without console errors": the page load and heading/row text can be a Client test; only the console-error part needs a browser.
- `test_learners_list_flow.py:259, :330` "with javascript off": server-rendered fallbacks; the response HTML and POST handling is Client-testable (the skill says redirects, markup attributes and flash messages belong in a Client test, `fls-dev/skills/playwright-tests/SKILL.md:29`).
- `test_mobile_navigation_flow.py:356, :398` "navigation shows ... with javascript off": the left column versus above-content placement is CSS, so it stays in the browser; the presence of the nav links in the HTML does not need one.
- `test_learners_list_flow.py:297` "bulk picker returns to no choice when cleared": likely Alpine state, browser.
- `test_local_time.py`: the locale formatting is JS, browser.

Whether anything can move is for the audit: the fls-dev skill already states the Client-versus-browser line (`SKILL.md:29`), and the existing suite has Client tests for educator views (`educator_interface/tests/test_interface_urls.py`, `test_views.py`) that may already cover the markup half.

## Skills and docs to update

- `claude_plugins/django-stack/skills/playwright-tests/SKILL.md:22` already says "one login, one data build, many assertions, layout looped at the end"; `:33` "Log in once per flow. See the resource file for the login pattern." The generic resource `claude_plugins/django-stack/resources/playwright-testing.md:118-134` shows a form-login fixture. Both must say that the fixture signs in without the form and only the sign-in subject test drives the form. Generic plugin: no FLS names (CLAUDE.md "Plugins").
- `claude_plugins/fls-dev/skills/playwright-tests/SKILL.md:13` ("logged in through the allauth form") and `:19-21` ("Why transaction=True and a login per test ... login happens per test through the UI") become wrong and must be rewritten; `:16` mentions `QA_VIEWPORTS`. `claude_plugins/fls-dev/resources/playwright-testing.md:14` also describes the form-login fixture.
- `freedom_ls/tests/playwright_fixtures.py` module docstring (lines 15-24, 26-46, 59-66) states the trade-off the spec reverses.
- Downstream: `freedom_ls/conftest.py:19-27` star-imports these fixtures into concrete projects, so renamed or removed fixtures reach them. Keep `logged_in_page` and `logged_in_user` names, and keep `_login_via_ui` importable for the sign-in test.

## Collisions with sibling specs

- **1 fast password hasher** (in progress; `faster-test-runs-1-fast-password-hasher/idea.md`): overlaps the same saving. Today each form login costs one Argon2 verify plus one Argon2 hash in `UserFactory`. A fast hasher shrinks the benefit of skipping the form, so the "2 to 3 minutes" estimate should be measured after spec 1 lands, or state which baseline it uses. Technically independent: a forced session never calls the hasher. It touches `config/settings_*.py` and `freedom_ls/conftest.py`; this spec edits `playwright_fixtures.py` and `freedom_ls/conftest.py` re-export lines, so a merge conflict in `conftest.py` is possible but small.
- **2 reuse test database** (ready; `faster-test-runs-2-reuse-test-database/idea.md`): changes pytest startup and DB creation. Playwright's 55s of DB setup out of 215s (timings research, "Playwright") is the startup cost it removes; this spec's before and after timing must say whether it measures startup or test bodies, or the two specs' savings will be double-counted. Also the connection-closing fixture at `playwright_fixtures.py:84-100` (needed for `DROP DATABASE`) interacts with a kept database; do not remove it from this side.
- **6 prune slow tests** (ready; `faster-test-runs-6-prune-slow-tests/idea.md`): explicitly out of scope for Playwright ("Playwright tests ... which their own specs cover"), so no file collision. Its ranking will show the Playwright tests; the boundary is that this spec owns every file under `tests/playwright/`.
- **Other in-flight work to watch**: the educator-interface refactor (`educator-interface-refactor-5-learner`, `-6-cohort`) moves modules and tests but states `playwright/` stays where it is (roadmap "Decided: ... `invariants/`, `playwright/` and `migrations/` stay"). Merging tests in `educator_interface/tests/playwright/` could conflict textually if those specs touch imports or `mock.patch` paths in the same files.
- Roadmap decision: "no spec reduces what is tested without naming the test that still covers it" (`roadmap.md`, Faster test runs notes), plus answers.md: the audit's "goes" rows are approved in the spec review before any test is touched; stop at first failure (no soft assertions); one test loads the data once then resizes per viewport.

## Open points for the spec

- Choose Option A (`force_login`, fires login signals) or B (hand-built session, no signals). A is simpler and already used by `logged_in_client`; B matches `qa_login_session.py` and avoids `last_login` and receiver side effects. Whichever is chosen, the sign-in-subject test must still go through the form so `user_logged_in` receivers get a real request.
- Whether `logged_in_user` keeps the verified `EmailAddress` (only needed by pages that read it).
- A role-agnostic helper to replace `educator_logged_in_page`, `cohort_admin_logged_in_page` and six inline `_login_via_ui` callers.
- Baseline timing: measure the Playwright subset with `-m playwright` before changes, after spec 1 and 2 land if possible. The timings research has only 23 tests in 215s (about 7s each, 55s DB setup); there is no per-test Playwright breakdown yet.
- The audit's 220 count is cases; the file greps count 203 functions. The audit should list by node id, not by function.

status: ok
