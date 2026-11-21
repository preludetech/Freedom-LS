"""Shared Playwright fixtures for end-to-end browser tests.

Available fixtures
------------------

- ``reset_local_storage`` (autouse, function): guarantees ``localStorage``
  and ``sessionStorage`` are empty at the *start* of each Playwright test.
  pytest-playwright already gives each test a fresh ``BrowserContext`` (so
  storage is empty by default), but the fixture is the explicit, documented
  contract: tests no longer need to call
  ``page.evaluate("localStorage.clear()")`` themselves. The clear happens
  via context teardown, which keeps in-test persistence semantics
  (writing to localStorage and navigating again still finds the value)
  intact.
- ``logged_in_page`` (function): yields a Playwright ``Page`` signed in as
  ``logged_in_user``, a freshly created, email-verified learner. It calls
  ``sign_in``, so the browser holds a session without the login form.

``sign_in(page, live_server, user)`` gives a page's browser context a session
for ``user``. It builds the session with the Django test client's
``force_login`` and adds the session cookie to the context. It does not
navigate. The educator fixtures in ``educator_interface`` and any test that
needs a second user or a fresh context use it too.

``_login_via_ui`` drives the allauth login form. It is for a test whose
subject is signing in; every other test signs in with ``sign_in``.

Why the session is made per test
--------------------------------

Browser tests use ``@pytest.mark.django_db(transaction=True)`` so that the
Playwright browser (a separate DB connection) sees data the test set up.
``transaction=True`` makes pytest-django flush the entire database at the end
of every test, which deletes the user and the ``django_session`` row a cookie
points at. A ``storage_state`` saved once is therefore dead by the second
test, so each test builds its session after its user exists.

Composition
-----------

``logged_in_page`` depends on ``live_server_site`` (sets the test
``Site``'s domain to match ``live_server.url`` so site-aware queries hit the
right row) and ``mock_site_context`` (patches ``_thread_locals.request`` and
``get_current_site`` for code that runs in the test's own thread: factories,
view helpers called directly from the test, etc.). The live server itself
runs in a separate thread and does its own site lookup; the mock is for the
test process.
"""

import contextlib
from collections.abc import Iterator

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, Playwright, expect
from pytest_django.live_server_helper import LiveServer

from django.conf import settings
from django.db import connections
from django.test import Client

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User

_PAGE_FIXTURE_NAMES = {"page", "logged_in_page"}


def close_db_connections_before_playwright_stops() -> None:
    """Close this thread's DB connections while Playwright's event loop is current.

    Playwright's sync API leaves its loop marked as running on the main thread,
    so Django stores the thread's connections in contextvar storage rather than
    the thread-local one. Once Playwright stops and the loop is cleared, nothing
    can see those connections to close them, and the open session makes
    pytest-django's ``DROP DATABASE`` fail with "being accessed by other users".
    """
    connections.close_all()


@pytest.fixture(scope="session")
def playwright(playwright: Playwright) -> Iterator[Playwright]:
    """pytest-playwright's ``playwright``, closing DB connections before it stops."""
    yield playwright
    close_db_connections_before_playwright_stops()


