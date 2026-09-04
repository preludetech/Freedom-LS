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

import pytest

from django.core.cache import cache
from django.template.loader import get_template
from django.test import Client, override_settings
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory

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
