from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
)
from freedom_ls.content_engine.tests.helpers import collection_item_for
from freedom_ls.deadlines.admin import (
    _policy_value_text,
)
from freedom_ls.deadlines.factories import (
    CourseDeadlineConfigFactory,
    CoursePauseFactory,
    DeadlineExtensionFactory,
    LearnerDeadlineOverrideFactory,
    SiteDeadlineConfigFactory,
)
from freedom_ls.deadlines.models import (
    CourseDeadlineConfig,
    CoursePause,
    DeadlineExtension,
    DeadlineKind,
    LearnerDeadlineOverride,
    SiteDeadlineConfig,
)
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.site_aware_models.factories import SiteTimeZoneConfigFactory
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context


def _queries_on(captured: CaptureQueriesContext, table: str) -> int:
    return sum(1 for query in captured.captured_queries if table in query["sql"])


PROGRESS_CHANGE_URL_NAME = "admin:freedom_ls_learner_progress_courseprogress_change"


def _record_with_item() -> tuple[CourseProgress, ContentCollectionItem]:
    course: Course = CourseFactory()
    topic = TopicFactory(title="Reading")
    course.items.create(child=topic, order=0)
    record: CourseProgress = CourseProgressFactory(course=course)
    return record, collection_item_for(course, topic)


def _progress_page(client: Client, record: CourseProgress):
    return client.get(reverse(PROGRESS_CHANGE_URL_NAME, args=[record.pk]))


@pytest.mark.django_db
def test_effective_deadlines_lists_items_sources_and_the_time_limit_end(
    staff_client, mock_site_context
) -> None:
    SiteTimeZoneConfigFactory(time_zone="Africa/Johannesburg")
    record, item = _record_with_item()
    Course.objects.filter(pk=record.course_id).update(time_limit_days=30)
    LearnerDeadlineOverrideFactory(
        course_progress=record,
        collection_item=item,
        kind=DeadlineKind.FIXED,
        due_date="2026-03-14",
        due_time="17:00",
        due_days_after_registration=None,
    )

    body = _progress_page(staff_client, record).content.decode()

    assert "Effective deadlines" in body
    assert "Reading: 14 Mar 2026, 17:00 SAST (Learner override)" in body
    assert "Course time limit end: " in body
    assert "(Content default)" in body


@pytest.mark.django_db
def test_effective_deadlines_escapes_an_author_title(
    staff_client, mock_site_context
) -> None:
    record, item = _record_with_item()
    assert item.child is not None
    type(item.child).objects.filter(pk=item.child.pk).update(
        title="<script>alert(1)</script>"
    )
    item.due_days_after_registration = 5
    item.save()

    body = _progress_page(staff_client, record).content.decode()

    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;: " in body


@pytest.mark.django_db
def test_effective_deadlines_says_so_when_there_are_none(
    staff_client, mock_site_context
) -> None:
    record, _ = _record_with_item()

    assert "No deadlines." in _progress_page(staff_client, record).content.decode()


def _progress_page_query_count(client: Client, record: CourseProgress) -> int:
    with CaptureQueriesContext(connection) as queries:
        response = _progress_page(client, record)
    assert response.status_code == 200
    return len(queries)


SITE_CONFIG_ADD = "admin:freedom_ls_deadlines_sitedeadlineconfig_add"
COURSE_CONFIG_ADD = "admin:freedom_ls_deadlines_coursedeadlineconfig_add"
INHERIT_POST = {
    "mark_overdue": "inherit",
    "close_items": "inherit",
    "end_course_access": "inherit",
    "notify_educators": "inherit",
    "grace_window": "",
    "after_access_ended": "inherit",
    "learners_may_pause": "inherit",
    "max_pauses": "",
    "max_pause_days": "",
}


@pytest.mark.django_db
def test_site_config_add_with_every_select_at_inherit_stores_inherit_and_none(
    staff_client, mock_site_context
) -> None:
    response = staff_client.post(reverse(SITE_CONFIG_ADD), INHERIT_POST)

    row = SiteDeadlineConfig.objects.get()
    assert response.status_code == 302
    assert row.close_items == "inherit"
    assert row.grace_window is None
    assert (row.max_pauses, row.max_pause_days) == (None, None)


@pytest.mark.django_db
def test_second_site_config_post_is_a_form_error_and_creates_no_row(
    staff_client, mock_site_context
) -> None:
    SiteDeadlineConfigFactory()

    response = staff_client.post(reverse(SITE_CONFIG_ADD), INHERIT_POST)

    assert response.status_code == 200
    assert response.context["adminform"].form.non_field_errors()
    assert SiteDeadlineConfig.objects.count() == 1


