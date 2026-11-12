from __future__ import annotations

from datetime import date, timedelta

import pytest

from django.contrib import admin
from django.db import connection
from django.http import HttpRequest
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import resolve, reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    CourseFactory,
    CoursePartChildDueDateFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePartChildDueDate,
)
from freedom_ls.content_engine.tests.helpers import collection_item_for
from freedom_ls.deadlines.admin import TIME_LIMIT_HELP, CohortDeadlineOverrideInline
from freedom_ls.deadlines.factories import (
    CohortDeadlineOverrideFactory,
    CourseDeadlineConfigFactory,
    CoursePauseFactory,
    LearnerDeadlineOverrideFactory,
    SiteDeadlineConfigFactory,
)
from freedom_ls.deadlines.models import (
    CohortDeadlineOverride,
    CourseDeadlineConfig,
    DeadlineKind,
    LearnerDeadlineOverride,
    SiteDeadlineConfig,
)
from freedom_ls.learner_management.factories import CohortCourseRegistrationFactory
from freedom_ls.learner_management.models import CohortCourseRegistration
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.site_aware_models.factories import SiteTimeZoneConfigFactory
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

CHANGE_URL_NAME = "admin:freedom_ls_learner_management_cohortcourseregistration_change"
ADD_URL_NAME = "admin:freedom_ls_learner_management_cohortcourseregistration_add"


def _registration_with_item() -> tuple[CohortCourseRegistration, ContentCollectionItem]:
    course: Course = CourseFactory()
    topic = TopicFactory()
    course.items.create(child=topic, order=0)
    registration: CohortCourseRegistration = CohortCourseRegistrationFactory(
        course=course
    )
    return registration, collection_item_for(course, topic)


def _payload(
    registration: CohortCourseRegistration, rows: list[dict[str, str]]
) -> dict[str, str]:
    payload = {
        "cohort": str(registration.cohort_id),
        "course": str(registration.course_id),
        "is_active": "on",
        "deadline_overrides-TOTAL_FORMS": str(len(rows)),
        "deadline_overrides-INITIAL_FORMS": "0",
        "deadline_overrides-MIN_NUM_FORMS": "0",
        "deadline_overrides-MAX_NUM_FORMS": "1000",
    }
    for index, row in enumerate(rows):
        payload[f"deadline_overrides-{index}-cohort_registration"] = str(
            registration.pk
        )
        for name, value in row.items():
            payload[f"deadline_overrides-{index}-{name}"] = value
    return payload


def _post(
    client: Client, registration: CohortCourseRegistration, rows: list[dict[str, str]]
):
    return client.post(
        reverse(CHANGE_URL_NAME, args=[registration.pk]), _payload(registration, rows)
    )


@pytest.mark.django_db
def test_adding_a_row_stamps_who_set_it_and_what_it_replaced(
    staff_client, mock_site_context
) -> None:
    registration, item = _registration_with_item()
    item.due_days_after_registration = 14
    item.save()

    response = _post(
        staff_client,
        registration,
        [
            {
                "collection_item": str(item.pk),
                "kind": DeadlineKind.RELATIVE,
                "due_days_after_registration": "3",
                "reason": "Late start",
            }
        ],
    )

    assert response.status_code == 302
    override = CohortDeadlineOverride.objects.get()
    assert override.set_by is not None
    assert override.set_by.is_superuser
    assert override.replaced_value == "relative:14"
    assert override.reason == "Late start"


@pytest.mark.django_db
def test_a_time_limit_row_is_added_with_an_empty_item_choice(
    staff_client, mock_site_context
) -> None:
    registration, _ = _registration_with_item()

    response = _post(
        staff_client,
        registration,
        [
            {
                "collection_item": "",
                "kind": DeadlineKind.RELATIVE,
                "due_days_after_registration": "30",
            }
        ],
    )

    assert response.status_code == 302
    assert CohortDeadlineOverride.objects.get().collection_item is None


