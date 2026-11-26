"""Force deleting a user takes their course pauses and deadline extensions."""

from __future__ import annotations

import pytest

from django.contrib import admin
from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.deadlines.factories import CoursePauseFactory, DeadlineExtensionFactory
from freedom_ls.deadlines.models import CoursePause, DeadlineExtension
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.force_delete import (
    build_plan,
    force_delete_users,
    user_progress_roots,
)

pytestmark = pytest.mark.django_db


def test_force_delete_counts_and_removes_a_pause_and_an_extension(
    mock_site_context,
) -> None:
    progress = CourseProgressFactory()
    user = progress.learner.user
    CoursePauseFactory(course_progress=progress)
    DeadlineExtensionFactory(course_progress=progress)
    actor = UserFactory(superuser=True)
    request = RequestFactory().post("/")
    request.user = actor

    plan = build_plan(
        targets=[user],
        progress_roots=user_progress_roots([user]),
        request=request,
        admin_site=admin.site,
    )
    force_delete_users(
        [user],
        actor=actor,
        reason="Erasure requested",
        request=request,
        admin_site=admin.site,
    )

    assert plan.can_run is True
    assert plan.counts()[str(CoursePause._meta.verbose_name_plural)] == 1
    assert plan.counts()[str(DeadlineExtension._meta.verbose_name_plural)] == 1
    assert not CoursePause._base_manager.exists()
    assert not DeadlineExtension._base_manager.exists()
