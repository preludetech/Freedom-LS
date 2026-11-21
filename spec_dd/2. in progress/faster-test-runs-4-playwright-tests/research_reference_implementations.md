# Research: reference implementations (sign in without the form)

Question: how do open-source Django projects and pytest plugins sign a user into a Playwright browser without the login form, and how do they structure fast E2E suites?

Caveat up front: web search found no polished open-source repo with a `force_login` plus `add_cookies` Playwright fixture. What exists is Selenium-era recipes and blog posts, which translate directly. The sketches marked "adapted" are inferred, not copied from a tested source.

## 1. The standard technique: create the session server-side, hand the cookie to the browser

Source: Django Tricks, "About Logging In the User in Selenium Tests" <https://www.djangotricks.com/tricks/3bNUzYpfpCRR>

```python
self.client.login(email="user@example.com", password=<synthetic password>)
# the driver must first load a page on the domain so the cookie can attach
self.browser.get(f"{self.live_server_url}/404/")
self.browser.add_cookie({
    "name": settings.SESSION_COOKIE_NAME,
    "value": self.client.session.session_key,
    "path": "/",
    "domain": settings.SESSION_COOKIE_DOMAIN,
})
self.browser.get(f"{self.live_server_url}/")
```

Selenium needs a prior page load on the domain. Playwright does not: `context.add_cookies` accepts a `url` and works before any navigation.

Adapted for pytest-playwright (not from a tested source):

```python
@pytest.fixture
def logged_in_page(page, live_server, logged_in_user, client):
    client.force_login(logged_in_user)  # no password hashing, no allauth verification checks
    page.context.add_cookies([{
        "name": settings.SESSION_COOKIE_NAME,
        "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
        "url": live_server.url,          # Playwright derives domain and path from this
    }])
    return page
```

Or without the test client, using the session store directly (same effect). The `SessionStore` import pattern comes from the Django Tricks Playwright post below:

```python
from importlib import import_module
SessionStore = import_module(settings.SESSION_ENGINE).SessionStore
s = SessionStore()
s[SESSION_KEY] = str(user.pk)
s[BACKEND_SESSION_KEY] = settings.AUTHENTICATION_BACKENDS[0]
s[HASH_SESSION_KEY] = user.get_session_auth_hash()
s.save()
cookie_value = s.session_key
```

