from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.content_engine.tests.helpers import collection_item_for
from freedom_ls.deadlines.admin import site_zone_text
from freedom_ls.deadlines.factories import CohortDeadlineOverrideFactory
from freedom_ls.deadlines.models import CohortDeadlineOverride, DeadlineKind
from freedom_ls.learner_management.factories import CohortCourseRegistrationFactory
from freedom_ls.learner_management.models import CohortCourseRegistration
from freedom_ls.site_aware_models.factories import SiteTimeZoneConfigFactory

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
def test_a_malformed_object_id_is_the_admins_404(
    staff_client, mock_site_context
) -> None:
    response = staff_client.get(
        reverse(CHANGE_URL_NAME, args=["not-a-uuid"]), follow=False
    )

    assert response.status_code in (302, 404)
    if response.status_code == 302:
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


def test_site_zone_text_names_the_zone() -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    instant = datetime(2026, 3, 14, 17, 0, tzinfo=ZoneInfo("Africa/Johannesburg"))

    assert site_zone_text(instant) == "14 Mar 2026, 17:00 SAST"