@pytest.mark.django_db
def test_saving_an_existing_row_recomputes_what_it_replaced(
    staff_client, mock_site_context
) -> None:
    registration, item = _registration_with_item()
    override = CohortDeadlineOverrideFactory(
        cohort_registration=registration,
        collection_item=item,
        replaced_value="relative:14",
    )
    item.due_days_after_registration = 20
    item.save()
    payload = _payload(
        registration,
        [
            {
                "id": str(override.pk),
                "collection_item": str(item.pk),
                "kind": DeadlineKind.RELATIVE,
                "due_days_after_registration": "5",
            }
        ],
    )
    payload["deadline_overrides-INITIAL_FORMS"] = "1"

    response = staff_client.post(
        reverse(CHANGE_URL_NAME, args=[registration.pk]), payload
    )

    assert response.status_code == 302
    override.refresh_from_db()
    assert override.replaced_value == "relative:20"
    assert override.due_days_after_registration == 5


@pytest.mark.django_db
def test_editing_only_the_reason_keeps_what_the_row_replaced(
    staff_client, mock_site_context
) -> None:
    """Re-stamping on every save silently cleared the 'Default has changed' note."""
    registration, item = _registration_with_item()
    override = CohortDeadlineOverrideFactory(
        cohort_registration=registration,
        collection_item=item,
        replaced_value="relative:14",
    )
    item.due_days_after_registration = 20
    item.save()
    payload = _payload(
        registration,
        [
            {
                "id": str(override.pk),
                "collection_item": str(item.pk),
                "kind": DeadlineKind.RELATIVE,
                "due_days_after_registration": "14",
                "reason": "Agreed with the cohort lead",
            }
        ],
    )
    payload["deadline_overrides-INITIAL_FORMS"] = "1"

    response = staff_client.post(
        reverse(CHANGE_URL_NAME, args=[registration.pk]), payload
    )

    assert response.status_code == 302
    override.refresh_from_db()
    assert override.replaced_value == "relative:14"
    assert override.reason == "Agreed with the cohort lead"
    body = staff_client.get(
        reverse(CHANGE_URL_NAME, args=[registration.pk])
    ).content.decode()
    assert "Default has changed" in body


@pytest.mark.django_db
def test_the_picker_lists_only_the_courses_items(
    staff_client, mock_site_context
) -> None:
    registration, item = _registration_with_item()
    _, foreign_item = _registration_with_item()

    response = staff_client.get(reverse(CHANGE_URL_NAME, args=[registration.pk]))

    formset = next(
        inline.formset
        for inline in response.context["inline_admin_formsets"]
        if inline.formset.prefix == "deadline_overrides"
    )
    field = formset.empty_form.fields["collection_item"]
    assert list(field.queryset) == [item]
    assert field.empty_label == "Course time limit"
    assert item.child is not None
    assert field.label_from_instance(item) == (
        f"{item.child.title} ({item.child.file_path})"
    )
    assert foreign_item not in field.queryset


@pytest.mark.django_db
def test_the_picker_offers_nothing_on_the_add_page(
    staff_client, mock_site_context
) -> None:
    _registration_with_item()

    response = staff_client.get(reverse(ADD_URL_NAME))

    formset = next(
        inline.formset
        for inline in response.context["inline_admin_formsets"]
        if inline.formset.prefix == "deadline_overrides"
    )
    assert list(formset.empty_form.fields["collection_item"].queryset) == []


@pytest.mark.django_db
def test_an_item_of_another_course_is_refused(staff_client, mock_site_context) -> None:
    registration, _ = _registration_with_item()
    _, foreign_item = _registration_with_item()

    response = _post(
        staff_client,
        registration,
        [
            {
                "collection_item": str(foreign_item.pk),
                "kind": DeadlineKind.RELATIVE,
                "due_days_after_registration": "3",
            }
        ],
    )

    assert response.status_code == 200
    assert not CohortDeadlineOverride.objects.exists()
    assert "Select a valid choice" in response.content.decode()


@pytest.mark.django_db
def test_a_malformed_object_id_redirects_to_the_admin_index(
    staff_client, mock_site_context
) -> None:
    response = staff_client.get(
        reverse(CHANGE_URL_NAME, args=["not-a-uuid"]), follow=False
    )

    assert response.status_code == 302
    assert response.url == reverse("admin:index")


