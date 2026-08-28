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
from freedom_ls.form_engine.factories import FormFactory
from freedom_ls.form_engine.models import FormStrategy
from freedom_ls.learner_interface.utils import get_course_index
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory

from .conftest import course_with_form, form_attempt


@pytest.fixture
def completed_quiz_no_pass_mark(mock_site_context):
    """A registered learner who has completed a QUIZ form with no pass mark set."""
    form = FormFactory(
        title="Ungraded Quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=None,
    )
    course = course_with_form(
        form, title="No Pass Mark Course", slug="no-pass-mark-course"
    )
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course, is_active=True)
    form_attempt(
        course,
        user,
        form,
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
            "learner_interface:view_course_item",
            kwargs={
                "course_slug": completed_quiz_no_pass_mark["course"].slug,
                "index": 1,
            },
        )
    )

    assert response.status_code == 200


def _results_page(fixture, logged_in_client):
    client = logged_in_client(fixture["user"])
    return client.get(
        reverse(
            "learner_interface:course_form_complete",
            kwargs={"course_slug": fixture["course"].slug, "index": 1},
        )
    )


@pytest.mark.django_db
def test_results_page_renders_for_completed_quiz_without_pass_mark(
    completed_quiz_no_pass_mark, logged_in_client
):
    response = _results_page(completed_quiz_no_pass_mark, logged_in_client)

    assert response.status_code == 200


@pytest.mark.django_db
def test_results_page_without_pass_mark_announces_no_verdict(
    completed_quiz_no_pass_mark, logged_in_client
):
    """No pass mark means no bar to clear, so the page claims neither outcome."""
    response = _results_page(completed_quiz_no_pass_mark, logged_in_client)

    content = response.content.decode()
    assert "Quiz passed" not in content
    assert "Quiz not passed" not in content


@pytest.mark.django_db
def test_results_page_without_pass_mark_still_shows_the_score(
    completed_quiz_no_pass_mark, logged_in_client
):
    """Dropping the verdict must not drop the score: 3 of 5 is still reported."""
    response = _results_page(completed_quiz_no_pass_mark, logged_in_client)

    content = response.content.decode()
    assert response.context["percentage"] == 60
    assert 'data-testid="quiz-score"' in content


@pytest.mark.django_db
def test_results_page_without_pass_mark_offers_continue_not_retry(
    completed_quiz_no_pass_mark, logged_in_client
):
    """A quiz nobody can fail cannot be "retried" — the only action is to move on."""
    response = _results_page(completed_quiz_no_pass_mark, logged_in_client)

    content = response.content.decode()
    assert "Retry quiz" not in content
    assert "Continue" in content


@pytest.mark.django_db
def test_dashboard_renders_for_learner_with_completed_quiz_without_pass_mark(
    completed_quiz_no_pass_mark, logged_in_client
):
    client = logged_in_client(completed_quiz_no_pass_mark["user"])

    response = client.get(reverse("learner_interface:dashboard"))

    assert response.status_code == 200
