"""Tests for the API key status filter."""

from __future__ import annotations

from datetime import timedelta

import pytest

from django.urls import reverse
from django.utils import timezone

from freedom_ls.api.factories import ApiKeyFactory
from freedom_ls.api.models import ApiKeyStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def keys_by_state(mock_site_context):
    now = timezone.now()
    return {
        "active": ApiKeyFactory(name="open-ended"),
        "active-with-expiry": ApiKeyFactory(
            name="expires later", expires_at=now + timedelta(days=1)
        ),
        "expired": ApiKeyFactory(name="lapsed", expires_at=now - timedelta(days=1)),
        "revoked": ApiKeyFactory(name="ended", revoked_at=now),
        "revoked-and-expired": ApiKeyFactory(
            name="ended and lapsed",
            revoked_at=now,
            expires_at=now - timedelta(days=1),
        ),
    }


def _names_for(client, status: str) -> set[str]:
    response = client.get(
        reverse("admin:freedom_ls_api_apikey_changelist"), {"status": status}
    )
    return {key.name for key in response.context["cl"].result_list}


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ApiKeyStatus.ACTIVE, {"open-ended", "expires later"}),
        (ApiKeyStatus.EXPIRED, {"lapsed"}),
        (ApiKeyStatus.REVOKED, {"ended", "ended and lapsed"}),
    ],
)
def test_each_status_value_returns_exactly_its_keys(
    staff_client, keys_by_state, status, expected
):
    # Act
    names = _names_for(staff_client, status)

    # Assert
    assert names == expected
