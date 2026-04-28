"""Tests for the FLS-specific erasure blocker.

``has_active_registrations`` is wired into
``EXPERIENCE_API_ERASURE_BLOCKERS`` in ``settings_dev`` / ``settings_prod``
so the ``erase_actor`` command refuses to run while a user still has
active course registrations. See spec §"Right to erasure".
"""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.student_management.models import UserCourseRegistration
from freedom_ls.student_management.xapi_erasure import has_active_registrations


@pytest.mark.django_db
def test_has_active_registrations_returns_false_when_none(mock_site_context) -> None:
    user = UserFactory()
    assert has_active_registrations(user.id) is False


@pytest.mark.django_db
def test_has_active_registrations_returns_true_when_user_has_one(
    mock_site_context,
) -> None:
    from freedom_ls.content_engine.models import Course

    user = UserFactory()
    course = Course.objects.create(
        site=mock_site_context,
        slug="c",
        title="C",
    )
    UserCourseRegistration.objects.create(
        site=mock_site_context,
        user=user,
        collection=course,
        is_active=True,
    )
    assert has_active_registrations(user.id) is True