@pytest.mark.django_db
def test_the_read_only_columns_show_the_default_and_the_effective_value(
    staff_client, mock_site_context
) -> None:
    SiteTimeZoneConfigFactory(time_zone="Africa/Johannesburg")
    registration, item = _registration_with_item()
    item.due_days_after_registration = 14
    item.save()
    CohortDeadlineOverrideFactory(
        cohort_registration=registration,
        collection_item=item,
        kind=DeadlineKind.FIXED,
        due_days_after_registration=None,
        due_date="2026-03-14",
        due_time="17:00",
        replaced_value="relative:14",
    )

    body = staff_client.get(
        reverse(CHANGE_URL_NAME, args=[registration.pk])
    ).content.decode()

    assert "14 days after registration" in body
    assert "Fixed 14 Mar 2026, 17:00 SAST" in body
    assert "Default has changed" not in body


@pytest.mark.django_db
def test_the_read_only_columns_say_one_day_in_the_singular(
    staff_client, mock_site_context
) -> None:
    registration, item = _registration_with_item()
    CohortDeadlineOverrideFactory(
        cohort_registration=registration,
        collection_item=item,
        kind=DeadlineKind.RELATIVE,
        due_days_after_registration=1,
    )

    body = staff_client.get(
        reverse(CHANGE_URL_NAME, args=[registration.pk])
    ).content.decode()

    assert "1 day after registration" in body
    assert "1 days after registration" not in body


@pytest.mark.django_db
def test_the_note_appears_after_the_content_default_changes(
    staff_client, mock_site_context
) -> None:
    registration, item = _registration_with_item()
    item.due_days_after_registration = 14
    item.save()
    CohortDeadlineOverrideFactory(
        cohort_registration=registration,
        collection_item=item,
        replaced_value="relative:14",
    )
    item.due_days_after_registration = 21
    item.save()

    body = staff_client.get(
        reverse(CHANGE_URL_NAME, args=[registration.pk])
    ).content.decode()

    assert (
        "Default has changed since this override was set "
        "(was relative:14, now relative:21)"
    ) in body


def _registration_with_part_row(
    placement_days: int,
) -> tuple[CohortCourseRegistration, ContentCollectionItem, ContentCollectionItem]:
    """A registration whose course places a part holding one topic row with a file value of
    14 days. Returns the registration, the part placement and the topic row."""
    course: Course = CourseFactory()
    part = CoursePartFactory()
    placement = course.items.create(child=part, order=0)
    row = part.items.create(
        child=TopicFactory(), order=0, due_days_after_registration=14
    )
    CoursePartChildDueDateFactory(
        part_collection_item=placement,
        collection_item=row,
        due_days_after_registration=placement_days,
    )
    registration: CohortCourseRegistration = CohortCourseRegistrationFactory(
        course=course
    )
    return registration, placement, row


def _registration_with_two_part_rows() -> tuple[
    CohortCourseRegistration, list[ContentCollectionItem]
]:
    """A registration whose course places a part holding two topic rows, each given a
    placement value."""
    course: Course = CourseFactory()
    part = CoursePartFactory()
    placement = course.items.create(child=part, order=0)
    rows: list[ContentCollectionItem] = []
    for order in range(2):
        row = part.items.create(child=TopicFactory(), order=order)
        CoursePartChildDueDateFactory(
            part_collection_item=placement,
            collection_item=row,
            due_days_after_registration=3 + order,
        )
        rows.append(row)
    registration: CohortCourseRegistration = CohortCourseRegistrationFactory(
        course=course
    )
    return registration, rows


def _queries_on(captured: CaptureQueriesContext, table: str) -> int:
    return sum(1 for query in captured.captured_queries if table in query["sql"])


@pytest.mark.django_db
def test_saving_several_rows_reads_the_placement_values_once(
    staff_client, mock_site_context
) -> None:
    registration, rows = _registration_with_two_part_rows()
    table = CoursePartChildDueDate._meta.db_table

    with CaptureQueriesContext(connection) as captured:
        response = _post(
            staff_client,
            registration,
            [
                {
                    "collection_item": str(row.pk),
                    "kind": DeadlineKind.RELATIVE,
                    "due_days_after_registration": "9",
                }
                for row in rows
            ],
        )

    assert response.status_code == 302
    assert _queries_on(captured, table) == 1
    assert sorted(
        CohortDeadlineOverride.objects.values_list("replaced_value", flat=True)
    ) == ["relative:3", "relative:4"]


