"""Seeding the applications panel withdraws every other application the persona holds.

The panel has to show exactly the seeded set, so an application left over from
an earlier QA run is deleted -- application first, then its sitting, since
CourseApplication.form_progress is RESTRICT.
"""

from __future__ import annotations

import pytest

from django.conf import settings

if "freedom_ls.qa_helpers" not in settings.INSTALLED_APPS:  # pragma: no cover
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.form_engine.factories import FormProgressFactory
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.qa_helpers.management.commands.qa_create_dashboard_applications_panel import (
    SeededApplication,
    _ensure_form,
    _seed_applications,
)

pytestmark = pytest.mark.dev_tooling


@pytest.mark.django_db
def test_stale_applications_and_their_sittings_are_withdrawn(mock_site_context):
    site = mock_site_context
    user = UserFactory()
    stale_sitting = FormProgressFactory(user=user)
    stale = CourseApplicationFactory(user=user, form_progress=stale_sitting)
    other_users = CourseApplicationFactory()
    form, question = _ensure_form(site)

    _seed_applications(
        site,
        user,
        [
            SeededApplication("Seeded Draft", 2, False),
            SeededApplication("Seeded Submitted", 1, True),
        ],
        form,
        question,
    )

    applications = CourseApplication._base_manager.filter(user=user).order_by(
        "-created_at"
    )
    assert [(a.course.title, a.is_submitted) for a in applications] == [
        ("Seeded Submitted", True),
        ("Seeded Draft", False),
    ]
    assert not CourseApplication._base_manager.filter(pk=stale.pk).exists()
    assert not FormProgress._base_manager.filter(pk=stale_sitting.pk).exists()
    assert CourseApplication._base_manager.filter(pk=other_users.pk).exists()


@pytest.mark.django_db
def test_an_empty_seed_leaves_the_persona_with_no_applications(mock_site_context):
    site = mock_site_context
    user = UserFactory()
    CourseApplicationFactory(user=user, form_progress=FormProgressFactory(user=user))
    form, question = _ensure_form(site)

    _seed_applications(site, user, [], form, question)

    assert not CourseApplication._base_manager.filter(user=user).exists()
    assert not FormProgress._base_manager.filter(user=user).exists()
