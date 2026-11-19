"""Tests for the header avatar partial, which is also swapped out of band."""

from __future__ import annotations

import pytest

from django.contrib.auth.models import AbstractBaseUser
from django.template.loader import render_to_string

from freedom_ls.accounts.factories import UserFactory

pytestmark = pytest.mark.django_db


def _render(user: AbstractBaseUser, *, oob: bool = False) -> str:
    return render_to_string(
        "partials/header_avatar.html", {"avatar_user": user, "oob": oob}
    )


def test_initials_show_when_there_is_no_picture(mock_site_context):
    rendered = _render(UserFactory(first_name="Mary", last_name="Jane"))

    assert "MJ" in rendered
    assert "<img" not in rendered


def test_the_picture_shows_over_the_initials_when_there_is_one(mock_site_context):
    user = UserFactory(with_profile_picture=True, first_name="Mary", last_name="Jane")

    rendered = _render(user)

    assert "<img data-profile-picture" in rendered
    assert f'src="{user.profile_picture_url}"' in rendered
    assert "MJ" in rendered


def test_the_accessible_name_comes_from_hidden_text(mock_site_context):
    rendered = _render(UserFactory(first_name="Mary", last_name="Jane"))

    assert "Open user menu for Mary Jane" in rendered


def test_the_oob_attribute_is_present_only_when_oob(mock_site_context):
    user = UserFactory()

    assert 'hx-swap-oob="true"' in _render(user, oob=True)
    assert "hx-swap-oob" not in _render(user, oob=False)
    assert 'id="header-avatar"' in _render(user)
