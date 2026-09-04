"""The page django-axes serves once a login attempt is locked out."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory

if TYPE_CHECKING:
    # Stub-only: the test client's response carries `templates`, which a plain
    # HttpResponse does not.
    from django.test.client import _MonkeyPatchedWSGIResponse

# The bare body django-axes returns when no lockout template is configured.
AXES_DEFAULT_BODY = "Account locked: too many login attempts"


def _lock_out(client: Client, email: str) -> _MonkeyPatchedWSGIResponse:
    """Submit failed logins until the pair is locked, and return that response."""
    login_url = reverse("account_login")
    credentials = {
        "login": email,
        "password": "wrong-password",  # pragma: allowlist secret
    }
    responses = [client.post(login_url, credentials) for _ in range(5)]
    return responses[-1]


@pytest.mark.django_db
def test_lockout_serves_the_branded_page(mock_site_context) -> None:
    user = UserFactory()

    response = _lock_out(Client(), user.email)

    assert response.status_code == 429
    assert "accounts/lockout.html" in [t.name for t in response.templates]


@pytest.mark.django_db
def test_lockout_renders_the_shared_error_panel(mock_site_context) -> None:
    """Lockout and 429.html must render the same panel."""
    user = UserFactory()

    response = _lock_out(Client(), user.email)

    assert "Error 429" in response.content.decode()


@pytest.mark.django_db
def test_lockout_page_offers_a_route_forward(mock_site_context) -> None:
    """A locked-out visitor must not land on a dead end."""
    user = UserFactory()

    response = _lock_out(Client(), user.email)
    body = response.content.decode()

    assert AXES_DEFAULT_BODY not in body
    assert reverse("account_login") in body
    assert reverse("account_reset_password") in body
