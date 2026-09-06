"""The progress admins render against the record-keyed models.

Every field name in a ModelAdmin is a string, so a stale one is a FieldError at
import or a 500 on the page -- never a type error. `CourseFormAttempt` reads
most of its columns through `form_progress`, which makes those paths
particularly easy to break from the form_engine side without noticing.
"""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.factories import FormProgressFactory
from freedom_ls.learner_progress.admin import quiz_result
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    CourseProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import CourseFormAttempt, TopicProgress

pytestmark = pytest.mark.django_db

CHANGELIST_URL_NAMES = [
    "admin:freedom_ls_learner_progress_courseprogress_changelist",
    "admin:freedom_ls_learner_progress_topicprogress_changelist",
    "admin:freedom_ls_learner_progress_courseformattempt_changelist",
]


@pytest.fixture
def superuser_client(mock_site_context):
    client = Client()
    client.force_login(UserFactory(superuser=True))
    return client


@pytest.fixture
def progress_rows(mock_site_context):
    TopicProgressFactory()
    CourseProgressFactory()
    CourseFormAttemptFactory()


@pytest.mark.parametrize("url_name", CHANGELIST_URL_NAMES)
def test_changelist_renders_with_rows_present(
    superuser_client, progress_rows, url_name
):
    response = superuser_client.get(reverse(url_name))

    assert response.status_code == 200


@pytest.mark.parametrize("url_name", CHANGELIST_URL_NAMES)
def test_changelist_search_resolves_its_field_paths(
    superuser_client, progress_rows, url_name
):
    """A search_fields path that no longer exists raises rather than filtering."""
    response = superuser_client.get(reverse(url_name), {"q": "nobody@example.com"})

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("url_name", "row_factory"),
    [
        (
            "admin:freedom_ls_learner_progress_courseprogress_change",
            CourseProgressFactory,
        ),
        (
            "admin:freedom_ls_learner_progress_topicprogress_change",
            TopicProgressFactory,
        ),
        (
            "admin:freedom_ls_learner_progress_courseformattempt_change",
            CourseFormAttemptFactory,
        ),
    ],
)
def test_change_form_renders(superuser_client, url_name, row_factory):
    row = row_factory()

    response = superuser_client.get(reverse(url_name, args=[row.pk]))

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("url_name", "lookup"),
    [
        (
            "admin:freedom_ls_learner_progress_topicprogress_changelist",
            "course_progress__learner__id__exact",
        ),
        (
            "admin:freedom_ls_learner_progress_courseformattempt_changelist",
            "course_progress__learner__id__exact",
        ),
        (
            "admin:freedom_ls_learner_progress_courseprogress_changelist",
            "learner__id__exact",
        ),
    ],
)
def test_changelist_accepts_the_learner_lookup_the_learner_page_links_with(
    superuser_client, url_name, lookup
):
    """`learner_progress_links` hard-codes these lookups into its hrefs.

    A changelist rejects any GET param it cannot account for, so a filter that
    stopped naming the learner would turn those links into 500s rather than
    quietly ignoring them.
    """
    record = CourseProgressFactory()
    learner_id = str(record.learner_id)

    response = superuser_client.get(reverse(url_name), {lookup: learner_id})

    assert response.status_code == 200


def test_course_progress_status_filter_separates_the_three_states(superuser_client):
    completed = CourseProgressFactory(
        started_at=timezone.now(), completed_time=timezone.now()
    )
    in_progress = CourseProgressFactory(started_at=timezone.now())
    never_opened = CourseProgressFactory(started_at=None)
    url = reverse("admin:freedom_ls_learner_progress_courseprogress_changelist")

    def visible(status: str) -> list:
        response = superuser_client.get(url, {"status": status})
        return [row.pk for row in response.context["cl"].result_list]

    assert visible("complete") == [completed.pk]
    assert visible("not_started") == [never_opened.pk]
    assert set(visible("incomplete")) == {in_progress.pk, never_opened.pk}


def test_course_progress_change_page_carries_the_item_panels(superuser_client):
    """The topics and form attempts behind one record, on the record's page."""
    record = CourseProgressFactory()
    topic_record = TopicProgressFactory(course_progress=record)
    attempt = CourseFormAttemptFactory(course_progress=record)

    response = superuser_client.get(
        reverse(
            "admin:freedom_ls_learner_progress_courseprogress_change", args=[record.pk]
        )
    )

    assert response.status_code == 200
    inline_models = {
        formset.formset.model for formset in response.context["inline_admin_formsets"]
    }
    assert {TopicProgress, CourseFormAttempt} <= inline_models
    body = response.content.decode()
    assert topic_record.topic.title in body
    assert str(attempt.form_progress.form) in body


def test_quiz_result_reports_a_pass_a_fail_and_neither(
    mock_site_context, course_with_scored_quiz, sit_quiz
):
    """Only a scored quiz has a result; every other attempt has none.

    `FormProgress.quiz_percentage` raises rather than returning nothing for the
    other cases, so this is what keeps the column off the error path.
    """
    course, form, question, right, wrong = course_with_scored_quiz()
    record = CourseProgressFactory(course=course)

    passed = sit_quiz(record, form, question, right)
    failed = sit_quiz(record, form, question, wrong)
    unscored = CourseFormAttemptFactory(course_progress=record).form_progress

    assert quiz_result(passed) == "100% passed"
    assert quiz_result(failed) == "0% failed"
    assert quiz_result(unscored) is None


def test_form_progress_changelist_says_which_course_an_attempt_was_sat_in(
    superuser_client,
):
    """Exercised through form_engine's changelist because the relation it reads
    is this app's: a form can be sat outside any course, and the absence of a
    CourseFormAttempt is exactly what records that."""
    in_course = CourseFormAttemptFactory()
    standalone = FormProgressFactory()

    response = superuser_client.get(
        reverse("admin:freedom_ls_form_engine_formprogress_changelist")
    )

    rows = {row.pk: row for row in response.context["cl"].result_list}
    admin_class = response.context["cl"].model_admin
    assert admin_class.in_course(rows[in_course.form_progress_id]) == str(
        in_course.course_progress.course
    )
    assert admin_class.in_course(rows[standalone.pk]) is None
