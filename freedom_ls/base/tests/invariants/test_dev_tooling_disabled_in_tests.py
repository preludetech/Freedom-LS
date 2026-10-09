"""``django_browser_reload`` must stay out of the test run's middleware stack.

Its ``/__reload__/events/`` view is an infinite ``StreamingHttpResponse``
generator (a server-sent-events ping loop) that never returns, so the request
that opens it never fires ``request_finished`` and its database connection is
never closed. ``BrowserReloadMiddleware`` is what gets a real browser to open
that connection at all -- it injects the reconnecting client-side script into
every HTML response. A Playwright test's browser does exactly that on every
page it visits, leaving one of these connections open until the browser
disconnects, which can outlast the pytest session's own database teardown and
make ``DROP DATABASE`` fail with "being accessed by other users".

``config.settings_dev`` already keeps the same kind of dev-only tooling
(``debug_toolbar``) out of ``INSTALLED_APPS``/``MIDDLEWARE`` during
``TESTING``; ``django_browser_reload`` needs the same treatment.
"""

from __future__ import annotations

from django.conf import settings


def test_browser_reload_app_not_installed_during_testing() -> None:
    assert "django_browser_reload" not in settings.INSTALLED_APPS


def test_browser_reload_middleware_not_active_during_testing() -> None:
    assert "django_browser_reload.middleware.BrowserReloadMiddleware" not in (
        settings.MIDDLEWARE
    )
