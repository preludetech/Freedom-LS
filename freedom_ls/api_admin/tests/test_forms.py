"""Tests for the API key add form."""

from __future__ import annotations

from datetime import timedelta

import pytest

from django.utils import timezone

from freedom_ls.api.scopes import ApiScope
from freedom_ls.api_admin.forms import ApiKeyAddForm


def test_the_form_has_no_site_field():
    assert list(ApiKeyAddForm().fields) == ["name", "scopes", "expires_at"]


def test_the_scope_choices_are_every_scope_with_its_description():
    # Arrange
    expected = [
        (scope.value, f"{scope.label}: {scope.description}") for scope in ApiScope
    ]

    # Act
    choices = list(ApiKeyAddForm().fields["scopes"].choices)

    # Assert
    assert choices == expected
    assert len(choices) >= 1


def test_an_empty_scope_selection_is_invalid():
    # Arrange
    form = ApiKeyAddForm(data={"name": "Reporting", "scopes": []})

    # Act / Assert
    assert not form.is_valid()
    assert "scopes" in form.errors


@pytest.mark.django_db
def test_a_past_expiry_is_invalid():
    # Arrange
    form = ApiKeyAddForm(
        data={
            "name": "Reporting",
            "scopes": [ApiScope.USERS.value],
            "expires_at": (timezone.now() - timedelta(days=1)).isoformat(),
        }
    )

    # Act / Assert
    assert not form.is_valid()
    assert form.errors["expires_at"] == ["The expiry must be in the future."]
