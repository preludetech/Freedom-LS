"""The progress admins render against the record-keyed models.

Every field name in a ModelAdmin is a string, so a stale one is a FieldError at
import or a 500 on the page -- never a type error. `CourseFormAttempt` reads
most of its columns through `form_progress`, which makes those paths
particularly easy to break from the form_engine side without noticing.
"""

from __future__ import annotations

import pytest

from django.contrib import admin
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.factories import FormProgressFactory
from freedom_ls.learner_progress.admin import (
    CourseProgressFormAttemptInline,
    CourseProgressTopicInline,
    quiz_result,
)
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    CourseProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)

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
def test_changelist_search_resolves_its_field_paths(
    superuser_client, progress_rows, url_name
):
    """A search_fields path that no longer exists raises rather than filtering."""
    response = superuser_client.get(reverse(url_name), {"q": "nobody@example.com"})

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


PROGRESS_FACTORIES = {
    "courseprogress": CourseProgressFactory,
    "topicprogress": TopicProgressFactory,
    "courseformattempt": CourseFormAttemptFactory,
}


def _progress_url(model_name: str, view: str, *args: object) -> str:
    return reverse(f"admin:freedom_ls_learner_progress_{model_name}_{view}", args=args)


@pytest.mark.parametrize("model_name", PROGRESS_FACTORIES)
def test_the_progress_changelist_opens_for_a_superuser_and_lists_the_row(
    superuser_client, model_name
):
    row = PROGRESS_FACTORIES[model_name]()

    response = superuser_client.get(_progress_url(model_name, "changelist"))

    assert response.status_code == 200
    assert [r.pk for r in response.context["cl"].result_list] == [row.pk]


@pytest.mark.parametrize("model_name", PROGRESS_FACTORIES)
def test_the_progress_change_page_has_no_save_button(superuser_client, model_name):
    row = PROGRESS_FACTORIES[model_name]()

    response = superuser_client.get(_progress_url(model_name, "change", row.pk))

    assert response.status_code == 200
    assert 'name="_save"' not in response.content.decode()


@pytest.mark.parametrize("model_name", PROGRESS_FACTORIES)
def test_a_superuser_cannot_open_the_progress_add_page(superuser_client, model_name):
    response = superuser_client.get(_progress_url(model_name, "add"))

    assert response.status_code == 403


@pytest.mark.parametrize("model_name", PROGRESS_FACTORIES)
def test_a_superuser_cannot_change_a_progress_row(superuser_client, model_name):
    row = PROGRESS_FACTORIES[model_name]()
    before = type(row)._base_manager.values().get(pk=row.pk)

    response = superuser_client.post(
        _progress_url(model_name, "change", row.pk), {"progress_percentage": "50"}
    )

    assert response.status_code == 403
    assert type(row)._base_manager.values().get(pk=row.pk) == before


@pytest.mark.parametrize("model_name", PROGRESS_FACTORIES)
def test_a_superuser_cannot_delete_a_progress_row(superuser_client, model_name):
    row = PROGRESS_FACTORIES[model_name]()

    response = superuser_client.post(
        _progress_url(model_name, "delete", row.pk), {"post": "yes"}
    )

    assert response.status_code == 403
    assert type(row)._base_manager.filter(pk=row.pk).exists()


@pytest.mark.parametrize("model_name", PROGRESS_FACTORIES)
def test_the_progress_admin_offers_no_delete_selected_action(
    superuser_client, rf, model_name
):
    request = rf.get("/")
    request.user = UserFactory(superuser=True)
    model = PROGRESS_FACTORIES[model_name]._meta.model

    actions = admin.site.get_model_admin(model).get_actions(request)

    assert "delete_selected" not in actions


@pytest.mark.parametrize("model_name", PROGRESS_FACTORIES)
def test_posting_delete_selected_to_the_changelist_leaves_the_row(
    superuser_client, model_name
):
    row = PROGRESS_FACTORIES[model_name]()

    response = superuser_client.post(
        _progress_url(model_name, "changelist"),
        {"action": "delete_selected", "_selected_action": [row.pk], "index": 0},
    )

    assert response.status_code == 200
    assert type(row)._base_manager.filter(pk=row.pk).exists()


@pytest.fixture
def course_progress_admin():
    return admin.site.get_model_admin(CourseProgress)


@pytest.mark.parametrize(
    "inline_class", [CourseProgressTopicInline, CourseProgressFormAttemptInline]
)
def test_the_item_inlines_deny_add(
    rf, mock_site_context, course_progress_admin, inline_class
):
    request = rf.get("/")
    request.user = UserFactory(superuser=True)
    inline = inline_class(course_progress_admin.model, admin.site)

    assert inline.has_add_permission(request) is False


@pytest.mark.parametrize(
    "inline_class", [CourseProgressTopicInline, CourseProgressFormAttemptInline]
)
def test_the_item_inlines_deny_change(
    rf, mock_site_context, course_progress_admin, inline_class
):
    request = rf.get("/")
    request.user = UserFactory(superuser=True)
    inline = inline_class(course_progress_admin.model, admin.site)

    assert inline.has_change_permission(request) is False


@pytest.mark.parametrize(
    "inline_class", [CourseProgressTopicInline, CourseProgressFormAttemptInline]
)
def test_the_item_inlines_deny_delete(
    rf, mock_site_context, course_progress_admin, inline_class
):
    request = rf.get("/")
    request.user = UserFactory(superuser=True)
    inline = inline_class(course_progress_admin.model, admin.site)

    assert inline.has_delete_permission(request) is False


@pytest.mark.parametrize(
    ("model_name", "lookup", "chosen"),
    [
        ("topicprogress", "topic__id__exact", lambda row: row.topic_id),
        ("courseprogress", "course__id__exact", lambda row: row.course_id),
        (
            "courseformattempt",
            "form_progress__form__id__exact",
            lambda row: row.form_progress.form_id,
        ),
    ],
)
def test_the_changelist_filters_to_the_chosen_topic_course_or_form(
    superuser_client, model_name, lookup, chosen
):
    wanted = PROGRESS_FACTORIES[model_name]()
    PROGRESS_FACTORIES[model_name]()

    response = superuser_client.get(
        _progress_url(model_name, "changelist"), {lookup: str(chosen(wanted))}
    )

    assert response.status_code == 200
    assert [r.pk for r in response.context["cl"].result_list] == [wanted.pk]


@pytest.mark.parametrize(
    ("model_name", "learner_of"),
    [
        ("topicprogress", lambda row: row.course_progress.learner),
        ("courseprogress", lambda row: row.learner),
        ("courseformattempt", lambda row: row.course_progress.learner),
    ],
)
def test_search_by_email_finds_only_that_learners_rows(
    superuser_client, model_name, learner_of
):
    wanted = PROGRESS_FACTORIES[model_name]()
    PROGRESS_FACTORIES[model_name]()

    response = superuser_client.get(
        _progress_url(model_name, "changelist"),
        {"q": learner_of(wanted).user.email},
    )

    assert [r.pk for r in response.context["cl"].result_list] == [wanted.pk]


@pytest.mark.parametrize(
    ("model_name", "lookup"),
    [
        ("topicprogress", "course_progress__learner__id__exact"),
        ("courseformattempt", "course_progress__learner__id__exact"),
    ],
)
def test_the_changelist_refuses_a_learner_filter(
    superuser_client, progress_rows, model_name, lookup
):
    response = superuser_client.get(
        _progress_url(model_name, "changelist"), {lookup: "1"}
    )

    assert response.status_code == 400
