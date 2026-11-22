# Prior art: fewer, faster Playwright tests

Question: what has already been tried for this, here or elsewhere, and what happened?

## In this repository

### 1. Phase 4 e2e hardening planned `storage_state` login and fell back (the key earlier decision)

- `spec_dd/3. done/2026-05-03_09:07_testing-best-practice-phase-4-e2e-hardening/1. spec.md` made
  "Login via `storage_state` is the default" (line 71). Per-test login was only for tests needing a
  fresh session (logout, signup).
- Its `2. plan.md` (steps 1 to 3) planned a session-scoped `authed_storage_state` fixture, a
  session-scoped `live_server` override to avoid `ScopeMismatch`, and a rewritten `logged_in_page`
  built from `browser.new_context(storage_state=...)`. It also wrote a fallback (line 149): if the
  storage-state fixture caused regressions, restore a function-scoped UI-login `logged_in_page`.
- What shipped is the fallback. The docstring of `freedom_ls/tests/playwright_fixtures.py`
  ("Scoping") records why: every E2E test is `@pytest.mark.django_db(transaction=True)`, so
  pytest-django flushes the whole database after each test. That deletes the synthetic user and the
  `django_session` row the cookie points at, so a cached `storage_state` is invalid by the second
  test. It concludes: "If a future test class can opt out of `transaction=True`, a session-scoped
  `storage_state` fixture can be layered on."
- The docstring only rules out a session-scoped, login-once state. It does not rule out creating
  the session per test (see "Gaps and options" below). That per-test route was not tried or
  evaluated anywhere in `spec_dd/`.
- The module also says role variants (`educator_logged_in_page`, etc.) are added only when a second
  test needs them. The educator tests now do that in
  `freedom_ls/educator_interface/tests/playwright/conftest.py`, which calls `_login_via_ui` for
  educator and cohort-admin users (lines 40 and 64). So there are at least three UI-login paths.
- Sibling fixtures: `playwright_fixtures.py` also holds an autouse `reset_local_storage` and a
  session `playwright` fixture that closes DB connections (to stop `DROP DATABASE` failing with
  "being accessed by other users"). Any new session-bound design must keep that cleanup working.

### 2. Measurements already taken

From `spec_dd/1. next/faster-test-runs/research_test_timings.md` ("Playwright"):

- 220 Playwright tests among 19,507.
- Sample: `comms/.../test_messaging_flow.py` plus `educator_interface/.../test_members_flow.py`, 23
  tests in 215s, 55s of that DB setup. About 7s per test. Slowest two 21s and 10s.
- Tests marked `transaction=True` show about 1s of teardown each (the flush). This is a fixed cost
  per browser test that neither merging nor login changes per test, but merging reduces how many
  times it is paid.
- Argon2 password hashing costs real time on every `UserFactory`. Swapping to MD5 cut one 230-test
  sample from 62.3s to 19.8s. Browser tests pay it for the factory user and again for the login
  verify. That belongs to another spec in the effort, but it shapes how much the form login costs.
- No per-test breakdown of "login share of the 7s" exists. That number is the one missing input for
  the "2 to 3 minutes" guess.

### 3. Playwright flakiness is already a problem in batch runs

`spec_dd/1. next/faster-test-runs/research_batch_test_load.md` (lines 72 to 74, 98): the tests that
failed in the most failed runs are Playwright flows: `test_learners_list_flow.py` (12 runs),
`test_members_flow.py` (11), `panel_framework`'s `test_data_table_flow.py` (11) and
`test_quick_view_flow.py` (9). Load average was 40 to 77. Whether these are load timeouts was not
measured. Implication for this spec: fewer, longer flows mean fewer browser launches under load, but
a long flow failing late costs a full rerun. The sibling idea
`faster-test-runs-10-rerun-only-failures-in-a-batch` is related.

### 4. Other earlier specs that touch the same ground

- `spec_dd/3. done/2026-04-28_07:25_testing-best-practice/` (research_tooling.md, spec, plan):
  rewrote the `playwright-tests` skill. The `authed_storage_state` / `authed_page` reference pattern
  and the "live_server scope" caveat come from here.
- `spec_dd/3. done/2026-05-02_18:13_testing-best-practice-phase-3-cleanup-flaky-and-redundant-tests/`:
  earlier redundant-test pruning, not Playwright-specific. Not read in full.
- `spec_dd/3. done/2026-03-10_21:13_mobile-responsiveness-audit/` is the origin of the viewport
  checks (375px and 360px, sidebar collapsed under 1024px, no horizontal overflow). The mobile files
  under `freedom_ls/*/tests/playwright/` (for example `test_cohort_detail_mobile.py`,
  `test_mobile_navigation_flow.py`, `test_touch_targets.py`, `test_admin_changelist_mobile.py` in
  `mail` and `messaging_policy`) trace to it. Which of these genuinely need a layout engine (real
  `getBoundingClientRect`, overflow, `matchMedia`) was not audited before. The spec's "no audit
  exists yet" is accurate.
