"""A completed QUIZ form with no ``quiz_pass_percentage`` set is a supported
authoring configuration (a survey / self-assessment with a score but no
verdict) and must never raise. Covers the status calculation in
``get_content_status`` plus the three views that build the outline through it:
the course player, the results page, and the dashboard.
"""

from __future__ import annotations

import pytest

from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import FormFactory
from freedom_ls.content_engine.models import FormStrategy
from freedom_ls.student_interface.utils import get_course_index
from freedom_ls.student_management.factories import UserCourseRegistrationFactory
from freedom_ls.student_progress.factories import FormProgressFactory

from .conftest import course_with_form


@pytest.fixture
def completed_quiz_no_pass_mark(mock_site_context):
    """A registered student who has completed a QUIZ form with no pass mark set."""
    form = FormFactory(
        title="Ungraded Quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=None,
    )
    course = course_with_form(
        form, title="No Pass Mark Course", slug="no-pass-mark-course"
    )
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course, is_active=True)
    FormProgressFactory(
        user=user,
        form=form,
        completed_time=timezone.now(),
        scores={"score": 3, "max_score": 5},
    )
    return {"course": course, "form": form, "user": user}


@pytest.mark.django_db
def test_get_course_index_quiz_without_pass_mark_reads_complete_ready(
    completed_quiz_no_pass_mark,
):
    """No pass mark to fail against: a completed attempt reads COMPLETE, not FAILED."""
    children = get_course_index(
        user=completed_quiz_no_pass_mark["user"],
        course=completed_quiz_no_pass_mark["course"],
        can_access_content=True,
    )
    statuses = [c["status"] for c in children]
    assert statuses == ["COMPLETE"]


@pytest.mark.django_db
def test_course_player_renders_for_completed_quiz_without_pass_mark(
    completed_quiz_no_pass_mark, logged_in_client
):
    client = logged_in_client(completed_quiz_no_pass_mark["user"])

    response = client.get(
        reverse(
            "student_interface:view_course_item",
            kwargs={
                "course_slug": completed_quiz_no_pass_mark["course"].slug,
                "index": 1,
            },
        )
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_results_page_renders_for_completed_quiz_without_pass_mark(
    completed_quiz_no_pass_mark, logged_in_client
):
    client = logged_in_client(completed_quiz_no_pass_mark["user"])

    response = client.get(
        reverse(
            "student_interface:course_form_complete",
            kwargs={
                "course_slug": completed_quiz_no_pass_mark["course"].slug,
                "index": 1,
            },
        )
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_dashboard_renders_for_student_with_completed_quiz_without_pass_mark(
    completed_quiz_no_pass_mark, logged_in_client
):
    client = logged_in_client(completed_quiz_no_pass_mark["user"])

    response = client.get(reverse("student_interface:dashboard"))

    assert response.status_code == 200