def _change_request(registration: CohortCourseRegistration) -> HttpRequest:
    url = reverse(CHANGE_URL_NAME, args=[registration.pk])
    request = RequestFactory().get(url)
    request.resolver_match = resolve(url)
    request.user = UserFactory(superuser=True)
    return request


@pytest.mark.django_db
def test_the_columns_read_the_placement_values_once_without_the_formset(
    mock_site_context,
) -> None:
    """A column rendered before the formset is built reads the course's defaults once,
    not once per row."""
    registration, rows = _registration_with_two_part_rows()
    overrides = [
        CohortDeadlineOverrideFactory(
            cohort_registration=registration,
            collection_item=row,
            due_days_after_registration=9,
        )
        for row in rows
    ]
    inline = CohortDeadlineOverrideInline(CohortCourseRegistration, admin.site)

    with CaptureQueriesContext(connection) as captured:
        shown = [inline.content_default(override) for override in overrides]

    assert shown == ["3 days after registration", "4 days after registration"]
    assert _queries_on(captured, CoursePartChildDueDate._meta.db_table) == 1


@pytest.mark.django_db
def test_the_inline_reads_the_parent_course_once_per_request(
    mock_site_context, django_assert_num_queries
) -> None:
    registration, _ = _registration_with_two_part_rows()
    inline = CohortDeadlineOverrideInline(CohortCourseRegistration, admin.site)
    request = _change_request(registration)

    with django_assert_num_queries(1):
        first = inline.parent_course(request)
        second = inline.parent_course(request)

    assert first == registration.course
    assert second is first


@pytest.mark.django_db
def test_building_the_formset_reads_the_parent_once(mock_site_context) -> None:
    registration, _ = _registration_with_two_part_rows()
    inline = CohortDeadlineOverrideInline(CohortCourseRegistration, admin.site)
    request = _change_request(registration)
    # The admin hands the inline the parent it loaded without its course.
    parent = CohortCourseRegistration.objects.get(pk=registration.pk)

    with CaptureQueriesContext(connection) as captured:
        inline.get_formset(request, parent)

    assert _queries_on(captured, CohortCourseRegistration._meta.db_table) == 1


@pytest.mark.django_db
def test_the_content_default_shows_the_placement_value(
    staff_client, mock_site_context
) -> None:
    registration, _, row = _registration_with_part_row(placement_days=3)
    CohortDeadlineOverrideFactory(
        cohort_registration=registration,
        collection_item=row,
        due_days_after_registration=9,
        replaced_value="relative:3",
    )

    body = staff_client.get(
        reverse(CHANGE_URL_NAME, args=[registration.pk])
    ).content.decode()

    assert "3 days after registration" in body
    assert "14 days after registration" not in body
    assert "Default has changed" not in body


@pytest.mark.django_db
def test_the_note_appears_after_the_placement_value_changes(
    staff_client, mock_site_context
) -> None:
    registration, _, row = _registration_with_part_row(placement_days=3)
    CohortDeadlineOverrideFactory(
        cohort_registration=registration,
        collection_item=row,
        replaced_value="relative:14",
    )

    body = staff_client.get(
        reverse(CHANGE_URL_NAME, args=[registration.pk])
    ).content.decode()

    assert (
        "Default has changed since this override was set "
        "(was relative:14, now relative:3)"
    ) in body


@pytest.mark.django_db
def test_a_refused_new_row_has_no_note(staff_client, mock_site_context) -> None:
    """A refused new row used to read 'Default has changed since this override was set
    (was nothing, now fixed:2024-01-31)', though it was never saved."""
    registration, item = _registration_with_item()
    item.due_date = "2024-01-31"
    item.save()
    CohortDeadlineOverrideFactory(
        cohort_registration=registration,
        collection_item=item,
        replaced_value="fixed:2024-01-31",
    )

    response = _post(
        staff_client,
        registration,
        [
            {
                "collection_item": str(item.pk),
                "kind": DeadlineKind.RELATIVE,
                "due_days_after_registration": "3",
            }
        ],
    )

    content = response.content.decode()
    assert READABLE_DUPLICATE in content
    assert "Default has changed" not in content


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
def test_the_course_progress_page_has_the_learner_override_inline(
    staff_client, mock_site_context
) -> None:
    record, _ = _record_with_item()

    response = _progress_page(staff_client, record)

    assert response.status_code == 200
    inline_models = {
        inline.formset.model for inline in response.context["inline_admin_formsets"]
    }
    assert LearnerDeadlineOverride in inline_models


