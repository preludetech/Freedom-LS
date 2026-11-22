# Research: known complaints (Playwright login, storage_state, merged flows, live_server)

Spec: "Fewer, faster Playwright tests". Each row gives the complaint, the fix, and how well it is sourced.
"Verified" means a page was fetched or a search result showed it. "Background" means standard Django or Playwright
behaviour that I did not find a dedicated source for, so check it in the spec's spike.

## 1. Programmatic login: the session cookie is not accepted

| Complaint | Fix | Source / confidence |
|---|---|---|
| The browser ignores or never sends the injected `sessionid`. Usual causes: the cookie has no `domain` or `url`, so `add_cookies` rejects it. The host differs (`localhost` vs `127.0.0.1`), so the cookie is not sent. `Secure` is set but the live server is plain http. `SameSite` blocks it. | Build the cookie with `name=settings.SESSION_COOKIE_NAME`, `value=session_key` and `url=live_server.url` (or the exact host), `path="/"`. Take the host from `live_server.url`, never hard-code it. Confirm the test settings have `SESSION_COOKIE_SECURE=False`. Playwright accepts `Secure` cookies on `http://localhost`, but not on other http hosts. | Background. Pattern shown for Selenium in the Django users thread (copy the test-client session cookie with `add_cookie`): <https://mid.mail-archive.com/django-users@googlegroups.com/msg211347.html> |
| Mixed hosts: the cookie is set for `127.0.0.1` but the page loads from `localhost`. | Visit and set the cookie on one host only. | Background. **FLS-specific:** site resolution is by Host header (agent memory notes say dev sites resolve by host, "127.0.0.1:8000"), so the host the cookie targets must also be the host the Site row matches. |
| `Client.login()` or `force_login` on a Django client gives a session that does not match what the real flow gives. `force_login` skips the login view, so allauth email-verification and axes checks are skipped. | That is the point for non-login tests. The sign-in form keeps its own tests (already settled in idea.md). `force_login` needs a backend: pass `backend=` if more than one is configured. `Client.login()` fails with django-axes (`AxesBackendRequestParameterRequired`). | Repo evidence: `.claude/agent-memory/sdd-qa-data-helper/reference_multiselect_quiz_scoring_command.md` and `reference_proving_allauth_login_works.md`. |
| Building the cookie by hand risks drift from what Django's session engine writes. | Create the session through the real engine: `client.force_login(user)`, then read `client.cookies[settings.SESSION_COOKIE_NAME].value`. Hand-built sessions break when `SESSION_ENGINE` changes (signed cookies, cache). | Background. |

## 2. Sessions flushed between tests (`transaction=True`)

| Complaint | Fix | Source / confidence |
|---|---|---|
| The session lives in the DB, so a transactional test's teardown flush deletes it. A `storage_state` file saved once per session then holds a dead `sessionid` for the next test. | Do not share one saved session across `transaction=True` tests. Either create the user and session inside each test's setup (one `force_login` is cheap, a few ms), or use a non-DB `SESSION_ENGINE` (signed cookies, cache, file) for the Playwright run, so the session survives a flush as long as the user row is recreated with the same pk. Recreate the user per test and inject a fresh cookie each time. | Flush cost and that `live_server` implies `transactional_db`: <https://pytest-django.readthedocs.io/en/stable/database.html>. Session-in-DB inference is background. |
| Reusing `storage_state` hides a user pk or password mismatch: the state is valid but the user row no longer exists, so the first page redirects to login. The error looks like a flaky login. | Assert the signed-in marker early in the fixture (for example the logout link) so a bad cookie fails loudly in setup, not three steps into the test. | Background. |
| Playwright's own guidance assumes a long-lived server-side user: log in once, save `playwright/.auth/user.json`, reuse. | That fits a persistent test DB. It does not fit flush-per-test. The doc also says not to commit the state file because it holds sensitive cookies, and that session storage is not covered by `storage_state`. | Verified: <https://playwright.dev/python/docs/auth> |
| Data disappears after a `live_server` test: later non-browser DB tests fail. pytest-django issue 1062 reports other tests failing after `live_server` was added, and a Django forum thread says tests that run after `live_server` (for example ones that `force_login` a DB user) fail. | Order browser tests last (`pytest_collection_modifyitems`), or run them as a separate invocation. Keep `transaction=True` data created inside the test, never in session-scoped fixtures. | Verified (search results): <https://www.github.com/pytest-dev/pytest-django/issues/1062>, <https://forum.djangoproject.com/t/pytest-test-order-effects/13891>, <https://timonweb.com/django/optimizing-test-execution-running-live_server-tests-last-with-pytest/> |
| Flush is slow when there are many tables (the test DB flushes every table after every test). | `available_apps`/`serialized_rollback` do not help on the pytest side. Per-test cost is flush plus setup, so fewer, longer tests save flushes as well as logins. This supports merging. | Background; the pytest-django docs say transactional tests are "much slower to set up due to the required flushing". <https://pytest-django.readthedocs.io/en/stable/database.html> |
| SQLite in-memory test DB breaks with `live_server` after a transactional test. | Not relevant to FLS (PostgreSQL 17), so ignore. | <https://scriptagc.wasmer.app/https_github_com/pytest-dev/pytest-django/issues/1197> (verified in search results). |

