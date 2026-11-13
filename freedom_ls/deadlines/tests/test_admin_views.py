from __future__ import annotations

from datetime import timedelta

import pytest

from django.contrib import messages
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.tests.helpers import collection_item_for
from freedom_ls.deadlines.factories import CoursePauseFactory
from freedom_ls.deadlines.models import CoursePause, DeadlineExtension
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.tests.factories import SiteFactory

pytestmark = pytest.mark.django_db

PAUSE_URL = "admin:freedom_ls_learner_progress_courseprogress_pause"
RESUME_URL = "admin:freedom_ls_learner_progress_courseprogress_resume"
EXTEND_URL = "admin:freedom_ls_learner_progress_courseprogress_extend"
CHANGE_URL = "admin:freedom_ls_learner_progress_courseprogress_change"


def _levels(response) -> list[int]:
    return [m.level for m in messages.get_messages(response.wsgi_request)]


@pytest.fixture
def view_only_client(mock_site_context, logged_in_client):
    user = UserFactory(is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="view_courseprogress"))
    return logged_in_client(user)


def test_a_pause_post_creates_the_pause_and_redirects_to_the_change_page(
    staff_client, mock_site_context
) -> None:
    record = CourseProgressFactory()

    response = staff_client.post(
        reverse(PAUSE_URL, args=[record.pk]), {"reason": "Medical leave"}
    )

    assert response.status_code == 302
    assert response.url == reverse(CHANGE_URL, args=[record.pk])
    pause = CoursePause.objects.get(course_progress=record)
    assert pause.reason == "Medical leave"
    assert pause.started_by is not None


def test_a_pause_post_with_a_planned_resume_stores_the_date(
    staff_client, mock_site_context
) -> None:
    record = CourseProgressFactory()
    resume_on = timezone.now().date() + timedelta(days=10)

    staff_client.post(
        reverse(PAUSE_URL, args=[record.pk]),
        {"reason": "Leave", "planned_resume_on": resume_on.isoformat()},
    )

    assert (
        CoursePause.objects.get(course_progress=record).planned_resume_on == resume_on
    )


def test_a_blank_reason_rerenders_with_an_error_and_writes_nothing(
    staff_client, mock_site_context
) -> None:
    record = CourseProgressFactory()

    response = staff_client.post(reverse(PAUSE_URL, args=[record.pk]), {"reason": ""})

    assert response.status_code == 200
    assert "reason" in response.context["form"].errors
    assert not CoursePause.objects.exists()


def test_a_service_refusal_shows_as_a_form_error(
    staff_client, mock_site_context
) -> None:
    record = CourseProgressFactory()
    CoursePauseFactory(course_progress=record)

    response = staff_client.post(
        reverse(PAUSE_URL, args=[record.pk]), {"reason": "Again"}
    )

    assert response.status_code == 200
    assert response.context["form"].non_field_errors()
    assert CoursePause.objects.count() == 1


def test_a_resume_post_ends_the_pause_and_redirects(
    staff_client, mock_site_context
) -> None:
    record = CourseProgressFactory()
    pause = CoursePauseFactory(course_progress=record)

    response = staff_client.post(
        reverse(RESUME_URL, args=[record.pk]), {"reason": "Back"}
    )

    assert response.status_code == 302
    assert response.url == reverse(CHANGE_URL, args=[record.pk])
    pause.refresh_from_db()
    assert pause.ended_at is not None
    assert pause.ended_reason == "Back"
    assert AuditLogEntry.unscoped.filter(action="course.resumed").count() == 1


def test_a_repeated_resume_post_is_a_no_op_with_a_warning(
    staff_client, mock_site_context
) -> None:
    record = CourseProgressFactory()
    CoursePauseFactory(course_progress=record)
    url = reverse(RESUME_URL, args=[record.pk])
    staff_client.post(url, {"reason": "Back"})

    response = staff_client.post(url, {"reason": "Back"})

    assert response.status_code == 302
    assert _levels(response)[-1] == messages.WARNING
    assert AuditLogEntry.unscoped.filter(action="course.resumed").count() == 1


def test_resume_get_for_an_unpaused_record_redirects_with_a_warning(
    staff_client, mock_site_context
) -> None:
    record = CourseProgressFactory()

    response = staff_client.get(reverse(RESUME_URL, args=[record.pk]))

    assert response.status_code == 302
    assert response.url == reverse(CHANGE_URL, args=[record.pk])
    assert _levels(response) == [messages.WARNING]


def test_resume_get_for_a_paused_record_shows_the_form(
    staff_client, mock_site_context
) -> None:
    record = CourseProgressFactory()
    CoursePauseFactory(course_progress=record)

    response = staff_client.get(reverse(RESUME_URL, args=[record.pk]))

    assert response.status_code == 200
    assert "reason" in response.context["form"].fields