@pytest.mark.django_db
def test_the_course_progress_page_stamps_a_new_learner_row(
    staff_client, mock_site_context
) -> None:
    record, item = _record_with_item()
    item.due_days_after_registration = 14
    item.save()
    page = _progress_page(staff_client, record)
    formset = next(
        inline.formset
        for inline in page.context["inline_admin_formsets"]
        if inline.formset.prefix == "deadline_overrides"
    )
    # Reuse the rendered form's initial data so unrelated fields post unchanged.
    form = page.context["adminform"].form
    payload = {
        name: ("" if value is None else str(value))
        for name, value in form.initial.items()
        if value is not None
    }
    for field_name in ("topic_progress", "form_attempts"):
        payload.setdefault(f"{field_name}-TOTAL_FORMS", "0")
    for inline in page.context["inline_admin_formsets"]:
        prefix = inline.formset.prefix
        payload[f"{prefix}-TOTAL_FORMS"] = "0"
        payload[f"{prefix}-INITIAL_FORMS"] = "0"
        payload[f"{prefix}-MIN_NUM_FORMS"] = "0"
        payload[f"{prefix}-MAX_NUM_FORMS"] = "1000"
    payload["deadline_overrides-TOTAL_FORMS"] = "1"
    payload["deadline_overrides-0-course_progress"] = str(record.pk)
    payload["deadline_overrides-0-collection_item"] = str(item.pk)
    payload["deadline_overrides-0-kind"] = DeadlineKind.RELATIVE
    payload["deadline_overrides-0-due_days_after_registration"] = "3"
    assert formset.prefix == "deadline_overrides"

    response = staff_client.post(
        reverse(PROGRESS_CHANGE_URL_NAME, args=[record.pk]), payload
    )

    assert response.status_code == 302
    override = LearnerDeadlineOverride.objects.get()
    assert override.set_by is not None
    assert override.replaced_value == "relative:14"


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


READABLE_DUPLICATE = "already has an override here"


def _learner_post(client: Client, record: CourseProgress, rows: list[dict[str, str]]):
    """Post the course progress page with new learner override rows."""
    page = _progress_page(client, record)
    form = page.context["adminform"].form
    payload = {
        name: str(value) for name, value in form.initial.items() if value is not None
    }
    for inline in page.context["inline_admin_formsets"]:
        prefix = inline.formset.prefix
        payload[f"{prefix}-TOTAL_FORMS"] = "0"
        payload[f"{prefix}-INITIAL_FORMS"] = "0"
        payload[f"{prefix}-MIN_NUM_FORMS"] = "0"
        payload[f"{prefix}-MAX_NUM_FORMS"] = "1000"
    payload["deadline_overrides-TOTAL_FORMS"] = str(len(rows))
    for index, row in enumerate(rows):
        payload[f"deadline_overrides-{index}-course_progress"] = str(record.pk)
        for name, value in row.items():
            payload[f"deadline_overrides-{index}-{name}"] = value
    return client.post(reverse(PROGRESS_CHANGE_URL_NAME, args=[record.pk]), payload)