## 3. Async-unsafe errors (`SynchronousOnlyOperation`, `DJANGO_ALLOW_ASYNC_UNSAFE`)

| Complaint | Fix | Source / confidence |
|---|---|---|
| Playwright's sync API runs an asyncio loop in the thread. Django ORM calls from the test body (create user, `force_login`, queries) then raise `SynchronousOnlyOperation: You cannot call this from an async context`. Often it shows at fixture teardown, after the test already passed. | The common workaround is `DJANGO_ALLOW_ASYNC_UNSAFE=true` in the E2E conftest or env. Django warns about data loss or corruption with concurrent access to the async-unsafe parts. In a single-threaded test that touches the ORM only between Playwright calls, the risk is low. The safer alternative is to put ORM calls in a sync function and call it via `asgiref.sync.sync_to_async`. That is awkward in a sync test. | Verified: <https://docs.djangoproject.com/en/stable/topics/async/>, community README <https://glama.ai/mcp/servers/@phainestai/mimir/blob/57b4bd723178bc90e03a81bc075cee148dbf5262/tests/e2e/README.md> |
| pytest-asyncio or anyio plugins make this worse (teardown errors although the tests pass). | Use only the sync API and sync tests. Do not install `pytest-playwright-asyncio` alongside `pytest-playwright`: they are incompatible and cause hangs. | Verified: <https://www.github.com/microsoft/playwright-pytest/issues/187> |
| Order of fixtures: ORM fixtures that run inside the page context's loop. | Create DB rows in fixtures that run before `page` is requested, or set the env var at conftest import. | Background. **Check first:** does the repo already set the variable? A grep of `*.py`, `*.toml` and `*.md` for `ALLOW_ASYNC` found no hit, so how `playwright_fixtures.py` avoids the error today needs reading before the spec decides. |

## 4. Live server thread and DB connections

| Complaint | Fix | Source / confidence |
|---|---|---|
| The `live_server` thread uses its own connection. With a plain `django_db` (transaction-wrapped) test the server cannot see rows created in the test. | This is why every browser test is `transaction=True`. It is a requirement, not a mistake. | Verified: <https://pytest-django.readthedocs.io/en/stable/helpers.html> and the database docs above. |
| Leaked connections: "database is being accessed by other users" when the test DB is dropped, because the live server thread kept a connection open. Hangs at the end of the run. | pytest-django closes connections on server shutdown. Do not start extra threads that open connections. Teardown hangs on the playwright fixture are known and unresolved in the issue linked above (open, label `p3-collecting-feedback`). | Verified (issue 187 above). |
| Parallel workers: each xdist worker needs its own live server port and its own DB. | pytest-django gives per-worker DB names under xdist. `live_server` uses port 0 (random), which is fine. Do not hard-code a port. | Background. Relevant to the roadmap spec on running tests in parallel. |
| Static files not served, or a slow first request. | Use `live_server` with `STORAGES` set to a plain static backend in test settings. | Background. |

## 5. Merging E2E tests into longer flows

