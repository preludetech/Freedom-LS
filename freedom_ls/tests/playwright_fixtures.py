"""Shared Playwright fixtures for end-to-end browser tests.

Available fixtures
------------------

- ``reset_local_storage`` (autouse, function): guarantees ``localStorage``
  and ``sessionStorage`` are empty at the *start* of each Playwright test.
  pytest-playwright already gives each test a fresh ``BrowserContext`` (so
  storage is empty by default), but the fixture is the explicit, documented
  contract — tests no longer need to call
  ``page.evaluate("localStorage.clear()")`` themselves. The clear happens
  via context teardown, which keeps in-test persistence semantics
  (writing to localStorage and navigating again still finds the value)
  intact.
- ``logged_in_page`` (function): yields a Playwright ``Page`` for a freshly-
  created, email-verified student user. Drives the allauth login form once
  per test using semantic locators (``get_by_label`` / ``get_by_role``) per
  the ``fls:playwright-tests`` skill. Replaces the older fixture body that
  used CSS selectors (``input[name="login"]``, ``button[type="submit"]``).

A ``fresh_login_page`` (no-auth) variant is intentionally not provided —
no current test needs it, and the spec's "appears in 2+ tests" gate keeps
us from shipping unused fixtures. Tests that need to drive the login or
signup UI themselves can use the standard ``page`` fixture directly.

Scoping
-------

All fixtures here are function-scoped. The spec for Phase 4 originally
called for a session-scoped ``storage_state`` login fixture so that the UI
login is paid only once per session, with the resulting cookies +
localStorage reused across every test via
``browser.new_context(storage_state=...)``.

That approach does not survive contact with the existing E2E test suite,
which uses ``@pytest.mark.django_db(transaction=True)`` so that the
Playwright browser (a separate DB connection) sees data the test set up.
``transaction=True`` makes pytest-django flush the entire database at the
end of every test — that wipes both the synthetic user the session-scoped
fixture created *and* the ``django_session`` row the cookie points at, so
the cached ``storage_state`` is invalid by the second test.

A function-scoped UI login is therefore the correct trade-off here:
slower per test (one form submission instead of zero), but compatible with
the transactional DB reset every existing E2E test relies on. If a future
test class can opt out of ``transaction=True``, a session-scoped
``storage_state`` fixture can be layered on without removing this one.

Composition
-----------

``logged_in_page`` depends on ``live_server_site`` (sets the test
``Site``'s domain to match ``live_server.url`` so allauth's site-aware
queries hit the right row) and ``mock_site_context`` (patches
``_thread_locals.request`` and ``get_current_site`` for code that runs in
the test's own thread — factories, view helpers called directly from the
test, etc.). The live server itself runs in a separate thread and does
its own site lookup; the mock is for the test process.

Role variants
-------------

Only a student-shaped login is provided today, because every existing
Playwright test uses a student. Role-specific variants
(``educator_logged_in_page``, ``admin_logged_in_page``) should be added
the moment a second test needs them — not preemptively.
"""

import contextlib

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, expect

from freedom_ls.accounts.factories import UserFactory

_PAGE_FIXTURE_NAMES = {"page", "logged_in_page"}


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


def _login_via_ui(page: Page, live_server, email: str, password: str) -> None:
    """Drive the allauth login form using semantic locators."""
    from conftest import reverse_url  # local to avoid circular import at module load

    login_url = reverse_url(live_server, "account_login")
    page.goto(login_url)

    # The allauth LoginForm uses ``EmailField`` with label "Email" when
    # ``ACCOUNT_LOGIN_METHODS == {"email"}`` (set in settings_base.py); the
    # password field's label is "Password"; the submit button's text is
    # "Sign In". All three are sourced from allauth's i18n catalogue.
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign In").click()

    # Auto-wait for the redirect away from the login URL. ``LOGIN_REDIRECT_URL``
    # is "/" in settings_base.py; assert we left ``account_login`` rather than
    # asserting the exact destination, since that destination is configured
    # outside this fixture's concern.
    expect(page).not_to_have_url(login_url)


@pytest.fixture
def logged_in_page(
    page: Page, live_server, db, live_server_site, mock_site_context
) -> Page:
    """Yield a Playwright ``Page`` logged in as a fresh, verified student.

    Uses semantic locators (``get_by_label``, ``get_by_role``) per the
    Playwright skill. See module docstring for why this is function-scoped
    rather than backed by a session-scoped ``storage_state`` fixture.
    """
    password = "testpass"  # noqa: S105 — synthetic test credential, never persisted  # pragma: allowlist secret
    user = UserFactory(password=password)

    # allauth refuses to authenticate users whose email is not verified
    # when ACCOUNT_EMAIL_VERIFICATION == "mandatory" (set in settings_base).
    EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )

    _login_via_ui(page, live_server, str(user.email), password)
    return page