@pytest.mark.parametrize("url_name", [PAUSE_URL, RESUME_URL])
@pytest.mark.parametrize("method", ["get", "post"])
def test_a_user_without_change_permission_gets_403(
    view_only_client, mock_site_context, url_name, method
) -> None:
    record = CourseProgressFactory()
    CoursePauseFactory(course_progress=record)

    response = getattr(view_only_client, method)(
        reverse(url_name, args=[record.pk]), {"reason": "x"}
    )

    assert response.status_code == 403
    assert CoursePause.objects.get().ended_at is None


@pytest.mark.parametrize("url_name", [PAUSE_URL, RESUME_URL])
def test_another_sites_record_is_a_404(
    staff_client, mock_site_context, url_name
) -> None:
    foreign = CourseProgressFactory(site=SiteFactory(domain="other.example.com"))

    response = staff_client.get(reverse(url_name, args=[foreign.pk]))

    assert response.status_code == 404


def _record_with_dated_item():
    course = CourseFactory(time_limit_days=30)
    topic = TopicFactory(title="Reading")
    course.items.create(child=topic, order=0)
    item = collection_item_for(course, topic)
    item.due_date = timezone.now().date() + timedelta(days=10)
    item.save()
    return CourseProgressFactory(course=course), item


@pytest.mark.parametrize(
    "extra", [{"days": "4"}, {"requested_date": "DATE"}], ids=["days", "date"]
)
def test_an_extend_post_creates_one_extension_and_redirects(
    staff_client, mock_site_context, extra
) -> None:
    record, item = _record_with_dated_item()
    if extra.get("requested_date") == "DATE":
        extra = {"requested_date": (item.due_date + timedelta(days=4)).isoformat()}

    response = staff_client.post(
        reverse(EXTEND_URL, args=[record.pk]),
        {
            "target_kind": "collection_item",
            "collection_item": str(item.pk),
            "reason": "Ill",
            **extra,
        },
    )

    assert response.status_code == 302
    assert response.url == reverse(CHANGE_URL, args=[record.pk])
    extension = DeadlineExtension.objects.get(course_progress=record)
    assert extension.days == 4
    assert extension.collection_item == item


def test_a_whole_course_post_names_the_learner_in_the_message(
    staff_client, mock_site_context
) -> None:
    record, _ = _record_with_dated_item()

    response = staff_client.post(
        reverse(EXTEND_URL, args=[record.pk]),
        {"target_kind": "course", "days": "2", "reason": "Ill"},
    )

    assert response.status_code == 302
    texts = [str(m) for m in messages.get_messages(response.wsgi_request)]
    assert texts == [
        f"Moved {record.learner}'s deadlines in {record.course} by 2 days."
    ]


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({"reason": "", "days": "2"}, id="blank-reason"),
        pytest.param({"days": "2", "requested_date": "2030-01-05"}, id="both"),
        pytest.param(
            {"target_kind": "course", "requested_date": "2030-01-05"}, id="course-date"
        ),
    ],
)
def test_an_invalid_extend_post_rerenders_with_an_error_and_writes_nothing(
    staff_client, mock_site_context, data
) -> None:
    record, _ = _record_with_dated_item()
    payload = {"target_kind": "time_limit", "reason": "Ill", **data}

    response = staff_client.post(reverse(EXTEND_URL, args=[record.pk]), payload)

    assert response.status_code == 200
    assert response.context["form"].errors
    assert not DeadlineExtension.objects.exists()


def test_an_extend_service_refusal_shows_as_a_form_error(
    staff_client, mock_site_context
) -> None:
    record, item = _record_with_dated_item()
    past = (item.due_date - timedelta(days=1)).isoformat()

    response = staff_client.post(
        reverse(EXTEND_URL, args=[record.pk]),
        {
            "target_kind": "collection_item",
            "collection_item": str(item.pk),
            "requested_date": past,
            "reason": "Ill",
        },
    )

    assert response.status_code == 200
    assert response.context["form"].non_field_errors()
    assert not DeadlineExtension.objects.exists()


def test_the_extend_page_lists_each_target_with_its_current_date(
    staff_client, mock_site_context
) -> None:
    record, _ = _record_with_dated_item()

    response = staff_client.get(reverse(EXTEND_URL, args=[record.pk]))

    assert [label for label, _ in response.context["targets"]] == [
        "Reading",
        "Course time limit",
    ]


def test_extend_requires_change_permission(view_only_client, mock_site_context) -> None:
    record, _ = _record_with_dated_item()

    response = view_only_client.post(
        reverse(EXTEND_URL, args=[record.pk]),
        {"target_kind": "course", "days": "2", "reason": "x"},
    )

    assert response.status_code == 403
    assert not DeadlineExtension.objects.exists()


def test_extend_for_another_sites_record_is_a_404(
    staff_client, mock_site_context
) -> None:
    foreign = CourseProgressFactory(site=SiteFactory(domain="other.example.com"))

    response = staff_client.get(reverse(EXTEND_URL, args=[foreign.pk]))

    assert response.status_code == 404