| Complaint | Fix | Source / confidence |
|---|---|---|
| A long test hides failures: the first failure stops the test, so later checks never run and you fix one failure per run. | Settled in answers.md: stop at the first failure, plain sequential expects. Compensate with clear step names: `with` blocks or comments, and `expect(..., "message")` so the failing step is obvious from the traceback. Merge only tests that share the same page and data, so each merged check would have needed the same setup anyway. | Background; matches answers.md. |
| State leakage between steps in a flow: an earlier step changes data (marks complete, submits) and breaks a later check. | Order the steps so read-only checks come first, then mutations. Keep one flow per distinct data state. Do not merge tests that mutate the same row. | Background. |
| Loss of isolation makes failures hard to debug. | Keep Playwright traces on failure (`--tracing retain-on-failure`) and screenshots. Name the flow after the page, not after the number of checks. | Background. |
| Timeouts: one test with many steps hits the per-test timeout and the default 30s action timeout. | Raise the per-test timeout only on merged tests, not globally. Do not add `sleep`s. | Background. |
| Flakiness: merged flows have more chances to hit race conditions (HTMX swaps). | Use web-first assertions (`expect(locator).to_be_visible()`) and `wait_for_response` or locator expectations after HTMX actions. Avoid `networkidle` and fixed waits. | Background. |

## 6. Viewport testing

| Complaint | Fix | Source / confidence |
|---|---|---|
| One test per viewport repeats login, data setup and page load, and each launches its own context. | Settled in answers.md: load once, then `page.set_viewport_size(...)` for each viewport and assert in turn. Resizing triggers media-query and `resize` handlers, but not JS that read the size at load only (for example code run once on `DOMContentLoaded`). Where a check depends on load-time JS, reload after resizing. | Background; answers.md. |
| Tailwind breakpoint tests check computed CSS only, which is slow in a browser. | Open question for the spec ("which layout checks can move out of the browser"): class-presence checks can be done against rendered HTML in a Django test (`response.content`), since Tailwind breakpoints are class names. Real layout (overflow, hidden elements, tap targets) needs a browser. | Background. Spec must decide with the audit. |
| Device emulation (`browser.new_context(**playwright.devices[...])`) sets user-agent, touch and device-scale-factor, which a plain resize does not. | Use `set_viewport_size` for width-only breakpoint checks. Use a new context only where touch or mobile UA matters. | Background. |

## 7. Other recurring complaints

- Hanging on teardown with `playwright` and `live_server` together: issue 187 above, no confirmed root cause. Workarounds: remove conflicting plugins, check `tracing.stop()`.
- Third-party guides default to logging in through the UI form in an authenticated-page fixture (<https://getautonoma.com/blog/django-playwright-testing-guide>), which is the slow pattern this spec removes. Treat such guides as showing the common baseline, not best practice for speed.
- Committing `storage_state` files leaks sessions: already noted in `claude_plugins/django-stack/resources/playwright-testing.md` line 138.

## Gaps

- No dedicated Stack Overflow thread was retrieved. The rows marked "Background" rest on standard Django and Playwright behaviour and need a short spike (one test with an injected cookie under `transaction=True`) to confirm them.
- I did not read `freedom_ls/tests/playwright_fixtures.py`. Its docstring explains the current login trade-off and should be read next.

## Sources

- <https://playwright.dev/python/docs/auth>
- <https://www.github.com/microsoft/playwright-pytest/issues/187>
- <https://www.github.com/pytest-dev/pytest-django/issues/1062>
- <https://scriptagc.wasmer.app/https_github_com/pytest-dev/pytest-django/issues/1197>
- <https://forum.djangoproject.com/t/pytest-test-order-effects/13891>
- <https://timonweb.com/django/optimizing-test-execution-running-live_server-tests-last-with-pytest/>
- <https://pytest-django.readthedocs.io/en/stable/database.html>
- <https://pytest-django.readthedocs.io/en/stable/helpers.html>
- <https://docs.djangoproject.com/en/stable/topics/async/>
- <https://glama.ai/mcp/servers/@phainestai/mimir/blob/57b4bd723178bc90e03a81bc075cee148dbf5262/tests/e2e/README.md>
- <https://mid.mail-archive.com/django-users@googlegroups.com/msg211347.html>
- <https://getautonoma.com/blog/django-playwright-testing-guide>

status: ok