- `spec_dd/1. next/faster-test-runs-6-prune-slow-tests/idea.md` leaves Playwright tests to this spec.

### 5. Nothing found

No earlier spec attempted merging same-page Playwright tests. No note records a trial of cookie
injection. No audit of the 220 tests exists.

## Elsewhere

Most sources are blog posts, not controlled studies. Numbers are the authors' own.

- Django plus Playwright: a pattern of `Client.force_login(user)`, then copying the session cookie
  into the browser context with `add_cookies` for the live-server host, is described. See
  <https://www.djangotricks.com/tricks/m9psJW4YSoMf/> (reading Django sessions in Playwright tests)
  and, for Selenium, <https://www.djangotricks.com/tricks/3bNUzYpfpCRR> (visit a non-auth page first
  so the cookie can be set for the right domain). I found no source that addresses
  `transaction=True` flush plus cookie reuse. That combination is unverified by the web.
- Playwright's own auth guidance (reuse saved state per worker or per project; use API requests to
  authenticate): <https://playwright.dev/python/docs/auth>. It assumes the server-side user survives
  between tests, which is the assumption this repo's flush breaks.
- Team that halved a Playwright suite: switched setup to API calls (setup went from roughly 25 to
  30s to about 3s), kept dedicated tests for the login flow, deleted about a dozen low-value tests,
  replaced one 30s E2E test with a 1.2s unit suite, and replaced fixed `waitForTimeout` calls with UI
  signals. CI went from frequently flaky to stable. Trade-off they name: a test using API setup can
  pass while the UI login is broken, so login keeps its own tests (this matches the settled item
  here). <https://dev.to/kate_astrid/how-we-halved-our-playwright-e2e-suite-mg6>
- "12x faster E2E tests": authenticate through the request API (shares cookies with the browser
  context). They kept some tests sequential because tests depended on earlier uploads, a warning
  for merging: shared state creates ordering coupling.
  <https://dev.to/alexneamtu/how-we-made-our-e2e-tests-12x-faster-51pm>
- GitLab issue proposing an API login mechanism for E2E tests, with UI login kept only for the login
  features: <https://gitlab.com/gitlab-org/gitlab/issues/27271>. GitLab's E2E best practices also
  push logic to lower test levels: <https://squid.nt.tuwien.ac.at/gitlab/help/development/testing_guide/end_to_end/best_practices.md>
- Programmatic login write-ups: UI login is a flakiness source because anything that breaks the
  login page breaks every test behind it (one audit claims 38% of runtime on the login page).
  Vendor content, with an unverified "40 to 60%" figure.
  <https://momentic.ai/resources/mastering-e2e-tests-a-deep-dive-into-programmatic-login-testing>
- Test data left over by earlier tests causes flakiness, so each test should clean up what it
  creates (relevant to merged flows that create more data per test).
  <https://dev.to/bugslayer/building-a-comprehensive-e2e-test-suite-with-playwright-lessons-from-100-test-cases-171k>
- Slowest UI-heavy tests moved to nightly or pre-deploy runs rather than every commit:
  <https://levelup.gitconnected.com/3-rules-for-turbo-charged-e2e-tests-7d93fd3210a1> (a possible
  but different lever; not in this spec's settled scope).

### What went wrong elsewhere (recurring)

1. API or cookie login hides a broken login page: fix is dedicated login tests (already settled).
2. Merged tests couple through shared state and ordering, and one failure hides the rest: fixed
   here by the answers (plain sequential expects, stop at first failure).
3. Lost coverage when pruning without a record: fixed here by the audit "goes" rows approved in the
   spec review.
4. Fixed sleeps and `networkidle` waits cause flakiness and survive refactors. Phase 4 already removed
   `networkidle` calls in `test_course_toc.py`.
5. Viewport checks in a browser are costly: the cheaper pattern is to resize one page
   (`page.set_viewport_size`) in one test, which the answers already chose.

## Gaps and options for the spec to weigh (inference, not prior art)

- A session-scoped `storage_state` is dead on arrival with `transaction=True` (documented). Two
  untried routes to evaluate: (a) per-test: after the user and `EmailAddress` exist, create a
  Django session through the session engine (or `Client.force_login`) and call
  `context.add_cookies(...)` for the live-server host, skipping the form and the password
  verification; (b) per-test `request` login via Playwright's API context. Route (a) needs the site
  and cookie domain to match `live_server_site`, and the session must be written to the real DB (the
  live server is a separate connection thread, which is the reason for `transaction=True`).
- The fixture file's own comment lists three places that sign in through the form (the
  `logged_in_page` fixture and two educator fixtures). The spec should list all callers, not only
  `logged_in_page`.
- Real login speed is hidden by Argon2. The timing research shows hashing is a large share of
  per-test cost. Cookie injection also skips the verify hash, which is why it may save more than
  the form-fill time alone.

status: ok
