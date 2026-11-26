"""The shared "Last active" formatter: educator_interface/panels/learner/last_active.py."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.educator_interface.panels.learner.last_active import last_active_text


@pytest.mark.django_db
def test_last_active_text_is_the_date_only(mock_site_context: Site) -> None:
    user = UserFactory(last_active=datetime(2026, 3, 4, 15, 30, tzinfo=UTC))

    assert last_active_text(user) == "4 Mar 2026"


@pytest.mark.django_db
def test_last_active_text_is_never_when_the_user_has_not_been_active(
    mock_site_context: Site,
) -> None:
    user = UserFactory(last_active=None)

    assert last_active_text(user) == "Never"