@pytest.mark.django_db
def test_course_config_post_for_another_sites_course_is_refused(
    staff_client, mock_site_context
) -> None:
    other_site = SiteFactory()
    with site_context(other_site):
        foreign_course = CourseFactory()

    response = staff_client.post(
        reverse(COURSE_CONFIG_ADD), {**INHERIT_POST, "course": str(foreign_course.pk)}
    )

    assert response.status_code == 200
    assert response.context["adminform"].form.errors["course"]
    assert CourseDeadlineConfig.objects.count() == 0


@pytest.mark.django_db
def test_the_course_progress_page_shows_the_layer_that_set_each_value(
    staff_client, mock_site_context
) -> None:
    record, _ = _record_with_item()
    CourseDeadlineConfigFactory(course=record.course, close_items="on")

    response = _progress_page(staff_client, record)

    content = response.content.decode()
    assert "<li>close_items: On (course)</li>" in content
    assert "<li>mark_overdue: On (settings)</li>" in content


@pytest.mark.django_db
def test_the_course_progress_add_page_renders_without_a_policy(
    staff_client, mock_site_context
) -> None:
    response = staff_client.get(
        reverse("admin:freedom_ls_learner_progress_courseprogress_add")
    )

    assert response.status_code == 200
    assert "close_items:" not in response.content.decode()


@pytest.mark.django_db
def test_the_course_progress_page_shows_when_access_ends(
    staff_client, mock_site_context
) -> None:
    SiteTimeZoneConfigFactory(time_zone="Africa/Johannesburg")
    record, _ = _record_with_item()
    Course.objects.filter(pk=record.course_id).update(time_limit_days=30)
    CourseDeadlineConfigFactory(course=record.course, end_course_access="on")

    body = _progress_page(staff_client, record).content.decode()

    assert "Access ends: " in body
    assert "SAST" in body.split("Access ends: ")[1].split("</li>")[0]


@pytest.mark.django_db
def test_the_course_progress_page_has_no_access_end_line_when_access_does_not_end(
    staff_client, mock_site_context
) -> None:
    record, _ = _record_with_item()
    Course.objects.filter(pk=record.course_id).update(time_limit_days=30)

    body = _progress_page(staff_client, record).content.decode()

    assert "Access ends" not in body


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_name",
    [
        "sitedeadlineconfig",
        "organisationdeadlineconfig",
        "coursedeadlineconfig",
        "cohortdeadlineconfig",
        "cohortcourseregistrationdeadlineconfig",
        "learnercourseregistrationdeadlineconfig",
    ],
)
def test_a_negative_grace_window_is_a_field_error_on_every_config_admin(
    staff_client, mock_site_context, model_name
) -> None:
    """A negative grace window used to surface only as the raw constraint name."""
    url = reverse(f"admin:freedom_ls_deadlines_{model_name}_add")

    response = staff_client.post(url, {**INHERIT_POST, "grace_window": "-1 00:00:00"})

    assert response.status_code == 200
    assert response.context["adminform"].form.errors["grace_window"] == [
        "The grace window cannot be negative."
    ]


@pytest.mark.django_db
def test_effective_deadlines_marks_a_shifted_deadline_with_the_days_it_moved(
    staff_client, mock_site_context
) -> None:
    SiteTimeZoneConfigFactory(time_zone="Africa/Johannesburg")
    record, item = _record_with_item()
    item.due_date = date(2026, 3, 14)
    item.save()
    CoursePauseFactory(
        course_progress=record,
        started_at=timezone.now() - timedelta(days=2, hours=1),
        ended_at=timezone.now() - timedelta(hours=1),
    )

    body = _progress_page(staff_client, record).content.decode()

    assert "(+3 days)" in body


@pytest.mark.django_db
def test_effective_deadlines_writes_a_one_day_shift_in_the_singular(
    staff_client, mock_site_context
) -> None:
    record, item = _record_with_item()
    item.due_date = date(2026, 3, 14)
    item.save()
    CoursePauseFactory(
        course_progress=record,
        started_at=timezone.now() - timedelta(hours=23),
        ended_at=timezone.now() - timedelta(hours=1),
    )

    body = _progress_page(staff_client, record).content.decode()

    assert "(+1 day)" in body
    assert "(+1 days)" not in body


@pytest.mark.django_db
def test_effective_deadlines_says_when_the_course_is_paused(
    staff_client, mock_site_context
) -> None:
    record, _ = _record_with_item()
    CoursePauseFactory(course_progress=record)

    body = _progress_page(staff_client, record).content.decode()

    assert "Paused since " in body
    assert ", until " not in body.split("Paused since ")[1].split("</p>")[0]


