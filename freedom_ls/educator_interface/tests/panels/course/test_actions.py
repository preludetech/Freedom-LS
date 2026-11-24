"""The actions on a course's Overview tab."""

from __future__ import annotations

import json

import lxml.html
import pytest

from django.db import connection
from django.test.utils import CaptureQueriesContext

from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.events import COHORT_CHANGED, REGISTRATION_CHANGED
from freedom_ls.educator_interface.tests.helpers import (
    RoleHolderClient,
    _get_document,
    _interface_url,
    _post,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.learner_management.models import Cohort, CohortCourseRegistration
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation

OVERVIEW = "__tabs/overview/__panels/cohorts"


def _page_url(organisation: Organisation, course: Course) -> str:
    return _interface_url(organisation.slug, f"courses/{course.pk}")


def _action_url(
    organisation: Organisation, course: Course, registration_pk: object = None
) -> str:
    url = _interface_url(
        organisation.slug,
        f"courses/{course.pk}/{OVERVIEW}/__actions/deactivate_cohort_registration",
    )
    return url if registration_pk is None else f"{url}?registration={registration_pk}"


def _deactivate_buttons(document: lxml.html.HtmlElement) -> list[str]:
    """The distinct aria-labels of the Deactivate triggers in the Cohort
    registrations panel. The table renders each row for wide and narrow
    screens, so a row's trigger appears more than once."""
    (panel,) = document.cssselect("section[data-panel='cohorts']")
    return sorted(
        {
            button.get("aria-label")
            for button in panel.cssselect("button")
            if button.text_content().strip() == "Deactivate"
        }
    )


def _register(organisation: Organisation, course: Course, **cohort_fields: object):
    cohort = CohortFactory(organisation=organisation, **cohort_fields)
    return cohort, CohortCourseRegistrationFactory(cohort=cohort, course=course)


@pytest.mark.django_db
def test_an_organisation_admin_sees_deactivate_on_an_active_row_of_an_active_cohort(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    _register(organisation, course, name="Cohort A")
    client = role_holder_client(organisation)

    document = _get_document(client, _page_url(organisation, course))

    assert _deactivate_buttons(document) == ["Deactivate Cohort A"]


@pytest.mark.django_db
def test_no_deactivate_on_an_inactive_registration(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    cohort = CohortFactory(organisation=organisation)
    CohortCourseRegistrationFactory(cohort=cohort, course=course, is_active=False)
    client = role_holder_client(organisation)

    document = _get_document(client, _page_url(organisation, course))

    assert _deactivate_buttons(document) == []


@pytest.mark.django_db
def test_no_deactivate_on_an_active_registration_of_an_inactive_cohort(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    _register(organisation, course, is_active=False)
    client = role_holder_client(organisation)

    document = _get_document(client, _page_url(organisation, course))

    assert _deactivate_buttons(document) == []


@pytest.mark.django_db
def test_the_confirmation_names_the_cohort_course_and_who_loses_access(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory(title="Algebra")
    cohort, registration = _register(organisation, course, name="Cohort A")
    CohortMembershipFactory(cohort=cohort)
    client = role_holder_client(organisation)

    response = client.get(
        _action_url(organisation, course, registration.pk), HTTP_HX_REQUEST="true"
    )

    text = " ".join(
        lxml.html.fromstring(response.content.decode()).text_content().split()
    )
    assert response.status_code == 200
    assert "Deactivate Cohort A's registration for Algebra" in text
    assert "1 learner" in text


@pytest.mark.django_db
def test_a_post_deactivates_the_registration_and_fires_both_events(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    cohort, registration = _register(organisation, course)
    client = role_holder_client(organisation)

    response = _post(
        client,
        _action_url(organisation, course),
        {"registration": str(registration.pk), "reason": "Course retired"},
    )

    registration.refresh_from_db()
    assert response.status_code == 204
    assert registration.is_active is False
    trigger = json.loads(response["HX-Trigger"])
    assert trigger[REGISTRATION_CHANGED] == {"ids": [str(registration.pk)]}
    assert trigger[COHORT_CHANGED] == {"ids": [str(cohort.pk)]}
    entry = AuditLogEntry.unscoped.get(reason="Course retired")
    assert entry.action == "cohort_registration.deactivated"
    assert entry.target_object_id == str(cohort.pk)


@pytest.mark.django_db
def test_a_post_for_a_cohort_deactivated_after_render_is_422_and_changes_nothing(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    cohort, registration = _register(organisation, course)
    client = role_holder_client(organisation)
    Cohort.objects.filter(pk=cohort.pk).update(is_active=False)

    response = _post(
        client,
        _action_url(organisation, course),
        {"registration": str(registration.pk), "reason": "Course retired"},
    )

    registration.refresh_from_db()
    assert response.status_code == 422
    assert registration.is_active is True


@pytest.mark.django_db
@pytest.mark.parametrize("case", ["inactive", "other course", "other organisation"])
def test_a_registration_outside_the_actions_scope_is_a_404(
    role_holder_client: RoleHolderClient, case: str
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    client = role_holder_client(organisation)
    if case == "inactive":
        registration = CohortCourseRegistrationFactory(
            cohort=CohortFactory(organisation=organisation),
            course=course,
            is_active=False,
        )
    elif case == "other course":
        registration = CohortCourseRegistrationFactory(
            cohort=CohortFactory(organisation=organisation), course=CourseFactory()
        )
    else:
        registration = CohortCourseRegistrationFactory(
            cohort=CohortFactory(organisation=OrganisationFactory()), course=course
        )

    response = _post(
        client,
        _action_url(organisation, course),
        {"registration": str(registration.pk), "reason": "Course retired"},
    )

    assert response.status_code == 404
    assert CohortCourseRegistration.objects.get(pk=registration.pk).is_active is (
        case != "inactive"
    )


@pytest.mark.django_db
def test_a_cohort_only_role_acts_on_its_own_cohorts_rows_only(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    own, own_registration = _register(organisation, course, name="Cohort One")
    _other, other_registration = _register(organisation, course, name="Cohort Two")
    client = role_holder_client(own, "cohort_admin")

    document = _get_document(client, _page_url(organisation, course))
    response = _post(
        client,
        _action_url(organisation, course),
        {"registration": str(other_registration.pk), "reason": "Course retired"},
    )

    assert _deactivate_buttons(document) == ["Deactivate Cohort One"]
    assert response.status_code == 404
    other_registration.refresh_from_db()
    assert other_registration.is_active is True
    assert own_registration.is_active is True


@pytest.mark.django_db
def test_the_panel_refreshes_on_registration_and_cohort_changes(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    _register(organisation, course)
    client = role_holder_client(organisation)

    document = _get_document(client, _page_url(organisation, course))

    (panel,) = document.cssselect("section[data-panel='cohorts']")
    trigger = panel.get("hx-trigger")
    assert f"{REGISTRATION_CHANGED} from:body" in trigger
    assert f"{COHORT_CHANGED} from:body" in trigger


@pytest.mark.django_db
def test_the_overview_render_does_not_query_per_cohort_row(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    course = CourseFactory()
    client = role_holder_client(organisation)
    _get_document(client, _page_url(organisation, course))

    def queries_with(rows: int) -> int:
        for _ in range(rows):
            _register(organisation, course)
        with CaptureQueriesContext(connection) as captured:
            _get_document(client, _page_url(organisation, course))
        return len(captured)

    one_more = queries_with(1)
    three_more = queries_with(2)

    assert three_more <= one_more + 1
