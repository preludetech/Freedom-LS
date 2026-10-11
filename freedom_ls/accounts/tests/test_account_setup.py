"""Tests for accounts.account_setup."""

from __future__ import annotations

from typing import cast

import pytest

from django.utils import timezone

from freedom_ls.accounts.account_setup import is_pending, pending_user_q
from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User


def _pending_user() -> User:
    user = cast(User, UserFactory())
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return user


def _self_signup_never_logged_in() -> User:
    return cast(User, UserFactory(last_login=None))


def _admin_made_with_typed_password() -> User:
    return cast(
        User,
        UserFactory(
            password="typed-password-1",  # pragma: allowlist secret
            last_login=None,
        ),
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("make_user", "expected"),
    [
        (_pending_user, True),
        (_self_signup_never_logged_in, False),
        (_admin_made_with_typed_password, False),
    ],
)
def test_is_pending_and_pending_user_q_agree(
    mock_site_context, make_user, expected: bool
) -> None:
    user = make_user()

    assert is_pending(user) is expected
    assert User.objects.filter(pending_user_q(), pk=user.pk).exists() is expected


@pytest.mark.django_db
def test_a_user_who_has_logged_in_is_not_pending(mock_site_context) -> None:
    user = _pending_user()
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])

    assert is_pending(user) is False
    assert not User.objects.filter(pending_user_q(), pk=user.pk).exists()
