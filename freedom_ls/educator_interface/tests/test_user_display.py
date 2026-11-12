"""email_below_name: the second line under a person's name."""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.educator_interface.user_display import email_below_name


@pytest.mark.django_db
def test_named_user_shows_their_email(mock_site_context: None) -> None:
    user = UserFactory(first_name="Ada", last_name="Lovelace", email="ada@example.com")

    assert email_below_name(user) == "ada@example.com"


@pytest.mark.django_db
def test_unnamed_user_shows_nothing_because_the_name_is_already_the_email(
    mock_site_context: None,
) -> None:
    user = UserFactory(first_name="", last_name="", email="ada@example.com")

    assert email_below_name(user) == ""
