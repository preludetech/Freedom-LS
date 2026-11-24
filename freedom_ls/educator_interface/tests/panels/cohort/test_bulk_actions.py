"""The bulk actions over the cohorts table."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks
from pytest_mock import MockerFixture

from django.contrib.sites.models import Site
from django.test import Client

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.educator_interface.panels.cohort.bulk_actions import (
    CohortCourseBulkAction,
    DeactivateCohortRegistrationBulkAction,
    RegisterCohortForCourseBulkAction,
)
from freedom_ls.educator_interface.tests.helpers import (
    _bulk_text,
    _cohort_admin_on,
    _cohort_url,
    _course_option_values,
    _get_document,
    _interface_url,
    _post,
    _scoped_request,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.bulk_actions import (
    BulkCount,
    BulkOutcome,
    run_apply,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse


def _cohorts_bulk_post(
    client: Client,
    organisation: Organisation,
    action_name: str,
    cohorts: list[Cohort],
    **extra: str,
) -> _MonkeyPatchedWSGIResponse:
    return client.post(
        _interface_url(organisation.slug, f"cohorts/__actions/{action_name}"),
        {"keys": [str(cohort.pk) for cohort in cohorts], **extra},
        HTTP_HX_REQUEST="true",
    )


def _cohorts_bulk_confirm(
    client: Client,
    organisation: Organisation,
    action_name: str,
    cohorts: list[Cohort],
    **extra: str,
) -> _MonkeyPatchedWSGIResponse:
    return _cohorts_bulk_post(
        client,
        organisation,
        action_name,
        cohorts,
        confirmed="on",
        expected_count=str(len(cohorts)),
        **extra,
    )


def _bulk_cohort(organisation: Organisation, **fields: object) -> Cohort:
    return cast(Cohort, CohortFactory(organisation=organisation, **fields))


@pytest.mark.django_db
def test_cohort_state_action_deactivates_through_the_service(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = _bulk_cohort(organisation)

    _post(staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate"))

    cohort.refresh_from_db()
    assert cohort.is_active is False


@pytest.mark.django_db
def test_cohort_state_action_reactivates_through_the_service(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = _bulk_cohort(organisation, is_active=False)

    _post(staff_client, _cohort_url(organisation, cohort, "/__actions/reactivate"))

    cohort.refresh_from_db()
    assert cohort.is_active is True


@pytest.mark.django_db
def test_bulk_cohort_deactivate_confirmation_counts_changes_and_skips(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    active = [_bulk_cohort(organisation) for _ in range(2)]
    inactive = _bulk_cohort(organisation, is_active=False)

    response = _cohorts_bulk_post(
        staff_client, organisation, "deactivate", [*active, inactive]
    )

    text = _bulk_text(response)
    assert "Deactivate 2 cohorts." in text
    assert "1 is already inactive and will be skipped." in text


@pytest.mark.django_db
def test_bulk_cohort_deactivate_changes_only_active_cohorts(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    active = [_bulk_cohort(organisation) for _ in range(2)]
    inactive = _bulk_cohort(organisation, is_active=False)

    response = _cohorts_bulk_confirm(
        staff_client, organisation, "deactivate", [*active, inactive]
    )

    assert "2 cohorts changed." in _bulk_text(response)
    assert (
        Cohort.objects.filter(organisation=organisation, is_active=False).count() == 3
    )


@pytest.mark.django_db
def test_bulk_cohort_reactivate_confirmation_counts_changes_and_skips(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    inactive = _bulk_cohort(organisation, is_active=False)
    active = _bulk_cohort(organisation)

    response = _cohorts_bulk_post(
        staff_client, organisation, "reactivate", [inactive, active]
    )

    text = _bulk_text(response)
    assert "Reactivate 1 cohort." in text
    assert "It gives access to its courses again." in text
    assert "1 is already active and will be skipped." in text


@pytest.mark.django_db
def test_bulk_cohort_reactivate_activates_inactive_cohorts(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    inactive = _bulk_cohort(organisation, is_active=False)

    _cohorts_bulk_confirm(staff_client, organisation, "reactivate", [inactive])

    inactive.refresh_from_db()
    assert inactive.is_active is True


@pytest.mark.django_db
def test_the_cohort_register_picker_offers_only_registerable_courses(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    published = CourseFactory(visibility=CourseVisibility.PUBLISHED)
    CourseFactory(visibility=CourseVisibility.COMING_SOON)
    cohort = _bulk_cohort(organisation)

    response = _cohorts_bulk_post(staff_client, organisation, "register", [cohort])

    assert response.status_code == 200
    assert _course_option_values(response) == {str(published.pk)}


@pytest.mark.django_db
def test_bulk_cohort_register_confirmation_counts_changes_and_skips(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory(title="Algebra")
    registered = _bulk_cohort(organisation)
    fresh = _bulk_cohort(organisation)
    inactive = _bulk_cohort(organisation, is_active=False)
    CohortCourseRegistrationFactory(cohort=registered, course=course)

    response = _cohorts_bulk_post(
        staff_client,
        organisation,
        "register",
        [registered, fresh, inactive],
        refresh="1",
        course=str(course.pk),
    )

    text = _bulk_text(response)
    assert "Register 1 cohort for Algebra." in text
    assert "1 is already registered and will be skipped." in text
    assert "1 is inactive and will be skipped." in text


@pytest.mark.django_db
def test_bulk_cohort_register_registers_only_unregistered_active_cohorts(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    registered = _bulk_cohort(organisation)
    fresh = _bulk_cohort(organisation)
    inactive = _bulk_cohort(organisation, is_active=False)
    CohortCourseRegistrationFactory(cohort=registered, course=course)

    response = _cohorts_bulk_confirm(
        staff_client,
        organisation,
        "register",
        [registered, fresh, inactive],
        course=str(course.pk),
    )

    assert "1 cohort changed." in _bulk_text(response)
    assert CohortCourseRegistration.objects.filter(
        cohort=fresh, course=course, is_active=True
    ).exists()
    assert not CohortCourseRegistration.objects.filter(cohort=inactive).exists()


@pytest.mark.django_db
def test_bulk_cohort_register_refreshed_without_a_course_answers_200(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = _bulk_cohort(organisation)

    response = _cohorts_bulk_post(
        staff_client, organisation, "register", [cohort], refresh="1"
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_bulk_cohort_register_fires_one_course_registered_event_per_changed_cohort(
    staff_client: Client,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    mocker: MockerFixture,
) -> None:
    fire = mocker.patch("freedom_ls.webhooks.events.fire_webhook_event_for_site")
    organisation = OrganisationFactory()
    course = CourseFactory()
    registered = _bulk_cohort(organisation)
    fresh = [_bulk_cohort(organisation) for _ in range(2)]
    CohortCourseRegistrationFactory(cohort=registered, course=course)

    with django_capture_on_commit_callbacks(execute=True):
        _cohorts_bulk_confirm(
            staff_client,
            organisation,
            "register",
            [registered, *fresh],
            course=str(course.pk),
        )

    fired = [(call.args[0], call.args[1]["cohort_id"]) for call in fire.call_args_list]
    assert sorted(fired) == sorted(
        ("cohort_registration.added", str(cohort.pk)) for cohort in fresh
    )


@pytest.mark.django_db
def test_a_cohort_admin_registers_only_their_own_cohorts(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    mine = _bulk_cohort(organisation)
    theirs = _bulk_cohort(organisation)
    educator = _cohort_admin_on(organisation, mine)
    course = CourseFactory()

    outcomes = RegisterCohortForCourseBulkAction().classify_all(
        _scoped_request(educator, organisation),
        Cohort.objects.filter(pk__in=[mine.pk, theirs.pk]),
        {"course": course},
    )

    assert outcomes == {
        str(mine.pk): BulkOutcome("changed"),
        str(theirs.pk): BulkOutcome(
            "skipped", "cohorts you don't have permission to change"
        ),
    }


@pytest.mark.django_db
def test_an_inactive_cohort_the_educator_cannot_change_is_skipped_for_permission_first(
    mock_site_context: Site,
) -> None:
    """The preview checks permission before state; the run must agree."""
    organisation = OrganisationFactory()
    mine = _bulk_cohort(organisation)
    theirs = _bulk_cohort(organisation, is_active=False)
    educator = _cohort_admin_on(organisation, mine)
    course = CourseFactory()
    action = RegisterCohortForCourseBulkAction()
    queryset = Cohort.objects.filter(pk__in=[theirs.pk])

    previewed = action.classify_all(
        _scoped_request(educator, organisation), queryset, {"course": course}
    )
    result = run_apply(action, educator, organisation, queryset, {"course": course})

    not_permitted = "cohorts you don't have permission to change"
    assert previewed == {str(theirs.pk): BulkOutcome("skipped", not_permitted)}
    assert result.counts == [BulkCount("skipped", not_permitted, 1)]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action_class",
    [RegisterCohortForCourseBulkAction, DeactivateCohortRegistrationBulkAction],
)
def test_run_skips_a_cohort_that_was_already_inactive_rather_than_failing_it(
    mock_site_context: Site, action_class: type[CohortCourseBulkAction]
) -> None:
    """An inactive cohort was reported as "could not be changed" at the end of
    the run, though the confirmation had promised to skip it."""
    organisation = OrganisationFactory()
    inactive = _bulk_cohort(organisation, is_active=False)
    educator = _cohort_admin_on(organisation, inactive)

    result = run_apply(
        action_class(),
        educator,
        organisation,
        Cohort._base_manager.filter(pk=inactive.pk),
        {"course": CourseFactory()},
    )

    assert result.counts == [BulkCount("skipped", "inactive", 1)]
    assert result.entries == []


@pytest.mark.django_db
def test_bulk_cohort_unregister_confirmation_counts_changes_and_skips(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory(title="Algebra")
    registered = _bulk_cohort(organisation)
    without_registration = _bulk_cohort(organisation)
    inactive = _bulk_cohort(organisation, is_active=False)
    CohortCourseRegistrationFactory(cohort=registered, course=course)

    response = _cohorts_bulk_post(
        staff_client,
        organisation,
        "deactivate_cohort_registration",
        [registered, without_registration, inactive],
        refresh="1",
        course=str(course.pk),
    )

    text = _bulk_text(response)
    assert "Deactivate the Algebra registration for 1 cohort." in text
    assert "1 is not registered and will be skipped." in text
    assert "1 is inactive and will be skipped." in text


@pytest.mark.django_db
def test_bulk_cohort_unregister_deactivates_the_active_registration(
    staff_client: Client,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    mocker: MockerFixture,
) -> None:
    fire = mocker.patch("freedom_ls.webhooks.events.fire_webhook_event_for_site")
    organisation = OrganisationFactory()
    course = CourseFactory()
    registered = _bulk_cohort(organisation)
    other = _bulk_cohort(organisation)
    registration = CohortCourseRegistrationFactory(cohort=registered, course=course)

    with django_capture_on_commit_callbacks(execute=True):
        response = _cohorts_bulk_confirm(
            staff_client,
            organisation,
            "deactivate_cohort_registration",
            [registered, other],
            course=str(course.pk),
        )

    registration.refresh_from_db()
    assert "1 cohort changed." in _bulk_text(response)
    assert registration.is_active is False
    assert [call.args[0] for call in fire.call_args_list] == [
        "cohort_registration.deactivated"
    ]


@pytest.mark.django_db
def test_the_cohorts_bar_promotes_all_four_actions_and_has_no_more_menu(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation)

    document = _get_document(staff_client, _interface_url(organisation.slug, "cohorts"))

    def labels(selector: str) -> list[str]:
        return [
            " ".join(element.text_content().split())
            for element in document.cssselect(selector)
        ]

    assert labels("div[data-total-count] > div > fieldset > button[formaction]") == [
        "Register for a course",
        "Deactivate a course registration",
        "Deactivate",
        "Reactivate",
    ]
    assert labels("[role='menu'] button[formaction]") == []