`client.force_login` does exactly this, so prefer it. Django docs say it "is faster than `login()` since the expensive password hashing algorithms are bypassed" and "skips the authentication and verification steps" (<https://docs.djangoproject.com/en/stable/topics/testing/tools/>). That matters here: the current fixture creates `EmailAddress(verified=True)` only because allauth refuses an unverified login at the form. `force_login` skips that check. The row is still harmless to keep if any page reads email verification state.

Caveats from sources:
- A django-users thread (<https://www.mail-archive.com/django-users@googlegroups.com/msg211347.html>) describes a pytest `force_login` plus cookie-copy fixture against a channels live server where the server reset the cookie and reported a missing user. The likely cause is the live server not seeing the user row: the data was in an uncommitted transaction, or the session was written to a different DB or cache. This is the exact failure to check for in FLS. The user and session rows must be committed, which `transaction=True` guarantees. The session backend must also be one the live-server thread reads (DB sessions, not locmem across processes).
- The session hash covers the user's password hash (`get_session_auth_hash`), so changing the password after login invalidates the cookie.
- Site-aware sessions: if `SESSION_COOKIE_DOMAIN` is set, use `url` or a matching `domain`. Otherwise `url` is enough.

## 2. Playwright's own recommendation: storage_state

Source: <https://playwright.dev/python/docs/auth>

- Log in once (UI or API), save `context.storage_state(path="state.json")`, and create later contexts with `browser.new_context(storage_state=...)`. The docs recommend a setup step per worker, or per test with `browser_context_args` in pytest-playwright.
- This only works if the identity in the stored cookie survives. The FLS fixture docstring (`freedom_ls/tests/playwright_fixtures.py`) already records why it does not: `transaction=True` flushes the user and `django_session` rows after each test, so a session-scoped state is stale by test two.
- Ways around that (adapted):
  1. Per-test cookie injection as in section 1. This is a few ms and needs no cached state. It fits `transaction=True` because the user and session are created inside each test's own database state.
  2. Keep the user and session out of the flush. This is fragile and not recommended.
  3. Stable identifiers: mint the session key deterministically (for example `SessionStore(session_key=fixed_key)`), and recreate user and session rows each test with a fixed pk and key. Then one `storage_state` or cookie value is valid every test. This is mostly useful if cookie injection is done at context level through the `browser_context_args` fixture, so every `page` is already signed in.

## 3. Structuring the live server and context

- Django Tricks, "About Reading Django Session in Playwright Tests" <https://www.djangotricks.com/tricks/m9psJW4YSoMf/> uses `LiveServerTestCase`. `setUpClass` starts Playwright, launches Chromium and creates one `BrowserContext`. `setUp` opens a new page and `tearDown` closes it. It sets `DJANGO_ALLOW_ASYNC_UNSAFE=true`, and reads the `sessionid` cookie back from `context.cookies()` to inspect the session through `SessionStore`. Takeaway: one browser and context per class, a page per test, is the common speed structure. pytest-playwright's default is a fresh context per test, which is cheap anyway (the browser is session-scoped).
- Django docs: `LiveServerTestCase` "does basically the same as `TransactionTestCase`", so the live server thread sees committed data. It truncates all tables after each test (<https://docs.djangoproject.com/en/stable/topics/testing/tools/>). Every reference that uses a live server therefore accepts the flush, and recreates users per test.
- pytest-django's `live_server` fixture needs `transaction=True` semantics for the same reason, which is what FLS does today.
- Autonoma, "Django Playwright testing guide" <https://getautonoma.com/blog/django-playwright-testing-guide> and the mimir E2E notes <https://glama.ai/mcp/servers/@phainestai/mimir/blob/57b4bd723178bc90e03a81bc075cee148dbf5262/docs/architecture/PLAYWRIGHT_E2E_SOLUTION.md> propose an `authenticated_page` fixture that logs in through the form. That is the slow pattern FLS has now. I found no source that does better with a flushed DB other than cookie injection.
- `django-selenium-login` (<https://pypi.org/project/django-selenium-login/>) packages the same idea: a `force_login` helper that creates a session and sets the cookie on the driver. It confirms the cookie-injection approach is a known pattern.

## 4. Implications for the spec's open questions

1. How a signed-in session reaches the browser under `transaction=True`: create the user (already done by `logged_in_user`), then `client.force_login(user)` or a `SessionStore` save, then `page.context.add_cookies([{name, value, url: live_server.url}])`. The session row is created after the flush at the start of the test and flushed at the end, so there is no staleness. The cost is a single DB insert. No storage_state caching is needed, and it is not valid across tests anyway.
2. Keep the form login tests: allauth login, logout and signup tests should keep using the plain `page` fixture and the UI.
3. Verification: add a quick assertion that the first `goto` is not redirected to `account_login`. The channels thread shows the silent failure mode is a redirect or a reset cookie.
4. Role variants (educator, admin) become trivial, since the helper only needs a user. This removes the reason the docstring gave for deferring them.
5. For merged-flow and viewport tests, none of the references solve the "merge" question. Playwright's own API supports it: `page.set_viewport_size({...})` between checks in one test.

## URLs

- <https://www.djangotricks.com/tricks/3bNUzYpfpCRR>
- <https://www.djangotricks.com/tricks/m9psJW4YSoMf/>
- <https://docs.djangoproject.com/en/stable/topics/testing/tools/>
- <https://playwright.dev/python/docs/auth>
- <https://www.mail-archive.com/django-users@googlegroups.com/msg211347.html>
- <https://pypi.org/project/django-selenium-login/>
- <https://getautonoma.com/blog/django-playwright-testing-guide>
- <https://glama.ai/mcp/servers/@phainestai/mimir/blob/57b4bd723178bc90e03a81bc075cee148dbf5262/docs/architecture/PLAYWRIGHT_E2E_SOLUTION.md>

status: ok
