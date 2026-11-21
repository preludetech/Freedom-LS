# Research: best practices for faster Playwright tests

Topic `best_practices`, spec "Fewer, faster Playwright tests". Sources are cited by number. Where a point comes from general knowledge and not a fetched page, it is marked "(experience)".

## 1. Programmatic authentication

**Established practice.** The Playwright Python auth docs [1] recommend authenticating once and reusing state through `browser_context.storage_state()` and `browser.new_context(storage_state=...)`. They say repeating the UI login in every test "can slow down test execution". The state holds cookies, local storage and optionally IndexedDB. Session storage is not persisted. The docs warn against committing the state file because it holds live session cookies.

**Django specifics.** The usual Django route skips the form and the saved file. You create a session on the server side, then give the browser the cookie:

1. Make the user, then call `client.force_login(user)` on a Django test client, or build a `SessionStore` yourself and save it. Both create a `django_session` row.
2. Read the session key (`client.cookies[settings.SESSION_COOKIE_NAME].value`) [2][3].
3. Call `context.add_cookies([{name: settings.SESSION_COOKIE_NAME, value: key, domain: <live_server host>, path: "/"}])`. You can also pass `url=live_server.url` and let Playwright derive domain and path.
4. Navigate straight to the protected page.

The cookie-injection route has two traps [2]:
- The cookie domain must match the host the live server uses (`localhost` against `127.0.0.1`). A mismatch looks like "not logged in".
- If the session row is missing, the server answers with an emptied session cookie.

**Interaction with `transaction=True` and a per-test flush.** The `playwright_fixtures.py` docstring is right that a session-scoped `storage_state` saved from one login dies at the first flush. The flush removes the user row and the `django_session` row. That argues against a shared file. It does not argue against per-test injection. The options, from cheapest to most involved:

- **A. Per-test `force_login` plus `add_cookies` (recommended shape).** Do it inside the function-scoped fixture. The user and session are created inside the test's own transaction=True database state, so the flush at the end cleans them up and nothing is stale. The cost is one ORM insert for the session plus one `add_cookies` call, in place of loading the login page, filling two fields and a POST/redirect round trip. Because the live server shares the same database in `transaction=True` mode, the session row is visible to it. (experience)
- **B. Request-based login.** Post to the login endpoint with `context.request` (APIRequestContext) so the cookie lands in the context without rendering a page. It is still a real login path, but it needs a CSRF token fetch and costs more than A. (experience)
- **C. Session-scoped `storage_state` plus re-creating the user and session per test with the same key.** You can pre-compute a fixed session key, and in each test recreate the user and a `Session` row with that key and `session_data` from `force_login`. This is more fragile than A. It is not worth it unless `add_cookies` shows up in profiles. (experience)
- **D. Drop `transaction=True` for tests that allow it.** Not practical here: the browser uses another DB connection, so it cannot see uncommitted data from a plain `django_db` test.

**Things to check on this repo.** allauth's email-verified requirement does not apply to `force_login` (it bypasses the auth backend), but the user still needs a verified `EmailAddress` if any view or middleware checks it. The site-aware session model and `SESSION_COOKIE_DOMAIN` must match the live server host. `live_server_site` already aligns the `Site` domain with `live_server.url`.

**Keep the form tested.** The common rule is to keep one UI login test (or a few) for the login feature and use the programmatic path elsewhere [1]. This matches the settled rule in idea.md.

## 2. Grouping assertions into flows versus one assertion per test

- Unit-test guidance (one assertion per test) exists to give precise failure messages. For E2E the cost model is different: each test pays for a browser context, a page load, data setup and a DB flush. The widely used E2E guidance is therefore to write tests around a user journey or scenario, with several `expect` calls, and to avoid splitting one page state into many tests [4]. (experience for the generalisation; the Playwright best-practice page itself could not be fetched, 404.)
- Playwright's own guidance asks for isolated tests that do not depend on each other [4]. A merged flow does not break that rule, because the flow is one test with its own state. What breaks it is flow tests that depend on an earlier test's leftovers.
- Merge when the tests share the same page, same data and same starting state, and differ only in what they read. Keep separate when they mutate state in conflicting ways, when a failure needs its own name for triage, or when the setup differs.
- The owner chose plain sequential `expect` calls that stop at the first failure (answers.md). That is the conventional default. Soft assertions (`expect.soft`) are a JS Playwright feature that has no Python equivalent in pytest-playwright anyway. Keep a short comment or a step label (a `# step:` comment, or a message in a helper) before each check so the failure line says which behaviour broke.
- Auto-waiting web-first assertions (`expect(locator).to_be_visible()`) should stay. Do not replace them with `time.sleep` or instant-read assertions when merging.

## 3. Viewport testing patterns

- Playwright supports changing the viewport mid-test with `page.set_viewport_size({...})`, and it re-lays out the page without a reload [5]. The decided shape (answers.md) is one test that loads once and loops over viewports. That matches the common "resize in one test" pattern.
- The alternative, `@pytest.mark.parametrize` over viewports, is clearer in reports and each case fails independently, but each case pays the full setup again. This is the exact cost the spec removes. Parametrising only makes sense when the viewport needs to be set before first load, for example when the page picks the layout in JS at load time or serves different markup per user agent / `is_mobile` / touch settings. For purely CSS (media query) layouts a resize works. For a page with JS that reads `window.innerWidth` only on load, reload after resizing, which is cheaper than a new context.
- When looping, put the viewport in the failure message, for example `expect(locator, "at 375x667")` or a loop over a list of named tuples, so a failure names the viewport. Reset the viewport at the end if later steps share the page.
- Keep the viewport list small. Typical sets are one phone, one tablet and one desktop width, taken from the breakpoints in Tailwind config rather than arbitrary sizes. (experience)