@pytest.mark.django_db
@pytest.mark.parametrize("with_item", [True, False], ids=["item", "time_limit"])
def test_a_second_cohort_override_for_the_same_target_reads_plainly(
    staff_client, mock_site_context, with_item: bool
) -> None:
    """A duplicate row used to show 'Constraint “unique_cohort_override_per_item” is violated.'"""
    registration, item = _registration_with_item()
    target = item if with_item else None
    CohortDeadlineOverrideFactory(
        cohort_registration=registration, collection_item=target
    )

    response = _post(
        staff_client,
        registration,
        [
            {
                "collection_item": str(item.pk) if with_item else "",
                "kind": DeadlineKind.RELATIVE,
                "due_days_after_registration": "3",
            }
        ],
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert READABLE_DUPLICATE in content
    assert "unique_cohort" not in content
    assert CohortDeadlineOverride.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("with_item", [True, False], ids=["item", "time_limit"])
def test_a_second_learner_override_for_the_same_target_reads_plainly(
    staff_client, mock_site_context, with_item: bool
) -> None:
    """A duplicate row used to show 'Constraint “unique_learner_override_per_item” is violated.'"""
    record, item = _record_with_item()
    target = item if with_item else None
    LearnerDeadlineOverrideFactory(course_progress=record, collection_item=target)

    response = _learner_post(
        staff_client,
        record,
        [
            {
                "collection_item": str(item.pk) if with_item else "",
                "kind": DeadlineKind.RELATIVE,
                "due_days_after_registration": "3",
            }
        ],
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert READABLE_DUPLICATE in content
    assert "unique_learner" not in content
    assert LearnerDeadlineOverride.objects.count() == 1


def _two_rows_for(target: ContentCollectionItem | None) -> list[dict[str, str]]:
    row = {
        "collection_item": str(target.pk) if target is not None else "",
        "kind": DeadlineKind.RELATIVE,
        "due_days_after_registration": "3",
    }
    return [row, {**row, "due_days_after_registration": "5"}]


@pytest.mark.django_db
@pytest.mark.parametrize("with_item", [True, False], ids=["item", "time_limit"])
def test_two_new_cohort_rows_for_the_same_target_are_refused_as_one_form_error(
    staff_client, mock_site_context, with_item: bool
) -> None:
    """The unique constraints are conditional, so the formset's own uniqueness check
    skips them and two new rows for one target used to reach the database as a 500."""
    registration, item = _registration_with_item()

    response = _post(
        staff_client, registration, _two_rows_for(item if with_item else None)
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert READABLE_DUPLICATE in content
    assert "unique_cohort" not in content
    assert CohortDeadlineOverride.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("with_item", [True, False], ids=["item", "time_limit"])
def test_two_new_learner_rows_for_the_same_target_are_refused_as_one_form_error(
    staff_client, mock_site_context, with_item: bool
) -> None:
    record, item = _record_with_item()

    response = _learner_post(
        staff_client, record, _two_rows_for(item if with_item else None)
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert READABLE_DUPLICATE in content
    assert "unique_learner" not in content
    assert LearnerDeadlineOverride.objects.count() == 0


@pytest.mark.django_db
def test_an_item_row_and_a_time_limit_row_can_be_added_together(
    staff_client, mock_site_context
) -> None:
    registration, item = _registration_with_item()
    row = {"kind": DeadlineKind.RELATIVE, "due_days_after_registration": "3"}

    response = _post(
        staff_client,
        registration,
        [{**row, "collection_item": str(item.pk)}, {**row, "collection_item": ""}],
    )

    assert response.status_code == 302
    assert CohortDeadlineOverride.objects.count() == 2


def _registration_with_overrides(
    item_count: int, override_count: int
) -> CohortCourseRegistration:
    course: Course = CourseFactory()
    part = CoursePartFactory()
    part_placement = course.items.create(child=part, order=0)
    items = []
    for order in range(item_count):
        row = part.items.create(child=TopicFactory(), order=order)
        if order % 2 == 0:
            CoursePartChildDueDateFactory(
                part_collection_item=part_placement, collection_item=row
            )
        items.append(row)
    registration: CohortCourseRegistration = CohortCourseRegistrationFactory(
        course=course
    )
    for item in items[:override_count]:
        CohortDeadlineOverrideFactory(
            cohort_registration=registration, collection_item=item
        )
    return registration


def _change_page_query_count(
    client: Client, registration: CohortCourseRegistration
) -> int:
    with CaptureQueriesContext(connection) as queries:
        response = client.get(reverse(CHANGE_URL_NAME, args=[registration.pk]))
    assert response.status_code == 200
    return len(queries)


@pytest.mark.django_db
def test_the_change_page_query_count_does_not_grow_with_items_or_rows(
    staff_client, mock_site_context
) -> None:
    """The picker read each item's child, and each row's read-only columns read the
    row's item, parent course and site, one query at a time."""
    small = _registration_with_overrides(item_count=4, override_count=1)
    large = _registration_with_overrides(item_count=24, override_count=6)
    _change_page_query_count(staff_client, small)

    assert _change_page_query_count(staff_client, large) == _change_page_query_count(
        staff_client, small
    )


def _cohort_record_with_overrides(
    item_count: int, override_count: int
) -> CourseProgress:
    """A cohort-granted record with a cohort and a learner override on the same items."""
    registration = _registration_with_overrides(item_count, override_count)
    record: CourseProgress = CourseProgressFactory(
        course=registration.course,
        cohort_registration=registration,
        learner_registration=None,
    )
    for row in CohortDeadlineOverride.objects.filter(cohort_registration=registration):
        LearnerDeadlineOverrideFactory(
            course_progress=record, collection_item=row.collection_item
        )
    return record


def _progress_page_query_count(client: Client, record: CourseProgress) -> int:
    with CaptureQueriesContext(connection) as queries:
        response = _progress_page(client, record)
    assert response.status_code == 200
    return len(queries)


@pytest.mark.django_db
def test_the_course_progress_page_query_count_does_not_grow_with_learner_rows(
    staff_client, mock_site_context
) -> None:
    """Each learner row's "Default changed" column read the cohort row beneath it one
    query at a time."""
    small = _cohort_record_with_overrides(item_count=4, override_count=1)
    large = _cohort_record_with_overrides(item_count=24, override_count=6)
    _progress_page_query_count(staff_client, small)

    assert _progress_page_query_count(
        staff_client, large
    ) == _progress_page_query_count(staff_client, small)


SITE_CONFIG_ADD = "admin:freedom_ls_deadlines_sitedeadlineconfig_add"
COURSE_CONFIG_ADD = "admin:freedom_ls_deadlines_coursedeadlineconfig_add"
INHERIT_POST = {
    "mark_overdue": "inherit",
    "close_items": "inherit",
    "end_course_access": "inherit",
    "notify_educators": "inherit",
    "grace_window": "",
    "after_access_ended": "inherit",
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
def test_a_cohort_fixed_date_time_limit_row_is_accepted(
    staff_client, mock_site_context
) -> None:
    registration, _ = _registration_with_item()

    response = _post(
        staff_client,
        registration,
        [
            {
                "collection_item": "",
                "kind": DeadlineKind.FIXED,
                "due_date": "2026-03-01",
            }
        ],
    )

    row = CohortDeadlineOverride.objects.get()
    assert response.status_code == 302
    assert row.collection_item_id is None
    assert row.due_date == date(2026, 3, 1)


@pytest.mark.django_db
def test_a_learner_fixed_date_time_limit_row_is_accepted(
    staff_client, mock_site_context
) -> None:
    record, _ = _record_with_item()

    response = _learner_post(
        staff_client,
        record,
        [
            {
                "collection_item": "",
                "kind": DeadlineKind.FIXED,
                "due_date": "2026-03-01",
            }
        ],
    )

    row = LearnerDeadlineOverride.objects.get()
    assert response.status_code == 302
    assert row.collection_item_id is None
    assert row.due_date == date(2026, 3, 1)


@pytest.mark.django_db
def test_the_override_inline_explains_that_a_time_limit_row_restores_ended_access(
    staff_client, mock_site_context
) -> None:
    registration, _ = _registration_with_item()

    page = staff_client.get(reverse(CHANGE_URL_NAME, args=[registration.pk]))

    assert TIME_LIMIT_HELP in page.content.decode()


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
def test_effective_deadlines_says_when_the_course_is_paused(
    staff_client, mock_site_context
) -> None:
    record, _ = _record_with_item()
    CoursePauseFactory(course_progress=record)

    body = _progress_page(staff_client, record).content.decode()

    assert "Paused since " in body
    assert ", until " not in body.split("Paused since ")[1].split("</p>")[0]


@pytest.mark.django_db
def test_effective_deadlines_names_the_planned_resume_of_a_paused_course(
    staff_client, mock_site_context
) -> None:
    record, _ = _record_with_item()
    CoursePauseFactory(
        course_progress=record,
        planned_resume_on=(timezone.now() + timedelta(days=5)).date(),
    )

    body = _progress_page(staff_client, record).content.decode()

    assert ", until " in body.split("Paused since ")[1].split("</p>")[0]