@pytest.mark.django_db
def test_effective_deadlines_writes_the_pause_start_in_the_site_zone(
    staff_client, mock_site_context
) -> None:
    """The pause start used to be written in UTC, the zone the database returns it in."""
    SiteTimeZoneConfigFactory(time_zone="Africa/Johannesburg")
    record, _ = _record_with_item()
    CoursePauseFactory(
        course_progress=record,
        started_at=datetime(2026, 11, 10, 23, 34, tzinfo=UTC),
    )

    body = _progress_page(staff_client, record).content.decode()

    since = body.split("Paused since ")[1].split("</p>")[0]
    assert since.startswith("11 Nov 2026, 01:34 SAST")


@pytest.mark.django_db
def test_effective_deadlines_names_the_planned_resume_of_a_paused_course(
    staff_client, mock_site_context
) -> None:
    SiteTimeZoneConfigFactory(time_zone="Africa/Johannesburg")
    record, _ = _record_with_item()
    CoursePauseFactory(course_progress=record, planned_resume_on=date(2999, 1, 5))

    body = _progress_page(staff_client, record).content.decode()

    assert (
        body.split("Paused since ")[1].split("</p>")[0].endswith(", until 5 Jan 2999")
    )


@pytest.mark.django_db
def test_the_progress_page_lists_the_records_pauses_in_the_inline(
    staff_client, mock_site_context
) -> None:
    record: CourseProgress = CourseProgressFactory()
    CoursePauseFactory(course_progress=record, reason="Medical leave")

    response = _progress_page(staff_client, record)

    assert "Medical leave" in response.content.decode()


@pytest.mark.django_db
def test_the_pause_inline_offers_no_way_to_add_change_or_delete(
    staff_client, mock_site_context
) -> None:
    record: CourseProgress = CourseProgressFactory()
    CoursePauseFactory(course_progress=record)
    response = _progress_page(staff_client, record)
    inline = next(
        i
        for i in response.context["inline_admin_formsets"]
        if i.opts.model is CoursePause
    )

    assert not inline.has_add_permission
    assert not inline.has_change_permission
    assert not inline.has_delete_permission


def _record_with_pauses(count: int) -> CourseProgress:
    record: CourseProgress = CourseProgressFactory()
    start = timezone.now() - timedelta(days=count * 3)
    for index in range(count):
        CoursePauseFactory(
            course_progress=record,
            started_at=start + timedelta(days=index * 3),
            ended_at=start + timedelta(days=index * 3 + 1),
            started_by=UserFactory(),
            ended_by=UserFactory(),
        )
    return record


@pytest.mark.django_db
def test_the_pause_inline_query_count_does_not_grow_with_pauses(
    staff_client, mock_site_context
) -> None:
    few = _record_with_pauses(1)
    many = _record_with_pauses(8)
    # The first render fills the content type cache, which would count against `many`.
    _progress_page_query_count(staff_client, few)

    assert _progress_page_query_count(staff_client, many) == _progress_page_query_count(
        staff_client, few
    )


@pytest.mark.django_db
def test_the_pause_changelist_stays_under_a_query_bound_for_many_rows(
    staff_client, mock_site_context, django_assert_max_num_queries
) -> None:
    for _ in range(12):
        CoursePauseFactory(started_by=UserFactory())
    url = reverse("admin:freedom_ls_deadlines_coursepause_changelist")

    with django_assert_max_num_queries(25):
        response = staff_client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("state", "expected"), [("paused", ["open"]), ("ended", ["ended"])]
)
def test_the_pause_changelist_filters_by_state(
    staff_client, mock_site_context, state, expected
) -> None:
    CoursePauseFactory(reason="open")
    CoursePauseFactory(reason="ended", ended_at=timezone.now())
    url = reverse("admin:freedom_ls_deadlines_coursepause_changelist")

    response = staff_client.get(url, {"state": state})

    assert [p.reason for p in response.context["cl"].result_list] == expected


@pytest.mark.django_db
def test_the_pause_admin_allows_no_add_or_delete(
    staff_client, mock_site_context
) -> None:
    pause: CoursePause = CoursePauseFactory()

    add = staff_client.get(reverse("admin:freedom_ls_deadlines_coursepause_add"))
    delete = staff_client.post(
        reverse("admin:freedom_ls_deadlines_coursepause_delete", args=[pause.pk]),
        {"post": "yes"},
    )

    assert (add.status_code, delete.status_code) == (403, 403)


@pytest.mark.django_db
def test_effective_deadlines_marks_an_extended_deadline_with_the_days_added(
    staff_client, mock_site_context
) -> None:
    record, item = _record_with_item()
    item.due_date = date(2026, 3, 14)
    item.save()
    DeadlineExtensionFactory(
        course_progress=record,
        target_kind="collection_item",
        collection_item=item,
        days=5,
    )

    body = _progress_page(staff_client, record).content.decode()

    assert "(+5 days)" in body