@pytest.fixture(autouse=True)
def reset_local_storage(request: pytest.FixtureRequest) -> None:
    """Guarantee localStorage / sessionStorage are empty at test start.

    Autouse so per-test setup boilerplate (``page.evaluate("localStorage
    .clear()")``) can go away. pytest-playwright gives every test a fresh
    ``BrowserContext`` already, so storage is naturally empty when the
    browser first starts — but a test that does its own ``page.goto()``,
    sets a localStorage value, and then expects a *second* test to find
    clean storage was relying on context teardown for that. This fixture
    makes the contract explicit: storage is empty at the start of every
    test that uses a Playwright ``page``.

    Implementation note: we intentionally do **not** install
    ``page.add_init_script(...)``. An init-script clear runs on *every*
    navigation, which would break tests that legitimately persist a value
    across an in-test ``goto`` (e.g. localStorage-backed UI state). The
    clear happens once at fixture-setup time; any value the test itself
    writes after that survives subsequent in-test navigations.
    """
    if not _PAGE_FIXTURE_NAMES.intersection(request.fixturenames):
        # Most pytest tests don't touch Playwright at all; skip cleanly.
        return

    page: Page = request.getfixturevalue("page")
    # The fresh BrowserContext means localStorage is already empty when the
    # browser starts, but we have to navigate somewhere first to be able to
    # call evaluate(). Skipping the eager navigation here — the test's own
    # first ``page.goto(...)`` will land in an empty origin's storage by
    # construction. If pytest-playwright ever changes context scoping, the
    # ``with contextlib.suppress`` keeps us defensive without crashing.
    if page.is_closed():
        return
    with contextlib.suppress(PlaywrightError):
        # `localStorage` and `sessionStorage` are scoped per-origin and the
        # browser only has an `about:blank` origin until the test navigates,
        # so this evaluate is a no-op in practice. It exists so a future
        # change in pytest-playwright (e.g. shared contexts across tests)
        # doesn't silently start leaking storage between tests.
        page.evaluate("window.localStorage.clear(); window.sessionStorage.clear();")


def _login_via_ui(
    page: Page, live_server: LiveServer, email: str, password: str
) -> None:
    """Drive the allauth login form using semantic locators."""
    from conftest import reverse_url  # local to avoid circular import at module load

    login_url = reverse_url(live_server, "account_login")
    page.goto(login_url)

    # The allauth LoginForm uses ``EmailField`` with label "Email" when
    # ``ACCOUNT_LOGIN_METHODS == {"email"}`` (set in settings_base.py); the
    # password field's label is "Password"; the submit button's text is
    # "Log in", set by the project's own account/login.html override.
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Log in").click()

    # Auto-wait for the redirect away from the login URL. ``LOGIN_REDIRECT_URL``
    # is "/" in settings_base.py; assert we left ``account_login`` rather than
    # asserting the exact destination, since that destination is configured
    # outside this fixture's concern.
    expect(page).not_to_have_url(login_url)


def sign_in(page: Page, live_server: LiveServer, user: User) -> None:
    """Give ``page``'s browser context a session for ``user``, without the login form.

    The session is made in this test, after ``user`` exists, because ``transaction=True``
    flushes ``django_session`` after every test: a session saved once would be gone by the
    next test. ``force_login`` builds it through the session engine and fires
    ``user_logged_in`` as a real login does. Does not navigate.
    """
    client = Client()
    # Axes's backend is first in AUTHENTICATION_BACKENDS and cannot be named for a
    # session, so the session records the model backend.
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    # The cookie name differs per worktree (settings_dev), so read it from settings.
    cookie_name = settings.SESSION_COOKIE_NAME
    page.context.add_cookies(
        [
            {
                "name": cookie_name,
                "value": client.cookies[cookie_name].value,
                "url": live_server.url,
            }
        ]
    )


# Synthetic credential shared by the logged-in fixtures; never persisted.
_LOGGED_IN_PASSWORD = "testpass"  # noqa: S105  # pragma: allowlist secret


@pytest.fixture
def logged_in_user(db, live_server_site, mock_site_context) -> User:
    """A fresh, email-verified learner user — the one ``logged_in_page`` signs in.

    Exposed as its own fixture so a test can register this exact user for the
    course it browses. Content surfaces gate on registration
    (``decision.can_access_content``), so an E2E test that navigates to course
    item content must register *this* user, not an unrelated one.
    """
    user: User = UserFactory(password=_LOGGED_IN_PASSWORD)

    # A verified primary address, for pages that read it. ``sign_in`` skips the
    # login form, so allauth never checks this address itself.
    EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user


@pytest.fixture
def logged_in_page(page: Page, live_server: LiveServer, logged_in_user: User) -> Page:
    """Yield a Playwright ``Page`` signed in as ``logged_in_user``.

    The session is made with ``sign_in`` per test; see the module docstring for
    why a session saved once cannot be reused.
    """
    sign_in(page, live_server, logged_in_user)
    return page