## 4. Moving layout checks out of the browser

(All experience unless cited. The decision on what moves is the audit's job.)

- Checks that only assert that a Tailwind class is in the markup (`hidden md:block`, `grid-cols-2`) do not need a browser. A Django test client response plus a parsed-HTML assertion (`assertContains`, BeautifulSoup/selectolax) or a Cotton component render test covers them in milliseconds. These tests do not prove the CSS works, only that the class is emitted.
- Checks that assert real rendering (an element is visible at a width, no horizontal overflow, text not clipped, sticky nav stays on screen) need a layout engine. Those stay in the browser, merged into the one resize loop from section 3.
- Content checks (this heading exists, this link has this href, this empty-state text shows) are not layout checks. A client-level render test covers them. A browser test is only needed when HTMX or JS changes the DOM.
- A middle route is a computed-style check (`to_have_css`) in the browser. It is still a browser test, so only use it where the class alone would not prove the result.
- Visual snapshot comparison (`toHaveScreenshot` in JS Playwright) is not part of the Python pytest-playwright core in the same way and adds flakiness. It is not a speed fix.

## 5. pytest-xdist with live_server

- pytest-django's `live_server` binds to a free port per process, and with xdist each worker is a separate process with its own `live_server`, so workers do not collide on ports. Each worker needs its own database: pytest-django appends the worker id (`test_<db>_gw0`) to the test database name when xdist is active [6]. The `transaction=True` flush is therefore per worker database and does not disturb other workers.
- pytest-playwright is documented as compatible with `pytest-xdist` (`-n auto`), with one browser per worker [7]. Each worker still pays browser start-up once (session-scoped `browser`), while each test gets a new context (cheap, tens of ms).
- Per-worker memory is the limit: each worker holds Chromium plus a Django live server thread. Set `-n` to the core count minus a margin and measure. More workers than cores adds nothing for CPU-bound page rendering.
- Other speed levers in pytest-playwright: reuse the session `browser` (the default), run headless, disable video and tracing unless a test fails (`--tracing retain-on-failure`, `--video retain-on-failure` or off) [7], and block or stub third-party requests (fonts, analytics) with `page.route` so page load does not wait on the network. (experience)
- Static files: serve built Tailwind output rather than rebuilding per test. Check that `live_server` uses `StaticLiveServerTestCase` behaviour (pytest-django's `live_server` serves static files via `staticfiles` when `DEBUG`/`runserver` handler applies) [6].

## 6. Measuring E2E suite timing

- `pytest --durations=0` (or `--durations=30`) lists the slowest setup, call and teardown phases per test [8]. Set `--durations-min=0.5` to cut noise. Setup and teardown phases show the login-fixture and flush costs separately from the test body.
- Compare like with like: same worker count, same machine, cold versus warm browser caches. Run each variant several times and use the median, since E2E timing is noisy. Record wall-clock time and the sum of per-test times (CPU time), because xdist hides the second behind the first.
- Use `pytest -p no:randomly` or a fixed seed when comparing, so ordering effects do not skew the numbers. (experience)
- Playwright traces (`--tracing on`) show where a single test spends time (navigation, waits), useful for a handful of representative tests, not for the whole suite [7].
- Take the "before" number once, up front, with the audit, and record it with the command used. The repo's `research_test_timings.md` already holds the baseline of 220 tests at roughly 7s each.
- Expected saving for the login change (experience, to check): form login costs about one page load plus a POST, plausibly 0.5 to 1.5 s a test. Over 220 tests, that is roughly 2 to 5 CPU minutes, in line with the 2 to 3 minutes of wall time in idea.md. Measure it, do not trust this.

## 7. Suggested rules for the skills update

1. A signed-in test uses a fixture that creates the user and session on the server and injects the session cookie. Only tests of the sign-in feature drive the form.
2. One test per page state or journey, not per assertion. Share the data and the page load.
3. Check several viewports in one test by resizing, with the viewport named in the failure message.
4. Anything provable from rendered HTML or a Cotton component render belongs in a non-browser test.
5. Fail at the first failed `expect`. No sleeps. Keep auto-waiting assertions.
6. Measure with `--durations` before and after, with the command recorded.

## References

1. Playwright Python, Authentication: https://playwright.dev/python/docs/auth
2. Django Tricks, reading Django session in Playwright tests: https://www.djangotricks.com/tricks/m9psJW4YSoMf/
3. Django Tricks, logging in the user in Selenium tests (force_login cookie injection): https://www.djangotricks.com/tricks/3bNUzYpfpCRR
4. Playwright best practices (page could not be fetched, 404; cited from the known guidance on isolation): https://playwright.dev/docs/best-practices
5. Playwright Python, Page.set_viewport_size: https://playwright.dev/python/docs/api/class-page#page-set-viewport-size
6. pytest-django, live_server and xdist database naming: https://pytest-django.readthedocs.io/en/latest/helpers.html#live-server and https://pytest-django.readthedocs.io/en/latest/usage.html#running-tests-in-parallel-with-pytest-xdist
7. Playwright Python, pytest plugin (xdist, tracing, video options): https://playwright.dev/python/docs/test-runners
8. pytest, profiling test duration: https://docs.pytest.org/en/stable/how-to/usage.html#profiling-test-execution-duration

Note: only references 1 to 3 were fetched or surfaced in search during this run. References 4 to 8 are standard documentation URLs cited from general knowledge and were not opened; check them before quoting.

status: ok