@pytest.mark.django_db
def test_the_progress_page_lists_the_records_extensions_read_only(
    staff_client, mock_site_context
) -> None:
    record: CourseProgress = CourseProgressFactory()
    DeadlineExtensionFactory(course_progress=record, reason="Was ill")
    response = _progress_page(staff_client, record)
    inline = next(
        i
        for i in response.context["inline_admin_formsets"]
        if i.opts.model is DeadlineExtension
    )

    assert "Was ill" in response.content.decode()
    assert not inline.has_add_permission
    assert not inline.has_change_permission
    assert not inline.has_delete_permission


@pytest.mark.django_db
def test_the_extension_changelist_stays_under_a_query_bound_for_many_rows(
    staff_client, mock_site_context, django_assert_max_num_queries
) -> None:
    for _ in range(12):
        DeadlineExtensionFactory(set_by=UserFactory())
    url = reverse("admin:freedom_ls_deadlines_deadlineextension_changelist")

    with django_assert_max_num_queries(25):
        response = staff_client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_the_extension_admin_allows_no_add_or_delete(
    staff_client, mock_site_context
) -> None:
    extension: DeadlineExtension = DeadlineExtensionFactory()

    add = staff_client.get(reverse("admin:freedom_ls_deadlines_deadlineextension_add"))
    delete = staff_client.post(
        reverse(
            "admin:freedom_ls_deadlines_deadlineextension_delete", args=[extension.pk]
        ),
        {"post": "yes"},
    )

    assert (add.status_code, delete.status_code) == (403, 403)


@pytest.mark.parametrize(
    ("field", "value", "text"),
    [
        ("max_pauses", 0, "No limit"),
        ("max_pause_days", 0, "No limit"),
        ("max_pauses", 3, "3"),
        ("max_pause_days", 30, "30"),
        ("learners_may_pause", True, "On"),
        ("learners_may_pause", False, "Off"),
    ],
)
def test_policy_value_text_renders_a_zero_limit_as_no_limit(field, value, text) -> None:
    assert _policy_value_text(field, value) == text


@pytest.mark.django_db
def test_effective_policy_lists_the_pause_settings_with_their_deciding_layer(
    staff_client, mock_site_context
) -> None:
    record, _ = _record_with_item()
    CourseDeadlineConfigFactory(course=record.course, max_pauses=2, max_pause_days=0)

    body = _progress_page(staff_client, record).content.decode()

    assert "learners_may_pause: Off (settings)" in body
    assert "max_pauses: 2 (course)" in body
    assert "max_pause_days: No limit (course)" in body


@pytest.mark.django_db
def test_the_progress_page_resolves_deadlines_once_per_record_instance(
    staff_client, mock_site_context
) -> None:
    record, _ = _record_with_item()
    CoursePauseFactory(course_progress=record)

    with CaptureQueriesContext(connection) as captured:
        _progress_page(staff_client, record)

    # The read-only fields are rendered several times from two record instances, and each
    # instance resolves the deadlines once.
    assert _queries_on(captured, CoursePause._meta.db_table) == 2
    assert _queries_on(captured, DeadlineExtension._meta.db_table) == 2


@pytest.mark.django_db
def test_a_progress_page_for_a_malformed_id_redirects_rather_than_failing(
    staff_client, mock_site_context
) -> None:
    response = staff_client.get(reverse(PROGRESS_CHANGE_URL_NAME, args=["not-a-uuid"]))

    assert response.status_code == 302


@pytest.mark.django_db
def test_the_course_progress_page_shows_deadlines_and_pauses_without_actions_or_override_inline(
    staff_client, mock_site_context
) -> None:
    record, _ = _record_with_item()
    CoursePauseFactory(course_progress=record, reason="Illness")

    response = _progress_page(staff_client, record)

    body = response.content.decode()
    inline_models = {
        inline.formset.model for inline in response.context["inline_admin_formsets"]
    }
    assert response.status_code == 200
    assert "Effective deadlines" in body
    assert CoursePause in inline_models
    assert LearnerDeadlineOverride not in inline_models
    assert response.context["actions_detail"] == []


@pytest.mark.parametrize("action", ["pause", "resume", "extend"])
def test_the_course_progress_admin_has_no_pause_resume_or_extend_url(
    action: str,
) -> None:
    with pytest.raises(NoReverseMatch):
        reverse(
            f"admin:freedom_ls_learner_progress_courseprogress_{action}",
            args=["00000000-0000-0000-0000-000000000000"],
        )
