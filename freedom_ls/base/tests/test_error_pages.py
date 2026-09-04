"""Contract tests for the FLS error pages.

The five shell pages (404, 403, 400, 403 CSRF and 429) are driven through the
real machinery — the test client against a live URL, an actual
`PermissionDenied`/`BadRequest`, a real CSRF check, or allauth's own rate
limiter — rather than `render_to_string`, so a template that fails to load or
a handler that silently falls back to a bare string shows up here.

The two standalone pages (500, 503) are driven the way Django's own
`server_error` view drives `500.html`: `get_template(name).render()` with no
arguments at all, so no `RequestContext` is built and no context processor
runs. Neither needs `django_db` or `mock_site_context` — that is the whole
point of shipping them as standalone documents rather than `_base.html`
children.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest

import django
from django.core.cache import cache
from django.template.loader import get_template
from django.test import Client, override_settings
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory

if TYPE_CHECKING:
    # Stub-only: the test client's response carries `templates`, which a plain
    # HttpResponse does not.
    from django.test.client import _MonkeyPatchedWSGIResponse

ERROR_PAGES_URLCONF = "freedom_ls.base.tests.error_pages_urls"


def _post_signup(client: Client, email: str):
    return client.post(
        reverse("account_signup"),
        {
            "email": email,
            "password1": "Sup3rS3cretPass!",  # pragma: allowlist secret
            "password2": "Sup3rS3cretPass!",  # pragma: allowlist secret
            "first_name": "Rate",
            "last_name": "Test",
        },
    )


def _post_change_password(client: Client, old_password: str):
    return client.post(
        reverse("account_change_password"),
        {
            "oldpassword": old_password,
            "password1": "Sup3rS3cretPass!",  # pragma: allowlist secret
            "password2": "Sup3rS3cretPass!",  # pragma: allowlist secret
        },
    )


@pytest.mark.django_db
def test_404_renders_the_error_page(mock_site_context) -> None:
    response = Client().get("/no-such-page/")

    assert response.status_code == 404
    assert "404.html" in [template.name for template in response.templates]
    body = response.content.decode()
    assert "We cannot find that page" in body
    assert "/no-such-page/" not in body


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=ERROR_PAGES_URLCONF)
def test_403_renders_the_error_page(mock_site_context) -> None:
    response = Client().get(reverse("test_403"))

    assert response.status_code == 403
    assert "403.html" in [template.name for template in response.templates]
    assert "You do not have access to this page" in response.content.decode()


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=ERROR_PAGES_URLCONF)
def test_400_renders_the_error_page(mock_site_context) -> None:
    response = Client().get(reverse("test_400"))

    assert response.status_code == 400
    assert "400.html" in [template.name for template in response.templates]
    assert "We could not handle that request" in response.content.decode()


@pytest.mark.django_db
def test_csrf_failure_renders_the_error_page(mock_site_context) -> None:
    client = Client(enforce_csrf_checks=True)

    response = client.post(
        reverse("account_login"),
        {
            "login": "nobody@example.com",
            "password": "wrong-password",  # pragma: allowlist secret
        },
    )

    assert response.status_code == 403
    assert "403_csrf.html" in [template.name for template in response.templates]
    body = response.content.decode()
    assert "The form was not sent" in body
    assert "CSRF verification failed" not in body


@pytest.mark.django_db
def test_429_signed_out_renders_the_error_page(mock_site_context) -> None:
    cache.clear()
    client = Client()

    with override_settings(ACCOUNT_RATE_LIMITS={"signup": "1/m/ip"}):
        _post_signup(client, "throttle-r0@example.com")
        throttled = _post_signup(client, "throttle-r1@example.com")

    assert throttled.status_code == 429
    assert "429.html" in [template.name for template in throttled.templates]
    body = throttled.content.decode()
    assert "You have made too many attempts" in body
    assert "429 Too Many Requests" not in body


@pytest.mark.django_db
def test_429_signed_in_renders_the_error_page(mock_site_context) -> None:
    cache.clear()
    user = UserFactory()
    client = Client()
    client.force_login(user)

    with override_settings(
        ACCOUNT_RATE_LIMITS={"change_password": "1/m/user"}  # pragma: allowlist secret
    ):
        _post_change_password(client, user.email)
        throttled = _post_change_password(client, user.email)

    assert throttled.status_code == 429
    assert "429.html" in [template.name for template in throttled.templates]
    body = throttled.content.decode()
    assert "You have made too many attempts" in body
    assert "429 Too Many Requests" not in body


@pytest.mark.django_db
def test_403_secondary_action_signs_out_and_reaches_login(mock_site_context) -> None:
    """A bare `{% url 'account_login' %}` would bounce an authenticated
    visitor straight back to their own dashboard without ever showing a
    form — the secondary action must sign the visitor out first.
    """
    forward_url = f"{reverse('account_logout')}?next={reverse('account_login')}"
    dashboard_url = reverse("learner_interface:dashboard")

    user = UserFactory()
    authenticated_client = Client()
    authenticated_client.force_login(user)
    authenticated_response = authenticated_client.get(forward_url, follow=True)

    assert authenticated_response.request["PATH_INFO"] != dashboard_url

    anonymous_response = Client().get(forward_url, follow=True)

    assert "account/login.html" in [
        template.name for template in anonymous_response.templates
    ]


def test_500_renders_from_a_bare_context_with_no_site_setup() -> None:
    """Pins the asymmetry: `500.html` needs neither `django_db` nor
    `mock_site_context`, unlike every shell-page test above. `server_error`
    calls `template.render()` with no arguments at all, so this is the exact
    call it makes.
    """
    body = get_template("500.html").render()

    assert "Sorry, there is a problem with this page" in body
    assert "vendor/tailwind.output.css" in body
    assert 'class="header"' not in body
    assert "hx-headers" not in body
    assert body.count("<h1") == 1
    assert "noindex" in body


def test_503_renders_from_a_bare_context_with_no_site_setup() -> None:
    body = get_template("503.html").render()

    assert "Sorry, the service is unavailable" in body
    assert "vendor/tailwind.output.css" in body
    assert 'class="header"' not in body
    assert "hx-headers" not in body
    assert body.count("<h1") == 1
    assert "noindex" in body


def test_503_has_no_dashboard_link_or_navigation() -> None:
    """A maintenance page must not carry anything that implies the service
    is up.
    """
    body = get_template("503.html").render()

    assert "dashboard" not in body.lower()
    assert "<nav" not in body


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=ERROR_PAGES_URLCONF, DEBUG=False)
def test_500_end_to_end_renders_the_standalone_page(mock_site_context) -> None:
    """Drives an actual raised exception through Django's real `handler500`
    machinery, the way `django.views.defaults.server_error` is reached in
    production, rather than calling the template directly. `DEBUG` has to be
    off, or Django's own debug page intercepts the exception before
    `server_error` ever runs.
    """
    client = Client(raise_request_exception=False)

    response = client.get(reverse("test_500"))

    assert response.status_code == 500
    assert "500.html" in [template.name for template in response.templates]
    assert "Sorry, there is a problem with this page" in response.content.decode()


# --- Cross-cutting behaviours, pinned once across all eight error surfaces ---
#
# Each renderer below reaches its page the same way the per-page tests above
# do (a real 404, a real CSRF failure, allauth's own rate limiter, axes'
# own lockout, `get_template().render()` for the two standalone pages) and
# returns (status_code, template_name, body) so the tests that follow can
# check one behaviour across every page without re-deriving how to reach it.


def _lock_out_account(client: Client, email: str) -> _MonkeyPatchedWSGIResponse:
    """Submit failed logins until the pair is locked, and return that response."""
    login_url = reverse("account_login")
    credentials = {
        "login": email,
        "password": "wrong-password",  # pragma: allowlist secret
    }
    responses = [client.post(login_url, credentials) for _ in range(5)]
    return responses[-1]


def _render_404_page() -> tuple[int, str, str]:
    response = Client().get("/no-such-page/")
    return response.status_code, "404.html", response.content.decode()


def _render_403_page() -> tuple[int, str, str]:
    with override_settings(ROOT_URLCONF=ERROR_PAGES_URLCONF):
        response = Client().get(reverse("test_403"))
    return response.status_code, "403.html", response.content.decode()


def _render_400_page() -> tuple[int, str, str]:
    with override_settings(ROOT_URLCONF=ERROR_PAGES_URLCONF):
        response = Client().get(reverse("test_400"))
    return response.status_code, "400.html", response.content.decode()


def _render_403_csrf_page() -> tuple[int, str, str]:
    client = Client(enforce_csrf_checks=True)
    response = client.post(
        reverse("account_login"),
        {
            "login": "nobody@example.com",
            "password": "wrong-password",  # pragma: allowlist secret
        },
    )
    return response.status_code, "403_csrf.html", response.content.decode()


def _render_429_page() -> tuple[int, str, str]:
    cache.clear()
    client = Client()
    with override_settings(ACCOUNT_RATE_LIMITS={"signup": "1/m/ip"}):
        _post_signup(client, "cross-cutting-429-a@example.com")
        response = _post_signup(client, "cross-cutting-429-b@example.com")
    return response.status_code, "429.html", response.content.decode()


def _render_500_page() -> tuple[int, str, str]:
    with override_settings(ROOT_URLCONF=ERROR_PAGES_URLCONF, DEBUG=False):
        response = Client(raise_request_exception=False).get(reverse("test_500"))
    return response.status_code, "500.html", response.content.decode()


def _render_503_page() -> tuple[int, str, str]:
    body = get_template("503.html").render()
    return 503, "503.html", body


def _render_lockout_page() -> tuple[int, str, str]:
    user = UserFactory()
    response = _lock_out_account(Client(), user.email)
    return response.status_code, "accounts/lockout.html", response.content.decode()


PAGE_RENDERERS: dict[str, Callable[[], tuple[int, str, str]]] = {
    "404": _render_404_page,
    "403": _render_403_page,
    "400": _render_400_page,
    "403_csrf": _render_403_csrf_page,
    "429": _render_429_page,
    "500": _render_500_page,
    "503": _render_503_page,
    "lockout": _render_lockout_page,
}


@pytest.mark.django_db
@pytest.mark.parametrize("page_name", sorted(PAGE_RENDERERS))
def test_every_page_offers_a_route_forward(mock_site_context, page_name: str) -> None:
    _, _, body = PAGE_RENDERERS[page_name]()

    assert 'class="btn' in body


@pytest.mark.django_db
@pytest.mark.parametrize("page_name", sorted(PAGE_RENDERERS))
def test_every_page_carries_noindex(mock_site_context, page_name: str) -> None:
    _, _, body = PAGE_RENDERERS[page_name]()

    assert 'content="noindex"' in body


@pytest.mark.django_db
def test_every_page_has_a_distinct_title(mock_site_context) -> None:
    """Several pages reuse the same wording for `<title>` and `<h1>`, so a
    body-text assertion alone would not notice a deleted or duplicated
    title block.
    """
    titles = []
    for page_name, render in PAGE_RENDERERS.items():
        _, _, body = render()
        match = re.search(r"<title>(.*?)</title>", body, re.DOTALL)
        assert match is not None, f"{page_name} has no <title>"
        titles.append(match.group(1).strip())

    assert len(titles) == len(set(titles))


@pytest.mark.django_db
def test_no_page_echoes_its_own_trigger_path(mock_site_context) -> None:
    """404 already pins this on its own. 403 and 400 use synthetic paths
    that appear nowhere else, so they are safe to check the same way; 429's
    trigger path is `account_signup`, a real route the site header already
    links to on every page, so checking for its absence would fail on the
    header, not on a leak. 403_csrf and lockout are excluded for the same
    reason as 429, plus both deliberately link back to `account_login`, the
    path that triggered them, as their primary action. 503 has no
    triggering path at all.
    """
    trigger_paths = {
        "403": "/test-403/",
        "400": "/test-400/",
        "500": "/test-500/",
    }

    for page_name, path in trigger_paths.items():
        _, _, body = PAGE_RENDERERS[page_name]()
        assert path not in body


@pytest.mark.django_db
@pytest.mark.parametrize("page_name", sorted(PAGE_RENDERERS))
def test_no_page_leaks_internal_detail(mock_site_context, page_name: str) -> None:
    _, _, body = PAGE_RENDERERS[page_name]()

    assert "Traceback" not in body
    assert "deliberate failure" not in body
    assert "RuntimeError" not in body
    assert django.get_version() not in body
    assert "Reference:" not in body
    assert "Error ID" not in body


@pytest.mark.django_db
@pytest.mark.parametrize("page_name", sorted(PAGE_RENDERERS))
def test_no_page_shows_a_countdown_or_rate_figure(
    mock_site_context, page_name: str
) -> None:
    _, _, body = PAGE_RENDERERS[page_name]()

    assert (
        re.search(r"\d+\s*(second|minute|hour|attempt|request)", body, re.IGNORECASE)
        is None
    )
