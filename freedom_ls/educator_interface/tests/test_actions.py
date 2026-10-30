"""The educator interface's panel actions, driven through the interface URLs."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import cast

import lxml.html
import pytest
from allauth.account.models import EmailAddress
from pytest_mock import MockerFixture

from django.contrib.sites.models import Site
from django.core import mail
from django.core.cache import cache
from django.db import connection, transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from freedom_ls.accounts.config import config
from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.audit_log.writer import subject_key
from freedom_ls.comms.models import Notification
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseAudience, CourseVisibility
from freedom_ls.educator_interface import actions as actions_module
from freedom_ls.educator_interface.actions import (
    AddToCohortBulkAction,
    CohortCourseBulkAction,
    DeactivateLearnersBulkAction,
    RegisterCohortForCourseBulkAction,
    RegisterForCourseBulkAction,
    RemoveFromCohortBulkAction,
    UnregisterCohortFromCourseBulkAction,
    UnregisterFromCourseBulkAction,
    cohort_not_empty_sentence,
    grantable_roles_for,
)
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
    MEMBER_CHANGED,
    REGISTRATION_CHANGED,
)
from freedom_ls.educator_interface.members import current_role_entries
from freedom_ls.educator_interface.views import OrganisationScopedRequest
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
    OrganisationMember,
)
from freedom_ls.learner_management.queries import (
    CHANGE_LEARNER,
    COURSE_NOT_OPEN_MESSAGE,
    VIEW_COHORT,
    VIEW_LEARNER,
)
from freedom_ls.learner_management.role_assignment import (
    GrantableRole,
    assign_role,
    deactivate_role,
)
from freedom_ls.learner_management.tests.scenario_world import custom_role_config
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.panel_framework.bulk_actions import (
    BulkCount,
    BulkOutcome,
    BulkResult,
    run_apply,
)
from freedom_ls.panel_framework.bulk_runs import (
    NOT_FOUND,
    report_finished,
    run_bulk_action,
    run_summary,
)
from freedom_ls.panel_framework.models import BulkActionRun, RunStatus
from freedom_ls.panel_framework.tasks import _run_bulk_action_task
from freedom_ls.role_based_permissions.exceptions import (
    RefusalReason,
    RoleChangeRefused,
)
from freedom_ls.role_based_permissions.loader import get_role_config
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment
from freedom_ls.role_based_permissions.types import SCOPE_OBJECT, Role
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.tests.audit_assertions import assert_entry
from freedom_ls.tests.factories import SiteFactory


def _interface_url(organisation_slug: str, path_string: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )


def _cohort_url(organisation: Organisation, cohort: Cohort, suffix: str = "") -> str:
    return _interface_url(organisation.slug, f"cohorts/{cohort.pk}{suffix}")


def _cohort_with_courses(
    organisation: Organisation, course_count: int, **cohort_fields: object
) -> Cohort:
    cohort = cast(Cohort, CohortFactory(organisation=organisation, **cohort_fields))
    for _ in range(course_count):
        CohortCourseRegistrationFactory(cohort=cohort)
    return cohort


def _get_fragment(client: Client, url: str) -> str:
    response = client.get(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    return " ".join(
        lxml.html.fromstring(response.content.decode()).text_content().split()
    )


def _post(client: Client, url: str, data: dict[str, str] | None = None):
    return client.post(url, data or {}, HTTP_HX_REQUEST="true")


# rename clash


@pytest.mark.django_db
def test_renaming_a_cohort_onto_a_sibling_name_answers_422_and_keeps_the_name(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation, name="Year 10 Science")
    cohort = CohortFactory(organisation=organisation, name="Year 11 Science")

    response = _post(
        staff_client,
        _cohort_url(organisation, cohort, "/__actions/edit"),
        {"name": "Year 10 Science"},
    )

    cohort.refresh_from_db()
    assert response.status_code == 422
    assert "Another cohort already has this name." in response.content.decode()
    assert cohort.name == "Year 11 Science"


# deactivate


@pytest.mark.django_db
def test_deactivate_fragment_names_how_many_courses_stop_giving_access(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 2, name="Evening group")

    text = _get_fragment(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    assert "Deactivate Evening group" in text
    assert "stop giving access to its 2 courses" in text


@pytest.mark.django_db
def test_deactivate_fragment_says_why_a_non_empty_cohort_cannot_be_deleted(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1, name="Evening group")
    CohortMembershipFactory(
        cohort=cohort, learner=LearnerFactory(organisation=organisation)
    )

    text = _get_fragment(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    assert (
        "Evening group can't be deleted while it has 1 learner and 1 course "
        "registration, counting inactive learners and inactive registrations." in text
    )


@pytest.mark.django_db
def test_deactivate_fragment_of_an_empty_cohort_does_not_mention_deleting(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0)

    text = _get_fragment(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    assert "can't be deleted" not in text


@pytest.mark.django_db
def test_deactivate_post_sets_the_cohort_inactive(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1)

    _post(staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate"))

    cohort.refresh_from_db()
    assert cohort.is_active is False


@pytest.mark.django_db
def test_deactivate_post_answers_204_with_a_location_to_the_cohort_page(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1)

    response = _post(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    assert response.status_code == 204
    assert json.loads(response["HX-Location"])["path"] == _cohort_url(
        organisation, cohort
    )


@pytest.mark.django_db
def test_stale_deactivate_on_an_inactive_cohort_answers_422_and_changes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1, is_active=False)

    response = _post(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    cohort.refresh_from_db()
    assert response.status_code == 422
    assert cohort.is_active is False
    assert not AuditLogEntry.unscoped.filter(action="cohort.deactivated").exists()


def _locks_the_cohort_row(captured: CaptureQueriesContext) -> bool:
    return any(
        'freedom_ls_learner_management_cohort"' in query["sql"]
        and "FOR UPDATE" in query["sql"]
        for query in captured.captured_queries
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("is_active", "action_name"), [(True, "deactivate"), (False, "reactivate")]
)
def test_a_cohort_state_change_locks_the_cohort_row_before_writing_its_entry(
    staff_client: Client, is_active: bool, action_name: str
):
    """Two overlapping submits must not each see the old state and each write
    an entry for the one change, so the state is re-read under a row lock."""
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1, is_active=is_active)

    with CaptureQueriesContext(connection) as captured:
        response = _post(
            staff_client, _cohort_url(organisation, cohort, f"/__actions/{action_name}")
        )

    assert response.status_code == 204
    assert _locks_the_cohort_row(captured)


# reactivate


@pytest.mark.django_db
def test_reactivate_fragment_names_how_many_courses_give_access_again(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 3, name="Old group", is_active=False)

    text = _get_fragment(
        staff_client, _cohort_url(organisation, cohort, "/__actions/reactivate")
    )

    assert "Reactivate Old group" in text
    assert "give access to its 3 courses again" in text


@pytest.mark.django_db
def test_reactivate_post_sets_the_cohort_active(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1, is_active=False)

    response = _post(
        staff_client, _cohort_url(organisation, cohort, "/__actions/reactivate")
    )

    cohort.refresh_from_db()
    assert response.status_code == 204
    assert cohort.is_active is True


@pytest.mark.django_db
def test_stale_reactivate_on_an_active_cohort_answers_422(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1)

    response = _post(
        staff_client, _cohort_url(organisation, cohort, "/__actions/reactivate")
    )

    assert response.status_code == 422
    assert "is already active" in response.content.decode()
    assert not AuditLogEntry.unscoped.filter(action="cohort.reactivated").exists()


@pytest.mark.django_db
def test_a_reason_posted_to_a_dialog_without_a_reason_field_is_ignored(
    staff_client: Client,
):
    """Reactivate takes no reason, so a hand-made POST carrying one, however
    long, neither fails nor reaches the entry."""
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1, is_active=False)

    response = _post(
        staff_client,
        _cohort_url(organisation, cohort, "/__actions/reactivate"),
        {"reason": "x" * 600},
    )

    assert response.status_code == 204
    assert AuditLogEntry.unscoped.get(action="cohort.reactivated").reason == ""


@pytest.mark.django_db
def test_cohort_not_empty_sentence_counts_inactive_learners_and_inactive_registrations(
    mock_site_context,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Evening group")
    removed = LearnerFactory(organisation=organisation, is_active=False)
    CohortMembershipFactory(cohort=cohort, learner=removed)
    CohortMembershipFactory(
        cohort=cohort, learner=LearnerFactory(organisation=organisation)
    )
    CohortCourseRegistrationFactory(cohort=cohort, is_active=False)

    sentence = cohort_not_empty_sentence(cohort)

    assert sentence == (
        "Evening group can't be deleted while it has 2 learners and 1 course "
        "registration, counting inactive learners and inactive registrations."
    )


@pytest.mark.django_db
def test_not_empty_sentence_pluralises_course_registrations(
    mock_site_context: Site,
) -> None:
    cohort = _cohort_with_courses(OrganisationFactory(), 2, name="Evening group")

    sentence = cohort_not_empty_sentence(cohort)

    assert "while it has 2 course registrations, counting" in sentence


@pytest.mark.django_db
def test_not_empty_sentence_never_names_a_zero_count(mock_site_context: Site) -> None:
    """ "0 learners" reads as a reason, and is not one."""
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Evening group")
    CohortMembershipFactory(
        cohort=cohort, learner=LearnerFactory(organisation=organisation)
    )

    sentence = cohort_not_empty_sentence(cohort)

    assert "while it has 1 learner, counting" in sentence
    assert "0 course" not in sentence


@pytest.mark.django_db
def test_not_empty_sentence_is_empty_for_an_empty_cohort(
    mock_site_context: Site,
) -> None:
    cohort = _cohort_with_courses(OrganisationFactory(), 0)

    assert cohort_not_empty_sentence(cohort) == ""


# inactive cohorts are read-only


@pytest.mark.django_db
def test_an_inactive_cohorts_page_renders_no_edit_trigger(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, is_active=False)

    response = staff_client.get(_cohort_url(organisation, cohort))

    document = lxml.html.fromstring(response.content.decode())
    triggers = {button.get("hx-get") for button in document.cssselect("button[hx-get]")}
    assert _cohort_url(organisation, cohort, "/__actions/edit") not in triggers


@pytest.mark.django_db
def test_editing_an_inactive_cohort_answers_422_with_the_inactive_fragment(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Old group", is_active=False)

    response = _post(
        staff_client,
        _cohort_url(organisation, cohort, "/__actions/edit"),
        {"name": "New name"},
    )

    assert response.status_code == 422
    assert "Old group is inactive" in response.content.decode()


@pytest.mark.django_db
def test_editing_an_inactive_cohort_leaves_its_name_unchanged(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Old group", is_active=False)

    _post(
        staff_client,
        _cohort_url(organisation, cohort, "/__actions/edit"),
        {"name": "New name"},
    )

    cohort.refresh_from_db()
    assert cohort.name == "Old group"


# register


def _register_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(organisation, cohort, "/__tabs/courses/__actions/register")


@pytest.mark.django_db
def test_register_fragment_title_names_the_cohort(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Evening group")

    text = _get_fragment(staff_client, _register_url(organisation, cohort))

    assert "Register Evening group for a course" in text


@pytest.mark.django_db
def test_register_post_answers_204_with_a_location_to_the_courses_tab(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0)
    course = CourseFactory()
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)

    response = _post(
        logged_in_client(educator),
        _register_url(organisation, cohort),
        {"course": str(course.pk)},
    )

    assert response.status_code == 204
    assert json.loads(response["HX-Location"])["path"] == _cohort_url(
        organisation, cohort, "/__tabs/courses"
    )


@pytest.mark.django_db
def test_register_post_creates_the_registration(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0)
    course = CourseFactory()

    _post(
        staff_client,
        _register_url(organisation, cohort),
        {"course": str(course.pk)},
    )

    assert cohort.course_registrations.filter(course=course, is_active=True).exists()


@pytest.mark.django_db
def test_register_post_for_a_course_closed_to_the_organisation_answers_422(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0)
    course = CourseFactory(audience=CourseAudience.ORGANISATION_LEARNERS)
    course.organisations.add(OrganisationFactory())

    response = _post(
        staff_client,
        _register_url(organisation, cohort),
        {"course": str(course.pk)},
    )

    assert response.status_code == 422
    assert not cohort.course_registrations.exists()


@pytest.mark.django_db
def test_register_post_on_an_inactive_cohort_answers_422_and_creates_no_row(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Old group", is_active=False)
    course = CourseFactory()

    response = _post(
        staff_client,
        _register_url(organisation, cohort),
        {"course": str(course.pk)},
    )

    assert response.status_code == 422
    assert "Old group is inactive" in response.content.decode()
    assert not cohort.course_registrations.exists()


# unregister


def _unregister_post_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(
        organisation, cohort, "/__tabs/courses/__actions/deactivate_cohort_registration"
    )


def _unregister_url(
    organisation: Organisation,
    cohort: Cohort,
    registration: CohortCourseRegistration | str,
) -> str:
    pk = registration if isinstance(registration, str) else registration.pk
    return f"{_unregister_post_url(organisation, cohort)}?registration={pk}"


def _member(organisation: Organisation, cohort: Cohort, first_name: str = "Ada"):
    learner = LearnerFactory(
        organisation=organisation, user__first_name=first_name, user__last_name="Lee"
    )
    CohortMembershipFactory(cohort=cohort, learner=learner)
    return learner


def _registered_cohort(
    organisation: Organisation, course_title: str = "Algebra", **cohort_fields: object
):
    cohort = cast(Cohort, CohortFactory(organisation=organisation, **cohort_fields))
    registration = CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title=course_title)
    )
    return cohort, registration


@pytest.mark.django_db
def test_unregister_fragment_title_names_the_cohort_and_course(staff_client: Client):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation, name="Evening group")

    text = _get_fragment(
        staff_client, _unregister_url(organisation, cohort, registration)
    )

    assert "Deactivate Evening group's registration for Algebra" in text


@pytest.mark.django_db
def test_unregister_fragment_counts_members_who_lose_access(staff_client: Client):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    _member(organisation, cohort, "Ada")
    _member(organisation, cohort, "Bea")
    kept = _member(organisation, cohort, "Cy")
    LearnerCourseRegistrationFactory(
        learner=kept, course=registration.course, is_active=True
    )

    text = _get_fragment(
        staff_client, _unregister_url(organisation, cohort, registration)
    )

    assert "2 learners lose access to Algebra." in text


@pytest.mark.django_db
def test_unregister_fragment_names_a_member_kept_by_an_individual_registration(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    kept = _member(organisation, cohort, "Cy")
    LearnerCourseRegistrationFactory(
        learner=kept, course=registration.course, is_active=True
    )

    text = _get_fragment(
        staff_client, _unregister_url(organisation, cohort, registration)
    )

    assert "These learners keep access through another registration: Cy Lee." in text


@pytest.mark.django_db
def test_unregister_fragment_names_a_member_kept_by_another_cohort(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    kept = _member(organisation, cohort, "Dee")
    other = CohortFactory(organisation=organisation)
    CohortMembershipFactory(cohort=other, learner=kept)
    CohortCourseRegistrationFactory(cohort=other, course=registration.course)

    text = _get_fragment(
        staff_client, _unregister_url(organisation, cohort, registration)
    )

    assert "keep access through another registration: Dee Lee." in text


@pytest.mark.django_db
def test_unregister_fragment_names_the_first_ten_keepers_and_counts_the_rest(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    for index in range(12):
        learner = _member(organisation, cohort, f"Keeper{index:02d}")
        LearnerCourseRegistrationFactory(
            learner=learner, course=registration.course, is_active=True
        )

    text = _get_fragment(
        staff_client, _unregister_url(organisation, cohort, registration)
    )

    assert "Keeper09 Lee and 2 more." in text
    assert "Keeper10" not in text


@pytest.mark.django_db
def test_unregister_fragment_omits_the_keepers_sentence_when_nobody_keeps_access(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    _member(organisation, cohort)

    text = _get_fragment(
        staff_client, _unregister_url(organisation, cohort, registration)
    )

    assert "keep access through another registration" not in text


@pytest.mark.django_db
def test_unregister_post_deactivates_the_registration(staff_client: Client):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)

    _post(
        staff_client,
        _unregister_post_url(organisation, cohort),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    assert registration.is_active is False


@pytest.mark.django_db
def test_unregister_post_answers_204_with_a_location_to_the_courses_tab(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)

    response = _post(
        staff_client,
        _unregister_post_url(organisation, cohort),
        {"registration": str(registration.pk)},
    )

    assert response.status_code == 204
    assert json.loads(response["HX-Location"])["path"] == _cohort_url(
        organisation, cohort, "/__tabs/courses"
    )


@pytest.mark.django_db
def test_a_cohort_admin_can_unregister_on_their_own_cohort(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)

    response = _post(
        logged_in_client(educator),
        _unregister_post_url(organisation, cohort),
        {"registration": str(registration.pk)},
    )

    assert response.status_code == 204


@pytest.mark.django_db
def test_unregister_with_a_registration_from_another_cohort_answers_404(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort, _ = _registered_cohort(organisation)
    _, foreign = _registered_cohort(organisation, "Geometry")

    response = staff_client.get(
        _unregister_url(organisation, cohort, foreign), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_unregister_with_a_registration_from_another_cohort_changes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort, _ = _registered_cohort(organisation)
    _, foreign = _registered_cohort(organisation, "Geometry")

    _post(
        staff_client,
        _unregister_post_url(organisation, cohort),
        {"registration": str(foreign.pk)},
    )

    foreign.refresh_from_db()
    assert foreign.is_active is True


@pytest.mark.django_db
def test_unregister_with_an_inactive_registration_answers_404(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    registration = CohortCourseRegistrationFactory(cohort=cohort, is_active=False)

    response = staff_client.get(
        _unregister_url(organisation, cohort, registration), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_unregister_with_a_malformed_registration_answers_404(staff_client: Client):
    organisation = OrganisationFactory()
    cohort, _ = _registered_cohort(organisation)

    response = staff_client.get(
        _unregister_url(organisation, cohort, "not-a-uuid"), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_courses_tab_footer_offers_register_but_no_unregister_button(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort, _ = _registered_cohort(organisation)

    response = staff_client.get(
        _cohort_url(organisation, cohort, "/__tabs/courses"), HTTP_HX_REQUEST="true"
    )

    footer_urls = [
        button.get("hx-get")
        for button in lxml.html.fromstring(response.content.decode()).cssselect(
            "button[hx-get]"
        )
    ]
    register_url = _register_url(organisation, cohort)
    assert register_url in footer_urls
    assert not [
        url
        for url in footer_urls
        if url.endswith("/__actions/deactivate_cohort_registration")
    ]


@pytest.mark.django_db
def test_unregister_post_on_an_inactive_cohort_answers_422_and_changes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(
        organisation, name="Old group", is_active=False
    )

    response = _post(
        staff_client,
        _unregister_post_url(organisation, cohort),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    assert response.status_code == 422
    assert "Old group is inactive" in response.content.decode()
    assert registration.is_active is True


# edit a learner's name


def _site_admin_client(site: Site, logged_in_client) -> Client:
    admin = UserFactory(staff=True)
    assign_role(UserFactory(superuser=True), admin, "site_admin", site)
    return cast(Client, logged_in_client(admin))


def _edit_name_url(organisation: Organisation, learner: Learner) -> str:
    return _interface_url(
        organisation.slug, f"learners/{learner.pk}/__actions/edit_name"
    )


def _named_learner(organisation: Organisation) -> Learner:
    return cast(
        Learner,
        LearnerFactory(
            organisation=organisation,
            user=UserFactory(first_name="Ada", last_name="Lovelace"),
        ),
    )


@pytest.mark.django_db
def test_a_site_admins_learner_header_offers_edit_name(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    client = _site_admin_client(mock_site_context, logged_in_client)

    response = client.get(_interface_url(organisation.slug, f"learners/{learner.pk}"))

    document = lxml.html.fromstring(response.content.decode())
    triggers = {button.get("hx-get") for button in document.cssselect("button[hx-get]")}
    assert _edit_name_url(organisation, learner) in triggers


@pytest.mark.django_db
def test_an_organisation_admins_learner_header_offers_no_edit_name(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    user = UserFactory(staff=True)
    assign_role(UserFactory(superuser=True), user, "organisation_admin", organisation)
    client = logged_in_client(user)

    response = client.get(_interface_url(organisation.slug, f"learners/{learner.pk}"))

    document = lxml.html.fromstring(response.content.decode())
    triggers = {button.get("hx-get") for button in document.cssselect("button[hx-get]")}
    assert _edit_name_url(organisation, learner) not in triggers


@pytest.mark.django_db
def test_edit_name_post_changes_the_users_first_name(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    client = _site_admin_client(mock_site_context, logged_in_client)

    _post(
        client,
        _edit_name_url(organisation, learner),
        {"first_name": "Grace", "last_name": "Hopper"},
    )

    learner.user.refresh_from_db()
    assert learner.user.first_name == "Grace"


@pytest.mark.django_db
def test_edit_name_post_sends_the_new_display_name_as_the_page_title(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    client = _site_admin_client(mock_site_context, logged_in_client)

    response = _post(
        client,
        _edit_name_url(organisation, learner),
        {"first_name": "Grace", "last_name": "Hopper"},
    )

    trigger = json.loads(response["HX-Trigger"])
    assert (response.status_code, trigger["instanceTitleChanged"]["title"]) == (
        204,
        "Grace Hopper",
    )


@pytest.mark.django_db
def test_edit_name_post_fires_the_learner_changed_event_for_the_learner(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    client = _site_admin_client(mock_site_context, logged_in_client)

    response = _post(
        client,
        _edit_name_url(organisation, learner),
        {"first_name": "Grace", "last_name": "Hopper"},
    )

    trigger = json.loads(response["HX-Trigger"])
    assert trigger[LEARNER_CHANGED] == {"ids": [str(learner.pk)]}


# deactivate and reactivate a learner


def _learner_state_url(
    organisation: Organisation, learner: Learner, action: str
) -> str:
    return _interface_url(
        organisation.slug, f"learners/{learner.pk}/__actions/{action}"
    )


def _header_triggers(
    client: Client, organisation: Organisation, learner: Learner
) -> set[str | None]:
    response = client.get(_interface_url(organisation.slug, f"learners/{learner.pk}"))
    document = lxml.html.fromstring(response.content.decode())
    return {button.get("hx-get") for button in document.cssselect("button[hx-get]")}


@pytest.mark.django_db
def test_an_active_learners_header_offers_deactivate_not_reactivate(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=True)

    triggers = _header_triggers(staff_client, organisation, learner)

    assert (
        _learner_state_url(organisation, learner, "deactivate") in triggers,
        _learner_state_url(organisation, learner, "reactivate") in triggers,
    ) == (True, False)


@pytest.mark.django_db
def test_a_removed_learners_header_offers_reactivate_not_deactivate(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=False)

    triggers = _header_triggers(staff_client, organisation, learner)

    assert (
        _learner_state_url(organisation, learner, "deactivate") in triggers,
        _learner_state_url(organisation, learner, "reactivate") in triggers,
    ) == (False, True)


@pytest.mark.django_db
def test_deactivate_fragment_names_self_registration_only_on_the_default_organisation(
    staff_client: Client, mock_site_context: Site
):
    default = get_default_organisation(mock_site_context)
    learner = LearnerFactory(organisation=default, is_active=True)

    text = _get_fragment(
        staff_client, _learner_state_url(default, learner, "deactivate")
    )

    assert "self-register" in text


@pytest.mark.django_db
def test_deactivate_fragment_omits_self_registration_on_another_organisation(
    staff_client: Client,
):
    organisation = OrganisationFactory(is_default=False)
    learner = LearnerFactory(organisation=organisation, is_active=True)

    text = _get_fragment(
        staff_client, _learner_state_url(organisation, learner, "deactivate")
    )

    assert "self-register" not in text


@pytest.mark.django_db
def test_reactivate_fragment_says_access_returns_through_existing_cohorts_and_registrations(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=False)

    text = _get_fragment(
        staff_client, _learner_state_url(organisation, learner, "reactivate")
    )

    assert "existing cohorts and registrations" in text


@pytest.mark.django_db
def test_deactivate_post_answers_204_with_a_location_to_the_learner_page(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=True)

    response = _post(
        staff_client, _learner_state_url(organisation, learner, "deactivate")
    )

    location = json.loads(response["HX-Location"])
    assert (response.status_code, location["path"]) == (
        204,
        _interface_url(organisation.slug, f"learners/{learner.pk}"),
    )


@pytest.mark.django_db
def test_deactivate_post_sets_the_learner_inactive(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=True)

    _post(staff_client, _learner_state_url(organisation, learner, "deactivate"))

    learner.refresh_from_db()
    assert learner.is_active is False


@pytest.mark.django_db
def test_reactivate_post_sets_the_learner_active(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=False)

    _post(staff_client, _learner_state_url(organisation, learner, "reactivate"))

    learner.refresh_from_db()
    assert learner.is_active is True


@pytest.mark.django_db
def test_deactivating_a_removed_learner_answers_422_and_changes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=False)

    response = _post(
        staff_client, _learner_state_url(organisation, learner, "deactivate")
    )

    learner.refresh_from_db()
    assert (response.status_code, learner.is_active) == (422, False)


@pytest.mark.django_db
def test_reactivating_an_active_learner_answers_422(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=True)

    response = _post(
        staff_client, _learner_state_url(organisation, learner, "reactivate")
    )

    assert response.status_code == 422


# remove from a cohort


def _remove_url_from_learner(
    organisation: Organisation, learner: Learner, cohort: Cohort | None = None
) -> str:
    url = _interface_url(
        organisation.slug,
        f"learners/{learner.pk}/__tabs/overview/__panels/cohorts"
        "/__actions/remove_from_cohort",
    )
    return f"{url}?cohort={cohort.pk}" if cohort is not None else url


def _remove_url_from_cohort(
    organisation: Organisation, cohort: Cohort, learner: Learner | None = None
) -> str:
    url = _cohort_url(
        organisation, cohort, "/__tabs/learners/__actions/remove_from_cohort"
    )
    return f"{url}?learner={learner.pk}" if learner is not None else url


def _membership(organisation: Organisation, **cohort_fields: object):
    cohort = cast(Cohort, CohortFactory(organisation=organisation, **cohort_fields))
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    CohortMembershipFactory(cohort=cohort, learner=learner)
    return learner, cohort


def _remove_triggers(client: Client, url: str) -> list[str]:
    document = lxml.html.fromstring(client.get(url).content.decode())
    return [
        button.get("hx-get") or ""
        for button in document.cssselect("button[hx-get]")
        if "remove_from_cohort" in (button.get("hx-get") or "")
    ]


@pytest.mark.django_db
def test_the_learner_page_renders_with_the_remove_action_registered(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, _ = _membership(organisation)

    response = staff_client.get(
        _interface_url(organisation.slug, f"learners/{learner.pk}")
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_remove_fragment_from_the_learner_page_names_the_courses_lost(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Algebra")
    )

    text = _get_fragment(
        staff_client, _remove_url_from_learner(organisation, learner, cohort)
    )

    assert "They lose access to: Algebra." in text
    assert "Progress is kept." in text


@pytest.mark.django_db
def test_remove_fragment_says_the_learner_keeps_every_course_through_another_registration(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    LearnerCourseRegistrationFactory(learner=learner, course=course)

    text = _get_fragment(
        staff_client, _remove_url_from_learner(organisation, learner, cohort)
    )

    assert "keep access to every course through another registration" in text


@pytest.mark.django_db
def test_remove_post_from_the_learner_page_deletes_the_membership(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)

    response = _post(
        staff_client,
        _remove_url_from_learner(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    assert response.status_code == 204
    assert not CohortMembership.objects.filter(learner=learner, cohort=cohort).exists()


@pytest.mark.django_db
def test_remove_post_sends_both_ids_with_the_learner_and_cohort_events(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)

    response = _post(
        staff_client,
        _remove_url_from_learner(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    trigger = json.loads(response["HX-Trigger"])
    ids = {"ids": [str(learner.pk), str(cohort.pk)]}
    assert (trigger[LEARNER_CHANGED], trigger[COHORT_CHANGED]) == (ids, ids)
    assert "closeModal" in trigger


@pytest.mark.django_db
def test_remove_fragment_from_the_cohort_page_names_the_courses_lost(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Algebra")
    )

    text = _get_fragment(
        staff_client, _remove_url_from_cohort(organisation, cohort, learner)
    )

    assert "They lose access to: Algebra." in text


@pytest.mark.django_db
def test_remove_post_from_the_cohort_page_deletes_the_membership(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)

    response = _post(
        staff_client,
        _remove_url_from_cohort(organisation, cohort),
        {"learner": str(learner.pk)},
    )

    assert response.status_code == 204
    assert not CohortMembership.objects.filter(learner=learner, cohort=cohort).exists()


@pytest.mark.django_db
def test_a_stale_remove_naming_an_inactive_cohort_answers_422_and_changes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation, is_active=False)

    response = _post(
        staff_client,
        _remove_url_from_learner(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    assert response.status_code == 422
    assert "is inactive" in response.content.decode()
    assert CohortMembership.objects.filter(learner=learner, cohort=cohort).exists()


@pytest.mark.django_db
def test_a_cohort_admins_learner_page_offers_remove_on_the_granted_cohort_only(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, granted = _membership(organisation)
    other = cast(Cohort, CohortFactory(organisation=organisation))
    CohortMembershipFactory(cohort=other, learner=learner)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", granted)
    assign_role(grantor, educator, "cohort_viewer", other)

    triggers = _remove_triggers(
        logged_in_client(educator),
        _interface_url(organisation.slug, f"learners/{learner.pk}"),
    )

    assert {t.split("?cohort=")[1] for t in triggers} == {str(granted.pk)}


@pytest.mark.django_db
def test_a_forged_remove_on_an_unassigned_cohort_answers_403(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, granted = _membership(organisation)
    other = cast(Cohort, CohortFactory(organisation=organisation))
    CohortMembershipFactory(cohort=other, learner=learner)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", granted)
    assign_role(grantor, educator, "cohort_viewer", other)

    response = _post(
        logged_in_client(educator),
        _remove_url_from_learner(organisation, learner),
        {"cohort": str(other.pk)},
    )

    assert response.status_code == 403
    assert CohortMembership.objects.filter(learner=learner, cohort=other).exists()


# add to a cohort


def _add_to_cohort_url(organisation: Organisation, learner: Learner) -> str:
    return _interface_url(
        organisation.slug, f"learners/{learner.pk}/__actions/add_to_cohort"
    )


def _add_learners_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(
        organisation, cohort, "/__tabs/learners/__actions/add_existing_learners"
    )


def _offered_options(client: Client, url: str) -> set[str]:
    response = client.get(url, HTTP_HX_REQUEST="true")
    document = lxml.html.fromstring(response.content.decode())
    return {
        option.get("value")
        for option in document.cssselect("option[value]")
        if option.get("value")
    }


def _cohort_admin_on(organisation: Organisation, *cohorts: Cohort):
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    for cohort in cohorts:
        assign_role(grantor, educator, "cohort_admin", cohort)
    return educator


@pytest.mark.django_db
def test_add_to_cohort_offers_only_active_cohorts_the_learner_is_not_in(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, member_of = _membership(organisation)
    open_cohort = cast(Cohort, CohortFactory(organisation=organisation))
    inactive = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))

    offered = _offered_options(staff_client, _add_to_cohort_url(organisation, learner))

    assert offered == {str(open_cohort.pk)}
    assert str(member_of.pk) not in offered
    assert str(inactive.pk) not in offered


@pytest.mark.django_db
def test_add_to_cohort_post_adds_the_membership(staff_client: Client):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = _post(
        staff_client,
        _add_to_cohort_url(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    assert response.status_code == 204
    assert CohortMembership.objects.filter(learner=learner, cohort=cohort).exists()


@pytest.mark.django_db
def test_add_to_cohort_post_sends_the_learner_and_cohort_events(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = _post(
        staff_client,
        _add_to_cohort_url(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    trigger = json.loads(response["HX-Trigger"])
    assert trigger[LEARNER_CHANGED] == {"ids": [str(learner.pk)]}
    assert trigger[COHORT_CHANGED] == {"ids": [str(cohort.pk)]}
    assert "closeModal" in trigger


@pytest.mark.django_db
def test_add_to_cohort_post_naming_an_inactive_cohort_answers_422_and_adds_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    cohort = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))

    response = _post(
        staff_client,
        _add_to_cohort_url(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    assert response.status_code == 422
    assert not CohortMembership.objects.filter(learner=learner).exists()


@pytest.mark.django_db
def test_a_cohort_admins_add_to_cohort_offers_only_assigned_cohorts(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, granted = _membership(organisation)
    spare = cast(Cohort, CohortFactory(organisation=organisation))
    unassigned = cast(Cohort, CohortFactory(organisation=organisation))
    educator = _cohort_admin_on(organisation, granted, spare)

    offered = _offered_options(
        logged_in_client(educator), _add_to_cohort_url(organisation, learner)
    )

    assert offered == {str(spare.pk)}
    assert str(unassigned.pk) not in offered


@pytest.mark.django_db
def test_a_forged_add_to_an_unassigned_cohort_answers_403_and_adds_nothing(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, granted = _membership(organisation)
    unassigned = cast(Cohort, CohortFactory(organisation=organisation))
    educator = _cohort_admin_on(organisation, granted)

    response = _post(
        logged_in_client(educator),
        _add_to_cohort_url(organisation, learner),
        {"cohort": str(unassigned.pk)},
    )

    assert response.status_code == 403
    assert not CohortMembership.objects.filter(
        learner=learner, cohort=unassigned
    ).exists()


def _learner_tab_triggers(client: Client, cohort: Cohort) -> list[str]:
    url = _cohort_url(cohort.organisation, cohort, "/__tabs/learners")
    document = lxml.html.fromstring(client.get(url).content.decode())
    return [
        button.get("hx-get") or ""
        for button in document.cssselect("button[hx-get]")
        if "add_existing_learners" in (button.get("hx-get") or "")
    ]


@pytest.mark.django_db
def test_a_cohort_admin_without_add_learner_sees_the_learner_picker_on_the_cohort_tab(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    educator = _cohort_admin_on(organisation, cohort)

    triggers = _learner_tab_triggers(logged_in_client(educator), cohort)

    assert len(triggers) == 1


@pytest.mark.django_db
def test_an_organisation_admin_with_add_learner_sees_no_learner_picker(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "organisation_admin", organisation)

    triggers = _learner_tab_triggers(logged_in_client(educator), cohort)

    assert triggers == []


@pytest.mark.django_db
def test_the_learner_picker_offers_learners_outside_the_cohort(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    member = cast(Learner, LearnerFactory(organisation=organisation))
    CohortMembershipFactory(cohort=cohort, learner=member)
    outsider = cast(Learner, LearnerFactory(organisation=organisation))
    educator = _cohort_admin_on(organisation, cohort)
    CohortMembershipFactory(
        cohort=CohortFactory(organisation=organisation), learner=outsider
    )
    assign_role(
        LearnerFactory(user__superuser=True).user,
        educator,
        "organisation_admin",
        organisation,
    )

    offered = _offered_options(
        logged_in_client(educator), _add_learners_url(organisation, cohort)
    )

    assert str(member.pk) not in offered
    assert str(outsider.pk) in offered


@pytest.mark.django_db
def test_the_learner_picker_post_adds_each_learner(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    first = cast(Learner, LearnerFactory(organisation=organisation))
    second = cast(Learner, LearnerFactory(organisation=organisation))

    response = staff_client.post(
        _add_learners_url(organisation, cohort),
        {"learners": [str(first.pk), str(second.pk)]},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 204
    assert set(
        CohortMembership.objects.filter(cohort=cohort).values_list(
            "learner_id", flat=True
        )
    ) == {first.pk, second.pk}


@pytest.mark.django_db
def test_the_learner_picker_post_sends_every_learner_id_and_the_cohort_id(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    first = cast(Learner, LearnerFactory(organisation=organisation))
    second = cast(Learner, LearnerFactory(organisation=organisation))

    response = staff_client.post(
        _add_learners_url(organisation, cohort),
        {"learners": [str(first.pk), str(second.pk)]},
        HTTP_HX_REQUEST="true",
    )

    trigger = json.loads(response["HX-Trigger"])
    assert set(trigger[LEARNER_CHANGED]["ids"]) == {str(first.pk), str(second.pk)}
    assert trigger[COHORT_CHANGED] == {"ids": [str(cohort.pk)]}


@pytest.mark.django_db
def test_a_stale_learner_picker_post_on_an_inactive_cohort_answers_422(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))
    learner = cast(Learner, LearnerFactory(organisation=organisation))

    response = staff_client.post(
        _add_learners_url(organisation, cohort),
        {"learners": [str(learner.pk)]},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    assert not CohortMembership.objects.filter(cohort=cohort).exists()


# add learners


def _add_learners_list_url(organisation: Organisation) -> str:
    return _interface_url(organisation.slug, "learners/__actions/add_learners")


def _add_learners_tab_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(organisation, cohort, "/__tabs/learners/__actions/add_learners")


def _organisation_admin_on(organisation: Organisation):
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "organisation_admin", organisation)
    return educator


def _list_triggers(client: Client, organisation: Organisation) -> list[str]:
    document = lxml.html.fromstring(
        client.get(_interface_url(organisation.slug, "learners")).content.decode()
    )
    return [
        button.get("hx-get") or ""
        for button in document.cssselect("button[hx-get]")
        if "__actions/add_learners" in (button.get("hx-get") or "")
    ]


@pytest.mark.django_db
def test_the_learners_list_offers_add_learners_to_an_organisation_admin(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    educator = _organisation_admin_on(organisation)

    triggers = _list_triggers(logged_in_client(educator), organisation)

    assert len(triggers) == 1


@pytest.mark.django_db
def test_the_learners_list_offers_no_add_learners_to_a_cohort_admin(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    educator = _cohort_admin_on(organisation, cohort)

    triggers = _list_triggers(logged_in_client(educator), organisation)

    assert triggers == []


@pytest.mark.django_db
def test_add_learners_offers_only_active_cohorts_the_user_may_add_to(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    open_cohort = cast(Cohort, CohortFactory(organisation=organisation))
    CohortFactory(organisation=organisation, is_active=False)
    CohortFactory(organisation=OrganisationFactory())

    offered = _offered_options(staff_client, _add_learners_list_url(organisation))

    assert offered == {str(open_cohort.pk)}


@pytest.mark.django_db
def test_add_learners_renders_a_preset_cohort_as_a_hidden_input(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = staff_client.get(
        _add_learners_list_url(organisation),
        {"cohort": str(cohort.pk)},
        HTTP_HX_REQUEST="true",
    )

    document = lxml.html.fromstring(response.content.decode())
    hidden = document.cssselect("input[type=hidden][name=cohort]")
    assert [field.get("value") for field in hidden] == [str(cohort.pk)]


@pytest.mark.django_db
def test_add_learners_post_without_entries_answers_422(staff_client: Client):
    organisation = OrganisationFactory()

    response = _post(
        staff_client, _add_learners_list_url(organisation), {"entries": ""}
    )

    assert response.status_code == 422


@pytest.mark.django_db
def test_add_learners_post_answers_200_with_the_results_and_creates_the_learners(
    staff_client: Client,
):
    organisation = OrganisationFactory()

    response = _post(
        staff_client,
        _add_learners_list_url(organisation),
        {"entries": "new@example.com, Nia, Okoye\nbad-address"},
    )

    assert response.status_code == 200
    assert "Account created and setup email sent" in response.content.decode()
    assert "Not a valid email address" in response.content.decode()
    assert Learner.objects.filter(
        organisation=organisation, user__email="new@example.com"
    ).exists()


@pytest.mark.django_db
def test_add_learners_post_sends_the_learner_changed_trigger(staff_client: Client):
    organisation = OrganisationFactory()

    response = _post(
        staff_client,
        _add_learners_list_url(organisation),
        {"entries": "new@example.com"},
    )

    assert LEARNER_CHANGED in json.loads(response["HX-Trigger"])


@pytest.mark.django_db
def test_add_learners_post_with_a_cohort_sends_the_cohort_changed_trigger_and_adds_them(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = _post(
        staff_client,
        _add_learners_list_url(organisation),
        {"entries": "new@example.com", "cohort": str(cohort.pk)},
    )

    assert COHORT_CHANGED in json.loads(response["HX-Trigger"])
    assert cohort.cohortmembership_set.count() == 1


@pytest.mark.django_db
def test_add_learners_post_on_a_cohort_tab_adds_to_that_cohort(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = _post(
        staff_client,
        _add_learners_tab_url(organisation, cohort),
        {"entries": "new@example.com"},
    )

    assert response.status_code == 200
    assert cohort.cohortmembership_set.count() == 1


@pytest.mark.django_db
def test_the_cohort_tab_title_names_the_cohort(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, name="Wave One"))

    fragment = _get_fragment(staff_client, _add_learners_tab_url(organisation, cohort))

    assert "Add learners to Wave One" in fragment


@pytest.mark.django_db
def test_an_organisation_admins_cohort_tab_offers_add_learners_not_the_picker(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    client = logged_in_client(_organisation_admin_on(organisation))
    url = _cohort_url(organisation, cohort, "/__tabs/learners")

    document = lxml.html.fromstring(client.get(url).content.decode())

    hx_gets = [
        button.get("hx-get") or "" for button in document.cssselect("button[hx-get]")
    ]
    assert [g.rsplit("/", 1)[-1] for g in hx_gets if "__actions/add" in g] == [
        "add_learners"
    ]


@pytest.mark.django_db
def test_an_inactive_cohorts_tab_offers_no_add_learners(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))

    html = staff_client.get(
        _cohort_url(organisation, cohort, "/__tabs/learners")
    ).content.decode()

    assert "__actions/add_learners" not in html


@pytest.mark.django_db
def test_a_stale_add_learners_post_on_an_inactive_cohort_answers_422_and_adds_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))

    response = _post(
        staff_client,
        _add_learners_tab_url(organisation, cohort),
        {"entries": "new@example.com"},
    )

    assert response.status_code == 422
    assert not Learner.objects.filter(user__email="new@example.com").exists()


# resend the account setup email


@pytest.fixture
def _clear_resend_guard():
    cache.clear()
    yield
    cache.clear()


def _resend_url(organisation: Organisation, learner: Learner) -> str:
    return _interface_url(
        organisation.slug, f"learners/{learner.pk}/__actions/resend_setup_email"
    )


def _pending_learner(organisation: Organisation) -> Learner:
    user = UserFactory(email="pending@example.com", last_login=None)
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return cast(Learner, LearnerFactory(organisation=organisation, user=user))


@pytest.mark.django_db
def test_a_pending_learners_header_offers_resend_setup_email(staff_client: Client):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)

    triggers = _header_triggers(staff_client, organisation, learner)

    assert _resend_url(organisation, learner) in triggers


@pytest.mark.django_db
def test_a_learner_who_has_set_up_their_account_is_offered_no_resend(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)

    triggers = _header_triggers(staff_client, organisation, learner)

    assert _resend_url(organisation, learner) not in triggers


@pytest.mark.django_db
def test_resend_fragment_names_the_address(staff_client: Client):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)

    text = _get_fragment(staff_client, _resend_url(organisation, learner))

    assert "pending@example.com" in text


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_resend_post_sends_one_message_and_answers_204(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(staff_client, _resend_url(organisation, learner))

    assert (response.status_code, len(mail.outbox)) == (204, 1)


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_resend_post_fires_learner_changed_and_closes_the_modal(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(staff_client, _resend_url(organisation, learner))

    events = json.loads(response["HX-Trigger"])
    assert (events[LEARNER_CHANGED], "closeModal" in events) == (
        {"ids": [str(learner.pk)]},
        True,
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_a_second_resend_answers_422_with_the_minutes_to_wait(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)
    with django_capture_on_commit_callbacks(execute=True):
        _post(staff_client, _resend_url(organisation, learner))

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(staff_client, _resend_url(organisation, learner))

    minutes = config.SETUP_EMAIL_RESEND_SECONDS // 60
    assert (response.status_code, len(mail.outbox)) == (422, 1)
    assert f"{minutes} minutes" in response.content.decode()


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_resend_for_a_learner_who_has_set_up_answers_422_and_sends_nothing(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(staff_client, _resend_url(organisation, learner))

    assert (response.status_code, len(mail.outbox)) == (422, 0)


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_a_cohort_admins_forged_resend_answers_403_and_sends_nothing(
    mock_site_context: Site, logged_in_client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    CohortMembershipFactory(cohort=cohort, learner=learner)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(logged_in_client(educator), _resend_url(organisation, learner))

    assert (response.status_code, len(mail.outbox)) == (403, 0)


# move between cohorts


def _move_url_from_learner(
    organisation: Organisation,
    learner: Learner,
    source: Cohort | None = None,
    destination: Cohort | None = None,
) -> str:
    url = _interface_url(
        organisation.slug,
        f"learners/{learner.pk}/__tabs/overview/__panels/cohorts/__actions/move",
    )
    params = []
    if source is not None:
        params.append(f"cohort={source.pk}")
    if destination is not None:
        params.append(f"destination={destination.pk}")
    return f"{url}?{'&'.join(params)}" if params else url


def _move_url_from_cohort(
    organisation: Organisation, source: Cohort, learner: Learner
) -> str:
    url = _cohort_url(organisation, source, "/__tabs/learners/__actions/move")
    return f"{url}?learner={learner.pk}"


def _move_options(client: Client, url: str) -> set[str]:
    response = client.get(url, HTTP_HX_REQUEST="true")
    document = lxml.html.fromstring(response.content.decode())
    return {
        option.get("value") or ""
        for option in document.cssselect("select[name='destination'] option")
        if option.get("value")
    }


@pytest.mark.django_db
def test_move_fragment_offers_only_active_cohorts_the_learner_is_not_in(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    open_cohort = CohortFactory(organisation=organisation)
    CohortFactory(organisation=organisation, is_active=False)
    already_in = CohortFactory(organisation=organisation)
    CohortMembershipFactory(cohort=already_in, learner=learner)

    options = _move_options(
        staff_client, _move_url_from_learner(organisation, learner, source)
    )

    assert options == {str(open_cohort.pk)}


@pytest.mark.django_db
def test_move_fragment_names_courses_lost_gained_and_where_progress_continues(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation)
    shared = CourseFactory(title="Algebra")
    lost = CourseFactory(title="Botany")
    gained = CourseFactory(title="Chemistry")
    source_registration = CohortCourseRegistrationFactory(cohort=source, course=shared)
    CohortCourseRegistrationFactory(cohort=source, course=lost)
    CohortCourseRegistrationFactory(cohort=destination, course=shared)
    CohortCourseRegistrationFactory(cohort=destination, course=gained)
    CourseProgressFactory(
        learner=learner,
        course=shared,
        learner_registration=None,
        cohort_registration=source_registration,
        progress_percentage=40,
    )

    text = _get_fragment(
        staff_client,
        _move_url_from_learner(organisation, learner, source, destination),
    )

    assert "They lose access to: Botany." in text
    assert "They gain access to: Chemistry." in text
    assert "Algebra: continues at 40%" in text


@pytest.mark.django_db
def test_move_post_moves_the_membership_and_answers_204_with_both_events(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation)

    response = _post(
        staff_client,
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(destination.pk)},
    )

    trigger = json.loads(response["HX-Trigger"])
    assert response.status_code == 204
    assert set(trigger[COHORT_CHANGED]["ids"]) == {
        str(learner.pk),
        str(source.pk),
        str(destination.pk),
    }
    assert str(learner.pk) in trigger[LEARNER_CHANGED]["ids"]
    assert list(CohortMembership.objects.filter(learner=learner)) == [
        CohortMembership.objects.get(learner=learner, cohort=destination)
    ]


@pytest.mark.django_db
def test_move_post_from_the_cohort_page_moves_the_membership(staff_client: Client):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation)

    response = _post(
        staff_client,
        _move_url_from_cohort(organisation, source, learner),
        {"learner": str(learner.pk), "destination": str(destination.pk)},
    )

    assert response.status_code == 204
    assert CohortMembership.objects.filter(learner=learner, cohort=destination).exists()


@pytest.mark.django_db
def test_move_post_to_a_cohort_outside_the_users_grants_answers_403(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    unassigned = CohortFactory(organisation=organisation)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", source)

    response = _post(
        logged_in_client(educator),
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(unassigned.pk)},
    )

    assert response.status_code == 403
    assert CohortMembership.objects.filter(learner=learner, cohort=source).exists()


@pytest.mark.django_db
def test_a_cohort_admin_can_move_between_two_assigned_cohorts(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", source)
    assign_role(grantor, educator, "cohort_admin", destination)

    response = _post(
        logged_in_client(educator),
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(destination.pk)},
    )

    assert response.status_code == 204


@pytest.mark.django_db
def test_move_post_naming_an_inactive_source_answers_422_and_changes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation, is_active=False)
    destination = CohortFactory(organisation=organisation)

    response = _post(
        staff_client,
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(destination.pk)},
    )

    assert response.status_code == 422
    assert CohortMembership.objects.filter(learner=learner, cohort=source).exists()


@pytest.mark.django_db
def test_move_post_naming_an_inactive_destination_answers_422_and_changes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation, is_active=False)

    response = _post(
        staff_client,
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(destination.pk)},
    )

    assert response.status_code == 422
    assert CohortMembership.objects.filter(learner=learner, cohort=source).exists()


@pytest.mark.django_db
def test_move_422_rerender_offers_the_same_destinations_as_the_fresh_dialog(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    open_cohort = CohortFactory(organisation=organisation)
    CohortFactory(organisation=organisation, is_active=False)

    response = _post(
        staff_client,
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": ""},
    )

    document = lxml.html.fromstring(response.content.decode())
    options = {
        option.get("value")
        for option in document.cssselect("select[name='destination'] option")
        if option.get("value")
    }
    assert (response.status_code, options) == (422, {str(open_cohort.pk)})


@pytest.mark.django_db
def test_stale_move_dialog_for_a_departed_member_gives_the_reason_and_no_form(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    CohortMembership.objects.filter(learner=learner, cohort=source).delete()
    CohortFactory(organisation=organisation)

    response = staff_client.get(
        _move_url_from_learner(organisation, learner, source), HTTP_HX_REQUEST="true"
    )

    document = lxml.html.fromstring(response.content.decode())
    assert (
        response.status_code,
        len(document.cssselect("form")),
        "is no longer a member of" in response.content.decode(),
    ) == (200, 0, True)


@pytest.mark.django_db
def test_a_member_leaving_mid_move_answers_422_with_the_reason(
    staff_client: Client, monkeypatch: pytest.MonkeyPatch
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation)

    def leave_then_refuse(*args: object, **kwargs: object) -> str:
        CohortMembership.objects.filter(learner=learner, cohort=source).delete()
        raise ValueError("The learner is not a member of the source cohort.")

    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.move_between_cohorts",
        leave_then_refuse,
    )

    response = _post(
        staff_client,
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(destination.pk)},
    )

    assert (
        response.status_code,
        "is no longer a member of" in response.content.decode(),
    ) == (422, True)


@pytest.mark.django_db
def test_stale_move_post_for_a_departed_member_answers_422_with_the_reason(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation)
    CohortMembership.objects.filter(learner=learner, cohort=source).delete()

    response = _post(
        staff_client,
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(destination.pk)},
    )

    assert (
        response.status_code,
        "is no longer a member of" in response.content.decode(),
        CohortMembership.objects.filter(learner=learner).exists(),
    ) == (422, True, False)


# register and unregister a learner individually


def _learner_register_url(organisation: Organisation, learner: Learner) -> str:
    return _interface_url(
        organisation.slug, f"learners/{learner.pk}/__actions/register_for_course"
    )


def _learner_unregister_url(organisation: Organisation, learner: Learner) -> str:
    return _interface_url(
        organisation.slug,
        f"learners/{learner.pk}/__tabs/overview/__panels/registrations"
        "/__actions/deactivate_registration",
    )


@pytest.mark.django_db
def test_register_fragment_offers_the_registerable_courses(staff_client: Client):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    open_course = CourseFactory()
    coming_soon = CourseFactory(visibility=CourseVisibility.COMING_SOON)
    held = LearnerCourseRegistrationFactory(learner=learner, is_active=True).course

    offered = _offered_options(
        staff_client, _learner_register_url(organisation, learner)
    )

    assert offered == {str(open_course.pk)}
    assert str(coming_soon.pk) not in offered
    assert str(held.pk) not in offered


@pytest.mark.django_db
def test_register_post_creates_the_registration_with_both_events(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    course = CourseFactory()

    response = _post(
        staff_client,
        _learner_register_url(organisation, learner),
        {"course": str(course.pk)},
    )

    trigger = json.loads(response["HX-Trigger"])
    assert response.status_code == 204
    assert LearnerCourseRegistration.objects.filter(
        learner=learner, course=course, is_active=True
    ).exists()
    assert trigger[REGISTRATION_CHANGED] == {"ids": [str(learner.pk)]}
    assert trigger[LEARNER_CHANGED] == {"ids": [str(learner.pk)]}
    assert "closeModal" in trigger


@pytest.mark.django_db
def test_register_post_naming_a_coming_soon_course_answers_422_with_no_row(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

    response = _post(
        staff_client,
        _learner_register_url(organisation, learner),
        {"course": str(course.pk)},
    )

    assert response.status_code == 422
    assert not LearnerCourseRegistration.objects.filter(learner=learner).exists()


@pytest.mark.django_db
def test_unregister_fragment_names_the_cohort_keeping_access(staff_client: Client):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation, name="Year 10")
    course = CourseFactory(title="Algebra")
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    registration = LearnerCourseRegistrationFactory(learner=learner, course=course)

    text = _get_fragment(
        staff_client,
        _learner_unregister_url(organisation, learner)
        + f"?registration={registration.pk}",
    )

    assert "They keep access through Year 10." in text
    assert "Progress is kept." in text


@pytest.mark.django_db
def test_unregister_fragment_does_not_name_a_cohort_the_educator_cannot_see(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner, seen = _membership(organisation, name="Year 10")
    hidden = cast(Cohort, CohortFactory(organisation=organisation, name="Staff Room"))
    CohortMembershipFactory(cohort=hidden, learner=learner)
    course = CourseFactory(title="Algebra")
    CohortCourseRegistrationFactory(cohort=hidden, course=course)
    registration = LearnerCourseRegistrationFactory(learner=learner, course=course)
    educator = _cohort_admin_on(organisation, seen)

    text = _get_fragment(
        logged_in_client(educator),
        _learner_unregister_url(organisation, learner)
        + f"?registration={registration.pk}",
    )

    assert "Staff Room" not in text
    assert "They keep access through another cohort." in text


@pytest.mark.django_db
def test_unregister_fragment_says_the_learner_loses_access_without_a_cohort(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Algebra")
    )

    text = _get_fragment(
        staff_client,
        _learner_unregister_url(organisation, learner)
        + f"?registration={registration.pk}",
    )

    assert "They lose access to Algebra." in text


@pytest.mark.django_db
def test_unregister_fragment_names_self_registration_only_on_the_default_organisation(
    staff_client: Client, mock_site_context: Site
):
    default = get_default_organisation(mock_site_context)
    learner = cast(Learner, LearnerFactory(organisation=default))
    registration = LearnerCourseRegistrationFactory(learner=learner)

    text = _get_fragment(
        staff_client,
        _learner_unregister_url(default, learner) + f"?registration={registration.pk}",
    )

    assert "self-register" in text


@pytest.mark.django_db
def test_unregister_fragment_omits_self_registration_on_another_organisation(
    staff_client: Client,
):
    organisation = OrganisationFactory(is_default=False)
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner)

    text = _get_fragment(
        staff_client,
        _learner_unregister_url(organisation, learner)
        + f"?registration={registration.pk}",
    )

    assert "self-register" not in text


@pytest.mark.django_db
def test_unregister_post_deactivates_the_registration_with_both_events(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner)

    response = _post(
        staff_client,
        _learner_unregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    trigger = json.loads(response["HX-Trigger"])
    assert (response.status_code, registration.is_active) == (204, False)
    assert trigger[REGISTRATION_CHANGED] == {"ids": [str(learner.pk)]}
    assert trigger[LEARNER_CHANGED] == {"ids": [str(learner.pk)]}


@pytest.mark.django_db
def test_a_cohort_admin_can_register_a_learner_in_an_assigned_cohort(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)
    course = CourseFactory()
    educator = _cohort_admin_on(organisation, cohort)

    response = _post(
        logged_in_client(educator),
        _learner_register_url(organisation, learner),
        {"course": str(course.pk)},
    )

    assert response.status_code == 204
    assert LearnerCourseRegistration.objects.filter(
        learner=learner, course=course
    ).exists()


@pytest.mark.django_db
def test_a_cohort_admins_forged_register_on_a_learner_outside_their_cohorts_is_refused(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    _, cohort = _membership(organisation)
    outsider = cast(Learner, LearnerFactory(organisation=organisation))
    course = CourseFactory()
    educator = _cohort_admin_on(organisation, cohort)

    response = _post(
        logged_in_client(educator),
        _learner_register_url(organisation, outsider),
        {"course": str(course.pk)},
    )

    assert response.status_code == 404
    assert not LearnerCourseRegistration.objects.filter(learner=outsider).exists()


# re-register a learner individually


def _learner_reregister_url(organisation: Organisation, learner: Learner) -> str:
    return _interface_url(
        organisation.slug,
        f"learners/{learner.pk}/__tabs/overview/__panels/registrations"
        "/__actions/reactivate_registration",
    )


def _reregister_triggers(client: Client, url: str) -> list[str]:
    document = lxml.html.fromstring(client.get(url).content.decode())
    return [
        button.get("hx-get") or ""
        for button in document.cssselect("button[hx-get]")
        if "reactivate_registration" in (button.get("hx-get") or "")
    ]


@pytest.mark.django_db
def test_reregister_is_offered_on_an_inactive_individual_row_only(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    inactive = LearnerCourseRegistrationFactory(learner=learner, is_active=False)
    LearnerCourseRegistrationFactory(learner=learner, is_active=True)
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    CohortMembershipFactory(cohort=cohort, learner=learner)
    CohortCourseRegistrationFactory(cohort=cohort, is_active=False)

    triggers = _reregister_triggers(
        staff_client, _interface_url(organisation.slug, f"learners/{learner.pk}")
    )

    assert [t.split("?registration=")[1] for t in triggers] == [str(inactive.pk)]


@pytest.mark.django_db
def test_reregister_fragment_names_the_learner_and_the_course(staff_client: Client):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Algebra"), is_active=False
    )

    text = _get_fragment(
        staff_client,
        _learner_reregister_url(organisation, learner)
        + f"?registration={registration.pk}",
    )

    assert f"Reactivate {learner.user.display_name}'s registration for Algebra?" in text


@pytest.mark.django_db
def test_reregister_post_reactivates_the_registration_with_both_events(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=False)

    response = _post(
        staff_client,
        _learner_reregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    trigger = json.loads(response["HX-Trigger"])
    assert (response.status_code, registration.is_active) == (204, True)
    assert trigger[REGISTRATION_CHANGED] == {"ids": [str(learner.pk)]}
    assert trigger[LEARNER_CHANGED] == {"ids": [str(learner.pk)]}


@pytest.mark.django_db
def test_reregister_post_on_a_course_that_gained_another_organisation_answers_422(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=False)
    course = registration.course
    course.audience = CourseAudience.ORGANISATION_LEARNERS
    course.save()
    course.organisations.add(OrganisationFactory())

    response = _post(
        staff_client,
        _learner_reregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    assert (response.status_code, registration.is_active) == (422, False)
    assert COURSE_NOT_OPEN_MESSAGE in response.content.decode()


@pytest.mark.django_db
def test_reregister_post_naming_an_active_registration_answers_404(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=True)

    response = _post(
        staff_client,
        _learner_reregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_cohort_viewers_forged_reregister_answers_403(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=False)
    grantor = LearnerFactory(user__superuser=True).user
    viewer = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, viewer, "cohort_viewer", cohort)

    response = _post(
        logged_in_client(viewer),
        _learner_reregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    assert (response.status_code, registration.is_active) == (403, False)


# empty pickers


def _empty_picker_text(client: Client, url: str) -> str:
    """The text of a picker dialog that has nothing to offer, after checking
    it shows no select, no submit button and a Close button."""
    response = client.get(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    document = lxml.html.fromstring(response.content.decode())
    assert document.cssselect("select") == []
    assert document.cssselect("button[type='submit']") == []
    assert "Close" in [
        button.text_content().strip() for button in document.cssselect("button")
    ]
    return " ".join(document.text_content().split())


@pytest.mark.django_db
def test_an_empty_learner_picker_says_everyone_is_already_in_the_cohort(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    _, cohort = _membership(organisation, name="Cohort A")
    educator = _cohort_admin_on(organisation, cohort)

    text = _empty_picker_text(
        logged_in_client(educator), _add_learners_url(organisation, cohort)
    )

    assert (
        "Everyone in your other cohorts is already in Cohort A. To add someone new, "
        "ask an organisation admin." in text
    )


@pytest.mark.django_db
def test_a_stale_learner_picker_post_naming_a_member_answers_422_and_adds_nothing(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    member, cohort = _membership(organisation)
    educator = _cohort_admin_on(organisation, cohort)

    response = logged_in_client(educator).post(
        _add_learners_url(organisation, cohort),
        {"learners": [str(member.pk)]},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    assert CohortMembership.objects.filter(learner=member).count() == 1


@pytest.mark.django_db
def test_an_empty_add_to_cohort_picker_says_the_learner_is_in_every_cohort(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, _ = _membership(organisation)
    learner.user.first_name, learner.user.last_name = "Ada", "Lovelace"
    learner.user.save()

    text = _empty_picker_text(staff_client, _add_to_cohort_url(organisation, learner))

    assert (
        "Ada Lovelace is already in every active cohort you can add learners to."
        in text
    )


@pytest.mark.django_db
def test_a_stale_add_to_cohort_post_naming_a_cohort_they_are_in_answers_422(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)

    response = _post(
        staff_client,
        _add_to_cohort_url(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    assert response.status_code == 422
    assert CohortMembership.objects.filter(learner=learner).count() == 1


@pytest.mark.django_db
def test_an_empty_register_picker_says_there_is_no_course_to_register_for(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(
        Learner,
        LearnerFactory(
            organisation=organisation,
            user__first_name="",
            user__last_name="",
            user__email="pick@example.com",
        ),
    )
    LearnerCourseRegistrationFactory(learner=learner, is_active=True)

    text = _empty_picker_text(
        staff_client, _learner_register_url(organisation, learner)
    )

    assert "There is no course pick@example.com can be registered for right now." in (
        text
    )


@pytest.mark.django_db
def test_a_stale_register_post_naming_a_held_course_answers_422(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    course = LearnerCourseRegistrationFactory(learner=learner, is_active=True).course

    response = _post(
        staff_client,
        _learner_register_url(organisation, learner),
        {"course": str(course.pk)},
    )

    assert response.status_code == 422
    assert LearnerCourseRegistration.objects.filter(learner=learner).count() == 1


@pytest.mark.django_db
def test_an_empty_move_picker_says_there_is_no_other_cohort(staff_client: Client):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    learner.user.first_name, learner.user.last_name = "Ada", "Lovelace"
    learner.user.save()
    CohortFactory(organisation=organisation, is_active=False)

    text = _empty_picker_text(
        staff_client, _move_url_from_learner(organisation, learner, source)
    )

    assert "There is no other active cohort you can move Ada Lovelace to." in text


@pytest.mark.django_db
def test_a_stale_move_post_with_no_other_cohort_answers_422(staff_client: Client):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)

    response = _post(
        staff_client,
        _move_url_from_cohort(organisation, source, learner),
        {"learner": str(learner.pk), "destination": str(source.pk)},
    )

    assert response.status_code == 422
    assert CohortMembership.objects.filter(learner=learner, cohort=source).exists()


@pytest.mark.django_db
def test_a_picker_with_something_to_offer_keeps_its_submit_button(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    CohortFactory(organisation=organisation)

    response = staff_client.get(
        _add_to_cohort_url(organisation, learner), HTTP_HX_REQUEST="true"
    )

    document = lxml.html.fromstring(response.content.decode())
    assert document.cssselect("select[name='cohort']")
    assert document.cssselect("button[type='submit']")


@pytest.mark.django_db
def test_grantable_roles_are_cached_on_the_request(
    panel_request, django_assert_max_num_queries
) -> None:
    request = panel_request()
    request.user = UserFactory(superuser=True)
    grantable_roles_for(request)

    with django_assert_max_num_queries(0):
        grantable_roles_for(request)


# add member


def _add_member_url(organisation: Organisation) -> str:
    return _interface_url(organisation.slug, "members/__actions/add_member")


def _holder_client(
    logged_in_client, target: Organisation | Cohort, role: str = "organisation_admin"
) -> tuple[Client, User]:
    user = cast(User, UserFactory(staff=True))
    assign_role(UserFactory(superuser=True), user, role, target)
    return logged_in_client(user), user


def _lookup(client: Client, organisation: Organisation, email: str):
    return _post(
        client, _add_member_url(organisation), {"step": "lookup", "email": email}
    )


def _submit_role(
    client: Client,
    organisation: Organisation,
    email: str,
    role: str,
    **extra: str,
):
    return _post(
        client,
        _add_member_url(organisation),
        {"step": "submit", "email": email, "role": role, **extra},
    )


def _confirm(
    client: Client, organisation: Organisation, email: str, role: str, **extra: str
):
    return _submit_role(client, organisation, email, role, confirmed="1", **extra)


def _text(response) -> str:
    return " ".join(
        lxml.html.fromstring(response.content.decode()).text_content().split()
    )


@pytest.fixture
def organisation(mock_site_context: Site) -> Organisation:
    return cast(Organisation, OrganisationFactory())


@pytest.fixture
def admin_client(logged_in_client, organisation: Organisation) -> Client:
    CohortFactory(organisation=organisation)
    return _holder_client(logged_in_client, organisation)[0]


@pytest.mark.django_db
def test_the_email_step_asks_for_an_address(admin_client, organisation):
    response = admin_client.get(_add_member_url(organisation), HTTP_HX_REQUEST="true")

    document = lxml.html.fromstring(response.content.decode())
    assert document.cssselect("input[name='email']")


@pytest.mark.django_db
def test_the_lookup_shows_an_existing_accounts_name_and_email(
    admin_client, organisation
):
    UserFactory(first_name="Ada", last_name="Lovelace", email="ada@example.com")

    text = _text(_lookup(admin_client, organisation, "ada@example.com"))

    assert "Existing account: Ada Lovelace, ada@example.com" in text


@pytest.mark.django_db
def test_the_lookup_creates_no_user(admin_client, organisation):
    UserFactory(email="ada@example.com")
    before = User._base_manager.count()

    _lookup(admin_client, organisation, "ada@example.com")
    _lookup(admin_client, organisation, "nobody@example.com")

    assert User._base_manager.count() == before


@pytest.mark.django_db
def test_the_lookup_of_another_sites_address_shows_the_message_and_no_name(
    admin_client, organisation
):
    User._base_manager.create(
        site=SiteFactory(), email="away@example.com", first_name="Awaynamed"
    )

    response = _lookup(admin_client, organisation, "away@example.com")

    text = _text(response)
    assert response.status_code == 422
    assert "belongs to an account on another site" in text
    assert "Awaynamed" not in text


@pytest.mark.django_db
def test_the_lookup_of_an_unknown_address_says_an_account_will_be_created(
    admin_client, organisation
):
    response = _lookup(admin_client, organisation, "nobody@example.com")

    assert response.status_code == 200
    assert "No account yet. One will be created and a setup email sent." in _text(
        response
    )


@pytest.mark.django_db
def test_the_lookup_of_an_unknown_address_offers_optional_name_fields(
    admin_client, organisation
):
    response = _lookup(admin_client, organisation, "nobody@example.com")

    document = lxml.html.fromstring(response.content.decode())
    assert document.cssselect("input[name='first_name']")
    assert document.cssselect("input[name='last_name']")
    assert document.cssselect("input[name='role']")


@pytest.mark.django_db
def test_the_lookup_of_an_existing_address_offers_no_name_fields(
    admin_client, organisation
):
    UserFactory(email="ada@example.com")

    response = _lookup(admin_client, organisation, "ada@example.com")

    document = lxml.html.fromstring(response.content.decode())
    assert not document.cssselect("input[name='first_name']")


@pytest.mark.django_db
def test_the_lookup_of_an_unknown_address_creates_nothing(admin_client, organisation):
    _lookup(admin_client, organisation, "nobody@example.com")

    assert not EmailAddress.objects.filter(email="nobody@example.com").exists()


@pytest.mark.django_db
def test_the_confirmation_for_an_unknown_address_says_an_account_will_be_created(
    admin_client, organisation
):
    response = _submit_role(
        admin_client,
        organisation,
        "nobody@example.com",
        "organisation_admin",
        first_name="Ada",
    )

    document = lxml.html.fromstring(response.content.decode())
    assert (
        "An account will be created for nobody@example.com and a setup email sent."
        in _text(response)
    )
    assert document.cssselect("input[type='hidden'][name='first_name'][value='Ada']")
    assert not User._base_manager.filter(email="nobody@example.com").exists()


@pytest.mark.django_db
def test_confirming_an_unknown_address_creates_the_account_with_the_names_and_role(
    admin_client, organisation
):
    _confirm(
        admin_client,
        organisation,
        "nobody@example.com",
        "organisation_admin",
        first_name="Ada",
        last_name="Lovelace",
    )

    user = User.objects.get(email="nobody@example.com")
    assert (user.first_name, user.last_name) == ("Ada", "Lovelace")
    assert EmailAddress.objects.filter(user=user).count() == 1
    assert ObjectRoleAssignment.objects.filter(
        user=user, role="organisation_admin"
    ).exists()


@pytest.mark.django_db
def test_confirming_an_unknown_address_sends_one_setup_email(
    admin_client, organisation, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        _confirm(admin_client, organisation, "nobody@example.com", "organisation_admin")

    assert [message.to for message in mail.outbox] == [["nobody@example.com"]]


@pytest.mark.django_db
def test_a_refusal_after_the_account_step_rolls_the_account_back(
    admin_client, organisation, monkeypatch, django_capture_on_commit_callbacks
):
    def refuse(*args: object, **kwargs: object) -> None:
        raise RoleChangeRefused(RefusalReason.NOT_PERMITTED)

    monkeypatch.setattr("freedom_ls.educator_interface.actions.assign_role", refuse)

    with django_capture_on_commit_callbacks(execute=True):
        response = _confirm(
            admin_client, organisation, "nobody@example.com", "organisation_admin"
        )

    assert response.status_code == 403
    assert not User._base_manager.filter(email="nobody@example.com").exists()
    assert not EmailAddress.objects.filter(email="nobody@example.com").exists()
    assert mail.outbox == []


@pytest.mark.django_db
def test_the_lookup_of_an_invalid_address_is_422(admin_client, organisation):
    response = _lookup(admin_client, organisation, "not-an-email")

    assert response.status_code == 422


@pytest.mark.django_db
def test_the_role_step_offers_the_three_member_roles_with_their_descriptions(
    admin_client, organisation
):
    UserFactory(email="ada@example.com")
    config = get_role_config(organisation.site.name)

    response = _lookup(admin_client, organisation, "ada@example.com")

    document = lxml.html.fromstring(response.content.decode())
    offered = [r.get("value") for r in document.cssselect("input[name='role']")]
    text = _text(response)
    assert offered == ["organisation_admin", "cohort_admin", "cohort_viewer"]
    assert all(config[role].description in text for role in offered)
    assert not document.cssselect("input[name='role'][checked]")


@pytest.mark.django_db
def test_a_site_admin_is_offered_three_roles(
    mock_site_context, logged_in_client, organisation
):
    CohortFactory(organisation=organisation)
    site_admin = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True), site_admin, "site_admin", organisation.site
    )
    UserFactory(email="ada@example.com")

    response = _lookup(logged_in_client(site_admin), organisation, "ada@example.com")

    document = lxml.html.fromstring(response.content.decode())
    assert len(document.cssselect("input[name='role']")) == 3


@pytest.mark.django_db
def test_with_no_active_cohort_only_organisation_admin_is_offered(
    mock_site_context, logged_in_client, organisation
):
    client, _ = _holder_client(logged_in_client, organisation)
    UserFactory(email="ada@example.com")

    response = _lookup(client, organisation, "ada@example.com")

    document = lxml.html.fromstring(response.content.decode())
    assert [r.get("value") for r in document.cssselect("input[name='role']")] == [
        "organisation_admin"
    ]
    assert "This organisation has no active cohorts yet." in _text(response)


@pytest.mark.django_db
def test_a_member_role_the_grantor_cannot_give_is_explained(
    admin_client, organisation, monkeypatch
):
    UserFactory(email="ada@example.com")
    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.grantable_roles",
        lambda *args: [GrantableRole("organisation_admin", None)],
    )

    text = _text(_lookup(admin_client, organisation, "ada@example.com"))

    assert "You can only give roles at or below your own." in text


@pytest.mark.django_db
def test_submitting_without_confirmation_shows_the_confirmation_and_writes_nothing(
    admin_client, organisation
):
    UserFactory(email="ada@example.com", first_name="Ada", last_name="Lovelace")
    roles_before = ObjectRoleAssignment.objects.count()
    members_before = OrganisationMember.objects.count()
    config = get_role_config(organisation.site.name)["organisation_admin"]

    response = _submit_role(
        admin_client, organisation, "ada@example.com", "organisation_admin"
    )

    text = _text(response)
    assert response.status_code == 200
    assert "Add Ada Lovelace as Organisation admin" in text
    assert config.description in text
    assert "Scope: Whole organisation." in text
    assert (
        ObjectRoleAssignment.objects.count(),
        OrganisationMember.objects.count(),
    ) == (
        roles_before,
        members_before,
    )


@pytest.mark.django_db
def test_the_confirmation_lists_the_current_and_after_roles(
    mock_site_context, logged_in_client, organisation
):
    cohort = CohortFactory(organisation=organisation, name="Alpha")
    client, _ = _holder_client(logged_in_client, organisation)
    holder = UserFactory(email="ada@example.com")
    assign_role(UserFactory(superuser=True), holder, "cohort_viewer", cohort)

    text = _text(
        _submit_role(client, organisation, "ada@example.com", "organisation_admin")
    )

    assert "Now Cohort viewer: Alpha After" in text
    assert "Organisation admin: Whole organisation" in text


@pytest.mark.django_db
def test_confirming_grants_organisation_admin_and_fires_member_changed(
    admin_client, organisation
):
    user = UserFactory(email="ada@example.com")

    response = _confirm(
        admin_client, organisation, "ada@example.com", "organisation_admin"
    )

    trigger = json.loads(response["HX-Trigger"])
    assert response.status_code == 204
    assert trigger[MEMBER_CHANGED] == {"ids": [str(user.pk)]}
    assert ObjectRoleAssignment.objects.filter(
        user=user, role="organisation_admin", object_id=str(organisation.pk)
    ).exists()


@pytest.mark.django_db
def test_granting_organisation_admin_to_a_holder_is_422_with_the_message(
    admin_client, organisation
):
    holder = UserFactory(email="ada@example.com", first_name="Ada", last_name="L")
    assign_role(UserFactory(superuser=True), holder, "organisation_admin", organisation)

    response = _submit_role(
        admin_client, organisation, "ada@example.com", "organisation_admin"
    )

    assert response.status_code == 422
    assert "Ada L is already an organisation admin here." in _text(response)


@pytest.mark.django_db
def test_a_confirmed_grant_of_organisation_admin_to_a_holder_is_422_and_restamps_nothing(
    admin_client, organisation
):
    """Two admins can open the dialog for the same person; the second to
    confirm must not overwrite who granted the role and when."""
    holder = UserFactory(email="ada@example.com", first_name="Ada", last_name="L")
    original_grantor = UserFactory(superuser=True)
    assign_role(original_grantor, holder, "organisation_admin", organisation)
    assignment = ObjectRoleAssignment.objects.get(
        user=holder, role="organisation_admin"
    )
    stamped_at = assignment.assigned_at

    response = _confirm(
        admin_client, organisation, "ada@example.com", "organisation_admin"
    )

    assert response.status_code == 422
    assert "Ada L is already an organisation admin here." in _text(response)
    assignment.refresh_from_db()
    assert assignment.assigned_by == original_grantor
    assert assignment.assigned_at == stamped_at


@pytest.mark.django_db
def test_a_role_outside_the_grantors_reach_is_the_403_fragment_and_writes_nothing(
    admin_client, organisation, monkeypatch
):
    cohort = CohortFactory(organisation=organisation)
    target = UserFactory(email="ada@example.com")
    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.grantable_roles",
        lambda *args: [GrantableRole("cohort_viewer", (cohort,))],
    )

    response = _confirm(
        admin_client, organisation, "ada@example.com", "organisation_admin"
    )

    assert response.status_code == 403
    assert not ObjectRoleAssignment.objects.filter(user=target).exists()


@pytest.mark.django_db
def test_a_cohort_role_is_checked_against_that_roles_own_cohorts(
    admin_client, organisation, monkeypatch
):
    allowed = CohortFactory(organisation=organisation)
    other = CohortFactory(organisation=organisation)
    target = UserFactory(email="ada@example.com")
    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.grantable_roles",
        lambda *args: [
            GrantableRole("cohort_admin", (other,)),
            GrantableRole("cohort_viewer", (allowed,)),
        ],
    )

    response = _confirm(
        admin_client,
        organisation,
        "ada@example.com",
        "cohort_viewer",
        cohorts=str(other.pk),
    )

    assert response.status_code == 403
    assert not ObjectRoleAssignment.objects.filter(user=target).exists()


@pytest.mark.django_db
def test_a_user_with_nothing_to_grant_is_denied_at_the_lookup(
    mock_site_context, logged_in_client, organisation, monkeypatch
):
    client, _ = _holder_client(logged_in_client, organisation)
    UserFactory(email="ada@example.com")
    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.grantable_roles", lambda *a: []
    )

    response = _lookup(client, organisation, "ada@example.com")

    assert response.status_code == 403
    assert "Ada" not in _text(response)


@pytest.mark.django_db
def test_a_refused_grant_to_oneself_is_422_with_the_message(
    mock_site_context, logged_in_client, organisation
):
    CohortFactory(organisation=organisation)
    client, me = _holder_client(logged_in_client, organisation)

    response = _confirm(client, organisation, me.email, "cohort_admin")

    assert response.status_code == 422


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("reason", "message"),
    [
        (
            RefusalReason.SELF,
            "You can't change your own roles. Ask another organisation admin.",
        ),
        (
            RefusalReason.INACTIVE_USER,
            "This person's account is turned off, so they can't be given a role.",
        ),
    ],
)
def test_each_refusal_answers_422_with_its_message(
    admin_client, organisation, monkeypatch, reason, message
):
    UserFactory(email="ada@example.com")

    def refuse(*args: object, **kwargs: object) -> None:
        raise RoleChangeRefused(reason)

    monkeypatch.setattr("freedom_ls.educator_interface.actions.assign_role", refuse)

    response = _confirm(
        admin_client, organisation, "ada@example.com", "organisation_admin"
    )

    assert (response.status_code, message in _text(response)) == (422, True)


@pytest.mark.django_db
def test_a_not_permitted_refusal_is_the_403_fragment(
    admin_client, organisation, monkeypatch
):
    UserFactory(email="ada@example.com")

    def refuse(*args: object, **kwargs: object) -> None:
        raise RoleChangeRefused(RefusalReason.NOT_PERMITTED)

    monkeypatch.setattr("freedom_ls.educator_interface.actions.assign_role", refuse)

    response = _confirm(
        admin_client, organisation, "ada@example.com", "organisation_admin"
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_a_turned_off_account_cannot_be_given_a_role(admin_client, organisation):
    UserFactory(email="ada@example.com", is_active=False)

    response = _confirm(
        admin_client, organisation, "ada@example.com", "organisation_admin"
    )

    assert response.status_code == 422
    assert "account is turned off" in _text(response)


@pytest.mark.django_db
def test_a_confirmed_post_for_another_sites_address_is_422_and_writes_nothing(
    admin_client, organisation
):
    away = User._base_manager.create(
        site=SiteFactory(), email="away@example.com", first_name="Awaynamed"
    )

    response = _confirm(
        admin_client, organisation, "away@example.com", "organisation_admin"
    )

    text = _text(response)
    assert response.status_code == 422
    assert "belongs to an account on another site" in text
    assert "Awaynamed" not in text
    assert not ObjectRoleAssignment.objects.filter(user_id=away.pk).exists()


@pytest.mark.django_db
def test_the_confirmation_for_a_site_level_admin_says_they_already_have_access(
    admin_client, organisation
):
    site_admin = UserFactory(email="boss@example.com")
    assign_role(
        UserFactory(superuser=True), site_admin, "site_admin", organisation.site
    )

    text = _text(
        _submit_role(
            admin_client, organisation, "boss@example.com", "organisation_admin"
        )
    )

    assert "already has access to every organisation" in text


@pytest.mark.django_db
def test_the_confirmation_for_a_suspended_member_says_the_role_waits_for_reactivation(
    admin_client, organisation
):
    cohort = CohortFactory(organisation=organisation)
    suspended = UserFactory(email="ada@example.com")
    assign_role(UserFactory(superuser=True), suspended, "cohort_viewer", cohort)
    OrganisationMember.objects.filter(user=suspended).update(is_active=False)

    text = _text(
        _submit_role(
            admin_client, organisation, "ada@example.com", "organisation_admin"
        )
    )
    _confirm(admin_client, organisation, "ada@example.com", "organisation_admin")

    assert "takes effect only once they are reactivated" in text
    assert not OrganisationMember.objects.get(user=suspended).is_active


@pytest.mark.django_db
def test_a_grant_to_someone_with_no_member_row_creates_an_active_one(
    admin_client, organisation
):
    user = UserFactory(email="ada@example.com")

    text = _text(
        _submit_role(
            admin_client, organisation, "ada@example.com", "organisation_admin"
        )
    )
    _confirm(admin_client, organisation, "ada@example.com", "organisation_admin")

    assert "Adding this role creates one" in text
    assert OrganisationMember.objects.get(
        user=user, organisation=organisation
    ).is_active


@pytest.mark.django_db
def test_a_cohort_admin_reaching_the_add_member_url_gets_404(
    mock_site_context, logged_in_client, organisation
):
    cohort = CohortFactory(organisation=organisation)
    client, _ = _holder_client(logged_in_client, cohort, "cohort_admin")

    response = client.get(_add_member_url(organisation), HTTP_HX_REQUEST="true")

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_empty_members_page_offers_add_member_in_the_header_and_the_empty_state(
    mock_site_context, logged_in_client, organisation
):
    site_admin = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True), site_admin, "site_admin", organisation.site
    )

    html = (
        logged_in_client(site_admin)
        .get(_interface_url(organisation.slug, "members"))
        .content.decode()
    )

    header, _, empty_state = html.partition("No members in this organisation yet.")
    assert "/members/__actions/add_member" in header
    assert "/members/__actions/add_member" in empty_state


@pytest.mark.django_db
def test_the_members_page_header_holds_the_add_member_trigger(
    admin_client, organisation
):
    html = admin_client.get(
        _interface_url(organisation.slug, "members")
    ).content.decode()

    assert "/members/__actions/add_member" in html


@pytest.mark.django_db
def test_a_site_admin_with_nothing_to_grant_sees_no_add_member_trigger(
    mock_site_context, logged_in_client, organisation, monkeypatch
):
    site_admin = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True), site_admin, "site_admin", organisation.site
    )
    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.grantable_roles", lambda *a: []
    )

    html = (
        logged_in_client(site_admin)
        .get(_interface_url(organisation.slug, "members"))
        .content.decode()
    )

    assert "/members/__actions/add_member" not in html


def _cohort(organisation: Organisation, **kwargs: str) -> Cohort:
    return cast(Cohort, CohortFactory(organisation=organisation, **kwargs))


def _cohort_post(
    client: Client,
    organisation: Organisation,
    role: str,
    cohorts: list[Cohort],
    confirmed: bool = False,
):
    data: dict[str, str | list[str]] = {
        "step": "submit",
        "email": "ada@example.com",
        "role": role,
        "cohorts": [str(cohort.pk) for cohort in cohorts],
    }
    if confirmed:
        data["confirmed"] = "1"
    return _post(client, _add_member_url(organisation), data)


@pytest.mark.django_db
def test_the_role_step_lists_each_grantable_cohort_with_the_roles_it_is_offered_for(
    admin_client, organisation, monkeypatch
):
    admin_only = _cohort(organisation, name="Alpha")
    both = _cohort(organisation, name="Beta")
    UserFactory(email="ada@example.com")
    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.grantable_roles",
        lambda *args: [
            GrantableRole("cohort_admin", (admin_only, both)),
            GrantableRole("cohort_viewer", (both,)),
        ],
    )

    response = _lookup(admin_client, organisation, "ada@example.com")

    rows = lxml.html.fromstring(response.content.decode()).cssselect(
        "[data-cohort-row]"
    )
    assert [(r.get("data-name"), r.get("data-roles")) for r in rows] == [
        ("alpha", "cohort_admin"),
        ("beta", "cohort_admin cohort_viewer"),
    ]


@pytest.mark.django_db
def test_the_role_step_explains_that_every_cohort_is_not_organisation_admin(
    admin_client, organisation
):
    UserFactory(email="ada@example.com")

    response = _lookup(admin_client, organisation, "ada@example.com")

    assert "Choosing every cohort is not the same as organisation admin" in _text(
        response
    )


@pytest.mark.django_db
def test_a_cohort_role_without_a_cohort_is_422_on_the_role_step(
    admin_client, organisation
):
    UserFactory(email="ada@example.com")

    response = _cohort_post(admin_client, organisation, "cohort_admin", [])

    assert response.status_code == 422
    assert "Choose at least one cohort." in _text(response)


@pytest.mark.django_db
def test_the_confirmation_names_the_cohorts_escaped(admin_client, organisation):
    cohort = _cohort(organisation, name="<b>Bold</b> cohort")
    UserFactory(email="ada@example.com")

    response = _cohort_post(admin_client, organisation, "cohort_admin", [cohort])

    html = response.content.decode()
    assert "&lt;b&gt;Bold&lt;/b&gt; cohort" in html
    assert "<b>Bold</b>" not in html


@pytest.mark.django_db
def test_a_weaker_role_on_a_cohort_already_held_with_a_stronger_one_is_no_widening(
    admin_client, organisation
):
    cohort = _cohort(organisation, name="Spring")
    holder = UserFactory(email="ada@example.com")
    assign_role(UserFactory(superuser=True), holder, "cohort_admin", cohort)

    response = _cohort_post(admin_client, organisation, "cohort_viewer", [cohort])

    text = _text(response)
    assert "Cohort viewer" in text
    assert "will be able to do more than they can now" not in text


@pytest.mark.django_db
def test_the_confirmation_for_new_cohorts_says_what_the_person_gains(
    admin_client, organisation
):
    cohort = _cohort(organisation, name="Spring")
    UserFactory(email="ada@example.com")

    response = _cohort_post(admin_client, organisation, "cohort_admin", [cohort])

    assert "will be able to do more than they can now" in _text(response)


@pytest.mark.django_db
def test_confirming_grants_the_role_on_each_cohort(admin_client, organisation):
    first = _cohort(organisation)
    second = _cohort(organisation)
    user = UserFactory(email="ada@example.com")

    response = _cohort_post(
        admin_client, organisation, "cohort_admin", [first, second], confirmed=True
    )

    granted = set(
        ObjectRoleAssignment.objects.filter(user=user, role="cohort_admin").values_list(
            "object_id", flat=True
        )
    )
    assert (response.status_code, granted) == (204, {str(first.pk), str(second.pk)})


@pytest.mark.django_db
def test_a_role_already_held_on_every_chosen_cohort_is_422(admin_client, organisation):
    cohort = _cohort(organisation)
    holder = UserFactory(email="ada@example.com", first_name="Ada", last_name="L")
    assign_role(UserFactory(superuser=True), holder, "cohort_admin", cohort)

    response = _cohort_post(admin_client, organisation, "cohort_admin", [cohort])

    assert response.status_code == 422
    assert "Ada L already holds this role on these cohorts." in _text(response)


@pytest.mark.django_db
def test_a_partial_overlap_names_the_held_cohorts_in_the_confirmation(
    admin_client, organisation
):
    held = _cohort(organisation, name="Held cohort")
    new = _cohort(organisation, name="New cohort")
    holder = UserFactory(email="ada@example.com")
    assign_role(UserFactory(superuser=True), holder, "cohort_admin", held)

    response = _cohort_post(admin_client, organisation, "cohort_admin", [held, new])

    text = _text(response)
    assert "Scope: New cohort." in text
    assert "already holds this role on Held cohort" in text


@pytest.mark.django_db
def test_a_partial_overlap_grants_only_the_new_cohorts(admin_client, organisation):
    held = _cohort(organisation)
    new = _cohort(organisation)
    holder = UserFactory(email="ada@example.com")
    assign_role(UserFactory(superuser=True), holder, "cohort_admin", held)

    response = _cohort_post(
        admin_client, organisation, "cohort_admin", [held, new], confirmed=True
    )

    granted = set(
        ObjectRoleAssignment.objects.filter(
            user=holder, role="cohort_admin"
        ).values_list("object_id", flat=True)
    )
    assert (response.status_code, granted) == (204, {str(held.pk), str(new.pk)})


@pytest.mark.django_db
def test_a_cohort_outside_the_chosen_roles_grantable_cohorts_is_the_403_fragment(
    admin_client, organisation, monkeypatch
):
    allowed = _cohort(organisation)
    outside = _cohort(organisation)
    user = UserFactory(email="ada@example.com")
    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.grantable_roles",
        lambda *args: [GrantableRole("cohort_admin", (allowed,))],
    )

    response = _cohort_post(
        admin_client, organisation, "cohort_admin", [outside], confirmed=True
    )

    assert response.status_code == 403
    assert not ObjectRoleAssignment.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_a_cohort_of_another_organisation_is_a_form_error_and_writes_nothing(
    admin_client, organisation
):
    foreign = _cohort(cast(Organisation, OrganisationFactory()))
    user = UserFactory(email="ada@example.com")

    response = _cohort_post(
        admin_client, organisation, "cohort_admin", [foreign], confirmed=True
    )

    assert response.status_code == 422
    assert not ObjectRoleAssignment.objects.filter(user=user).exists()


def _remove_role_url(organisation: Organisation) -> str:
    return _interface_url(organisation.slug, "members/__actions/deactivate_role")


def _member_holding(
    role: str, target: Organisation | Cohort | list[Cohort], **fields: str
) -> User:
    user = cast(User, UserFactory(**fields))
    for each in target if isinstance(target, list) else [target]:
        assign_role(UserFactory(superuser=True), user, role, each)
    return user


def _remove_dialog(client: Client, organisation: Organisation, user: User, role: str):
    return client.get(
        _remove_role_url(organisation),
        {"user": str(user.pk), "role": role},
        HTTP_HX_REQUEST="true",
    )


def _remove(client: Client, organisation: Organisation, user: User, role: str):
    return _post(
        client, _remove_role_url(organisation), {"user": str(user.pk), "role": role}
    )


def _active_roles(user: User) -> set[tuple[str, str]]:
    return {
        (a.role, a.object_id)
        for a in ObjectRoleAssignment.objects.filter(user=user, is_active=True)
    }


@pytest.mark.django_db
def test_the_remove_confirmation_names_the_person_the_role_and_the_scope(
    admin_client, organisation
):
    cohort = _cohort(organisation, name="Evening group")
    user = _member_holding(
        "cohort_admin", cohort, first_name="Ada", last_name="Lovelace"
    )

    text = _text(_remove_dialog(admin_client, organisation, user, "cohort_admin"))

    assert "Deactivate Cohort admin for Ada Lovelace" in text
    assert (
        "They lose Cohort admin on Evening group: Manages the learners and course registrations in their cohorts."
        in text
    )


@pytest.mark.django_db
def test_the_remove_confirmation_names_every_cohort_without_truncating(
    admin_client, organisation
):
    """The sentence used to splice a verb phrase after "They lose" and reuse
    the list's shortened scope, hiding cohorts that were being lost."""
    cohorts = [
        _cohort(organisation, name="Cohort A"),
        _cohort(organisation, name="Cohort B"),
        _cohort(organisation, name="Cohort C"),
    ]
    user = _member_holding("cohort_admin", cohorts)

    text = _text(_remove_dialog(admin_client, organisation, user, "cohort_admin"))

    assert "They lose Cohort admin on Cohort A, Cohort B and Cohort C: " in text


@pytest.mark.django_db
def test_the_remove_confirmation_lists_what_the_person_keeps(
    admin_client, organisation
):
    cohort = _cohort(organisation, name="Evening group")
    user = _member_holding("cohort_admin", cohort)
    assign_role(UserFactory(superuser=True), user, "cohort_viewer", cohort)
    LearnerFactory(user=user, organisation=organisation)

    text = _text(_remove_dialog(admin_client, organisation, user, "cohort_admin"))

    assert (
        "They keep their account, Cohort viewer on Evening group "
        "and their learner access in this organisation."
    ) in text


@pytest.mark.django_db
def test_the_remove_confirmation_loads_the_persons_roles_once(
    admin_client, organisation, monkeypatch
):
    cohort = _cohort(organisation)
    user = _member_holding("cohort_admin", cohort)
    assign_role(UserFactory(superuser=True), user, "cohort_viewer", cohort)
    calls: list[User] = []
    real_entries = current_role_entries

    def counting(target_user, target_organisation):
        calls.append(target_user)
        return real_entries(target_user, target_organisation)

    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.current_role_entries", counting
    )

    response = _remove_dialog(admin_client, organisation, user, "cohort_admin")

    assert response.status_code == 200
    assert "They keep their account and Cohort viewer on" in _text(response)
    assert len(calls) == 1


@pytest.mark.django_db
def test_the_remove_confirmation_writes_nothing(admin_client, organisation):
    user = _member_holding("cohort_admin", _cohort(organisation))
    before = _active_roles(user)

    _remove_dialog(admin_client, organisation, user, "cohort_admin")

    assert _active_roles(user) == before


@pytest.mark.django_db
def test_a_confirmed_removal_ends_the_role_on_every_cohort_of_the_entry(
    admin_client, organisation
):
    cohorts = [_cohort(organisation), _cohort(organisation)]
    user = _member_holding("cohort_viewer", cohorts)

    response = _remove(admin_client, organisation, user, "cohort_viewer")

    assert response.status_code == 204
    assert _active_roles(user) == set()
    assert json.loads(response["HX-Trigger"])[MEMBER_CHANGED] == {"ids": [str(user.pk)]}


def _reach_only(monkeypatch, *cohorts: Cohort) -> None:
    """Make the grantor able to give and take roles on `cohorts` alone."""
    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.cohorts_visible_to",
        lambda *args, **kwargs: Cohort.objects.filter(pk__in=[c.pk for c in cohorts]),
    )


@pytest.mark.django_db
def test_a_confirmed_removal_leaves_a_cohort_outside_the_grantors_reach(
    admin_client, organisation, monkeypatch
):
    reachable = _cohort(organisation)
    unreachable = _cohort(organisation)
    user = _member_holding("cohort_viewer", [reachable, unreachable])
    _reach_only(monkeypatch, reachable)

    response = _remove(admin_client, organisation, user, "cohort_viewer")

    assert response.status_code == 204
    assert _active_roles(user) == {("cohort_viewer", str(unreachable.pk))}


@pytest.mark.django_db
def test_the_remove_confirmation_names_the_cohort_that_stays_out_of_reach(
    admin_client, organisation, monkeypatch
):
    reachable = _cohort(organisation, name="Reachable")
    unreachable = _cohort(organisation, name="Beyond reach")
    user = _member_holding("cohort_viewer", [reachable, unreachable])
    _reach_only(monkeypatch, reachable)

    text = _text(_remove_dialog(admin_client, organisation, user, "cohort_viewer"))

    assert "They lose Cohort viewer on Reachable:" in text
    assert (
        "Cohort viewer on Beyond reach is outside the cohorts you can give, so it stays."
        in text
    )


@pytest.mark.django_db
def test_a_removal_with_no_cohort_in_reach_is_refused_and_writes_nothing(
    admin_client, organisation, monkeypatch
):
    unreachable = _cohort(organisation)
    user = _member_holding("cohort_viewer", unreachable)
    _reach_only(monkeypatch, _cohort(organisation))
    before = _active_roles(user)

    dialog = _remove_dialog(admin_client, organisation, user, "cohort_viewer")
    response = _remove(admin_client, organisation, user, "cohort_viewer")

    assert dialog.status_code == 404
    assert response.status_code == 403
    assert _active_roles(user) == before


@pytest.mark.django_db
def test_a_confirmed_removal_leaves_the_other_roles_and_the_member_row(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    user = _member_holding("cohort_admin", cohort)
    assign_role(UserFactory(superuser=True), user, "cohort_viewer", cohort)

    _remove(admin_client, organisation, user, "cohort_admin")

    assert _active_roles(user) == {("cohort_viewer", str(cohort.pk))}
    assert OrganisationMember.objects.get(
        user=user, organisation=organisation
    ).is_active


@pytest.mark.django_db
def test_the_remove_confirmation_for_a_site_level_target_says_their_access_is_unaffected(
    admin_client, organisation
):
    user = _member_holding("cohort_viewer", _cohort(organisation))
    assign_role(UserFactory(superuser=True), user, "site_admin", organisation.site)

    text = _text(_remove_dialog(admin_client, organisation, user, "cohort_viewer"))

    assert "Their site-level access is unaffected" in text


@pytest.mark.django_db
def test_an_organisation_admin_removing_the_last_organisation_admin_is_422(
    admin_client, organisation, monkeypatch
):
    sole = _member_holding("organisation_admin", organisation)
    monkeypatch.setattr(
        "freedom_ls.learner_management.role_assignment.is_last_organisation_admin",
        lambda *args: True,
    )

    response = _remove(admin_client, organisation, sole, "organisation_admin")

    assert response.status_code == 422
    assert "only organisation admin" in _text(response)
    assert _active_roles(sole) == {("organisation_admin", str(organisation.pk))}


@pytest.mark.django_db
def test_a_site_admin_removing_the_last_organisation_admin_is_warned_then_succeeds(
    mock_site_context, logged_in_client, organisation
):
    sole = _member_holding(
        "organisation_admin", organisation, first_name="Ada", last_name="Lovelace"
    )
    site_admin = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True), site_admin, "site_admin", organisation.site
    )
    client = logged_in_client(site_admin)

    dialog = _text(_remove_dialog(client, organisation, sole, "organisation_admin"))
    response = _remove(client, organisation, sole, "organisation_admin")

    assert "Ada Lovelace is the only organisation admin." in dialog
    assert response.status_code == 204
    assert _active_roles(sole) == set()


@pytest.mark.django_db
def test_the_warning_is_absent_when_another_organisation_admin_remains(
    admin_client, organisation
):
    other = _member_holding("organisation_admin", organisation)

    text = _text(
        _remove_dialog(admin_client, organisation, other, "organisation_admin")
    )

    assert "only organisation admin" not in text


@pytest.mark.django_db
def test_removing_your_own_role_is_422_with_the_self_message(
    mock_site_context, logged_in_client, organisation
):
    client, me = _holder_client(logged_in_client, organisation)

    response = _remove(client, organisation, me, "organisation_admin")

    assert response.status_code == 422
    assert "You can't change your own roles." in _text(response)
    assert _active_roles(me) == {("organisation_admin", str(organisation.pk))}


@pytest.mark.django_db
def test_removing_a_role_the_user_does_not_hold_answers_the_unavailable_fragment(
    admin_client, organisation
):
    user = _member_holding("cohort_viewer", _cohort(organisation))

    response = _remove(admin_client, organisation, user, "cohort_admin")

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


@pytest.mark.django_db
def test_removing_a_role_from_a_user_who_is_no_member_answers_the_unavailable_fragment(
    admin_client, organisation
):
    response = _remove(admin_client, organisation, UserFactory(), "cohort_viewer")

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


@pytest.mark.django_db
def test_a_refusal_partway_through_a_removal_is_403_and_keeps_every_cohort(
    admin_client, organisation, monkeypatch
):
    cohorts = [_cohort(organisation), _cohort(organisation)]
    user = _member_holding("cohort_viewer", cohorts)
    before = _active_roles(user)
    real_remove_role = deactivate_role
    calls: list[Cohort] = []

    def refuse_second(grantor, target_user, role, target, **kwargs):
        if calls:
            raise RoleChangeRefused(RefusalReason.NOT_PERMITTED)
        calls.append(target)
        real_remove_role(grantor, target_user, role, target, **kwargs)

    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.deactivate_role", refuse_second
    )

    response = _remove(admin_client, organisation, user, "cohort_viewer")

    assert response.status_code == 403
    assert _active_roles(user) == before


@pytest.mark.django_db
def test_the_remove_confirmation_escapes_the_persons_name(admin_client, organisation):
    user = _member_holding(
        "cohort_viewer", _cohort(organisation), first_name="<b>Bold</b>"
    )

    html = _remove_dialog(
        admin_client, organisation, user, "cohort_viewer"
    ).content.decode()

    assert "<b>Bold</b>" not in html
    assert "&lt;b&gt;Bold&lt;/b&gt;" in html


def _change_cohorts_url(organisation: Organisation) -> str:
    return _interface_url(organisation.slug, "members/__actions/change_cohorts")


def _change_dialog(
    client: Client, organisation: Organisation, user: User, role: str = "cohort_viewer"
):
    return client.get(
        _change_cohorts_url(organisation),
        {"user": str(user.pk), "role": role},
        HTTP_HX_REQUEST="true",
    )


def _change(
    client: Client,
    organisation: Organisation,
    user: User,
    cohorts: list[Cohort],
    role: str = "cohort_viewer",
    confirmed: bool = True,
):
    data: dict[str, str | list[str]] = {
        "user": str(user.pk),
        "role": role,
        "cohorts": [str(cohort.pk) for cohort in cohorts],
    }
    if confirmed:
        data["confirmed"] = "1"
    return client.post(_change_cohorts_url(organisation), data, HTTP_HX_REQUEST="true")


def _checkbox_state(response) -> dict[str, bool]:
    document = lxml.html.fromstring(response.content.decode())
    return {
        box.get("value"): box.get("checked") is not None
        for box in document.cssselect("input[name='cohorts']")
    }


@pytest.mark.django_db
def test_the_change_dialog_ticks_the_cohorts_the_person_holds(
    admin_client, organisation
):
    held = _cohort(organisation, name="Held group")
    free = _cohort(organisation, name="Free group")
    user = _member_holding("cohort_viewer", held)

    response = _change_dialog(admin_client, organisation, user)

    state = _checkbox_state(response)
    assert (state[str(held.pk)], state[str(free.pk)]) == (True, False)


@pytest.mark.django_db
def test_a_held_cohort_outside_the_grantors_reach_is_listed_read_only(
    admin_client, organisation, monkeypatch
):
    reachable = _cohort(organisation, name="Reachable")
    unreachable = _cohort(organisation, name="Beyond reach")
    user = _member_holding("cohort_viewer", [reachable, unreachable])
    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.grantable_roles",
        lambda *args: [GrantableRole("cohort_viewer", (reachable,))],
    )

    response = _change_dialog(admin_client, organisation, user)

    assert _checkbox_state(response) == {str(reachable.pk): True}
    assert "Beyond reach (outside the cohorts you can give)" in _text(response)


@pytest.mark.django_db
def test_an_inactive_held_cohort_is_listed_read_only(admin_client, organisation):
    active = _cohort(organisation)
    dormant = _cohort(organisation, name="Dormant group")
    user = _member_holding("cohort_viewer", [active, dormant])
    Cohort.objects.filter(pk=dormant.pk).update(is_active=False)

    response = _change_dialog(admin_client, organisation, user)

    assert str(dormant.pk) not in _checkbox_state(response)
    assert "Dormant group (inactive)" in _text(response)


@pytest.mark.django_db
def test_an_inactive_held_cohort_is_untouched_by_a_change(admin_client, organisation):
    active = _cohort(organisation)
    dormant = _cohort(organisation)
    user = _member_holding("cohort_viewer", [active, dormant])
    Cohort.objects.filter(pk=dormant.pk).update(is_active=False)

    _change(admin_client, organisation, user, [])

    assert _active_roles(user) == {("cohort_viewer", str(dormant.pk))}


@pytest.mark.django_db
def test_a_held_cohort_outside_the_grantors_reach_is_untouched_by_a_change(
    admin_client, organisation, monkeypatch
):
    reachable = _cohort(organisation)
    unreachable = _cohort(organisation)
    user = _member_holding("cohort_viewer", [reachable, unreachable])
    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.grantable_roles",
        lambda *args: [GrantableRole("cohort_viewer", (reachable,))],
    )

    _change(admin_client, organisation, user, [])

    assert _active_roles(user) == {("cohort_viewer", str(unreachable.pk))}


@pytest.mark.django_db
def test_the_confirmation_for_an_added_cohort_names_it_as_a_widening(
    admin_client, organisation
):
    held = _cohort(organisation)
    added = _cohort(organisation, name="Newly given")
    user = _member_holding("cohort_viewer", held)

    response = _change(admin_client, organisation, user, [held, added], confirmed=False)

    text = _text(response)
    assert "Adds: Newly given" in text
    assert "will be able to do more than they can now" in text
    assert "Deactivates on:" not in text


@pytest.mark.django_db
def test_adding_a_cohort_held_with_a_stronger_role_is_no_widening(
    admin_client, organisation
):
    held = _cohort(organisation)
    administered = _cohort(organisation, name="Already run")
    user = _member_holding("cohort_viewer", held)
    assign_role(UserFactory(superuser=True), user, "cohort_admin", administered)

    response = _change(
        admin_client, organisation, user, [held, administered], confirmed=False
    )

    text = _text(response)
    assert "Adds: Already run" in text
    assert "will be able to do more than they can now" not in text


@pytest.mark.django_db
def test_the_confirmation_for_a_removed_cohort_names_the_loss(
    admin_client, organisation
):
    kept = _cohort(organisation)
    dropped = _cohort(organisation, name="Let go")
    user = _member_holding("cohort_viewer", [kept, dropped])

    response = _change(admin_client, organisation, user, [kept], confirmed=False)

    text = _text(response)
    assert "Deactivates on: Let go" in text
    assert "will be able to do more" not in text
    assert "Adds:" not in text


@pytest.mark.django_db
def test_the_confirmation_for_an_added_and_a_removed_cohort_names_both(
    admin_client, organisation
):
    held = _cohort(organisation, name="Dropped one")
    added = _cohort(organisation, name="Added one")
    user = _member_holding("cohort_viewer", held)

    response = _change(admin_client, organisation, user, [added], confirmed=False)

    text = _text(response)
    assert "Adds: Added one" in text
    assert "Deactivates on: Dropped one" in text


@pytest.mark.django_db
def test_the_confirmation_for_every_cohort_removed_uses_the_remove_wording(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    user = _member_holding("cohort_viewer", cohort)

    response = _change(admin_client, organisation, user, [], confirmed=False)

    document = lxml.html.fromstring(response.content.decode())
    assert f"Deactivate Cohort viewer for {user.display_name}" in _text(response)
    (button,) = document.cssselect("button[type=submit]")
    assert button.text_content().split()[0] == "Deactivate"


@pytest.mark.django_db
def test_a_confirmed_addition_grants_the_cohort(admin_client, organisation):
    held = _cohort(organisation)
    added = _cohort(organisation)
    user = _member_holding("cohort_viewer", held)

    _change(admin_client, organisation, user, [held, added])

    assert _active_roles(user) == {
        ("cohort_viewer", str(held.pk)),
        ("cohort_viewer", str(added.pk)),
    }


@pytest.mark.django_db
def test_a_confirmed_removal_deactivates_the_cohort(admin_client, organisation):
    kept = _cohort(organisation)
    dropped = _cohort(organisation)
    user = _member_holding("cohort_viewer", [kept, dropped])

    _change(admin_client, organisation, user, [kept])

    assert _active_roles(user) == {("cohort_viewer", str(kept.pk))}


@pytest.mark.django_db
def test_a_confirmed_change_with_an_addition_and_a_removal_does_both(
    admin_client, organisation
):
    dropped = _cohort(organisation)
    added = _cohort(organisation)
    user = _member_holding("cohort_viewer", dropped)

    _change(admin_client, organisation, user, [added])

    assert _active_roles(user) == {("cohort_viewer", str(added.pk))}


@pytest.mark.django_db
def test_removing_every_cohort_leaves_no_active_assignment_for_the_role(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    user = _member_holding("cohort_viewer", cohort)
    assign_role(UserFactory(superuser=True), user, "cohort_admin", cohort)

    _change(admin_client, organisation, user, [])

    assert _active_roles(user) == {("cohort_admin", str(cohort.pk))}


@pytest.mark.django_db
def test_a_confirmed_change_answers_204_with_member_changed(admin_client, organisation):
    user = _member_holding("cohort_viewer", _cohort(organisation))

    response = _change(admin_client, organisation, user, [_cohort(organisation)])

    assert response.status_code == 204
    assert json.loads(response["HX-Trigger"])[MEMBER_CHANGED] == {"ids": [str(user.pk)]}


@pytest.mark.django_db
def test_an_unconfirmed_change_leaves_every_assignment_unchanged(
    admin_client, organisation
):
    held = _cohort(organisation)
    user = _member_holding("cohort_viewer", held)
    before = _active_roles(user)

    _change(admin_client, organisation, user, [_cohort(organisation)], confirmed=False)

    assert _active_roles(user) == before


@pytest.mark.django_db
def test_an_unchanged_selection_is_422(admin_client, organisation):
    held = _cohort(organisation)
    user = _member_holding("cohort_viewer", held)

    response = _change(admin_client, organisation, user, [held], confirmed=False)

    assert response.status_code == 422
    assert "Nothing changed. Tick or untick a cohort first." in _text(response)


@pytest.mark.django_db
def test_a_cohort_outside_the_offered_set_answers_the_unavailable_fragment(
    admin_client, organisation, monkeypatch
):
    reachable = _cohort(organisation)
    outside = _cohort(organisation)
    user = _member_holding("cohort_viewer", reachable)
    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.grantable_roles",
        lambda *args: [GrantableRole("cohort_viewer", (reachable,))],
    )

    response = _change(admin_client, organisation, user, [reachable, outside])

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()
    assert _active_roles(user) == {("cohort_viewer", str(reachable.pk))}


@pytest.mark.django_db
def test_a_change_naming_the_viewer_is_422_with_the_self_message(
    mock_site_context, logged_in_client, organisation
):
    client, me = _holder_client(logged_in_client, organisation)
    cohort = _cohort(organisation)
    assign_role(UserFactory(superuser=True), me, "cohort_viewer", cohort)
    before = _active_roles(me)

    response = _change(client, organisation, me, [_cohort(organisation)])

    assert response.status_code == 422
    assert "You can't change your own roles." in _text(response)
    assert _active_roles(me) == before


@pytest.mark.django_db
def test_the_confirmation_for_a_person_with_no_member_row_says_the_grant_creates_one(
    admin_client, organisation
):
    held = _cohort(organisation)
    added = _cohort(organisation)
    user = _member_holding("cohort_viewer", held)
    OrganisationMember.objects.filter(user=user).delete()

    response = _change(admin_client, organisation, user, [held, added], confirmed=False)

    assert "Adding this role creates one" in _text(response)


@pytest.mark.django_db
def test_the_confirmation_for_a_suspended_member_says_the_cohorts_wait_for_reactivation(
    admin_client, organisation
):
    held = _cohort(organisation)
    added = _cohort(organisation)
    user = _member_holding("cohort_viewer", held)
    OrganisationMember.objects.filter(user=user).update(is_active=False)

    text = _text(
        _change(admin_client, organisation, user, [held, added], confirmed=False)
    )

    assert "is inactive here, so the added cohorts take effect only once" in text
    assert "has no active membership here" not in text


@pytest.mark.django_db
def test_a_change_for_an_organisation_admin_role_answers_the_unavailable_fragment(
    admin_client, organisation
):
    user = _member_holding("organisation_admin", organisation)

    response = _change(
        admin_client, organisation, user, [_cohort(organisation)], "organisation_admin"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_refusal_partway_through_a_change_keeps_every_assignment(
    admin_client, organisation, monkeypatch
):
    dropped = _cohort(organisation)
    added = _cohort(organisation)
    user = _member_holding("cohort_viewer", dropped)
    before = _active_roles(user)

    def refuse(*args: object, **kwargs: object) -> None:
        raise RoleChangeRefused(RefusalReason.NOT_PERMITTED)

    monkeypatch.setattr("freedom_ls.educator_interface.actions.deactivate_role", refuse)

    response = _change(admin_client, organisation, user, [added])

    assert response.status_code == 403
    assert _active_roles(user) == before


def _state_url(organisation: Organisation, action: str) -> str:
    return _interface_url(organisation.slug, f"members/__actions/{action}")


def _state_dialog(client: Client, organisation: Organisation, user: User, action: str):
    return client.get(
        _state_url(organisation, action),
        {"user": str(user.pk)},
        HTTP_HX_REQUEST="true",
    )


def _state_post(client: Client, organisation: Organisation, user: User, action: str):
    return _post(client, _state_url(organisation, action), {"user": str(user.pk)})


def _member_row(user: User, organisation: Organisation) -> OrganisationMember:
    return cast(
        OrganisationMember,
        OrganisationMember.objects.get(user=user, organisation=organisation),
    )


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["deactivate", "reactivate"])
def test_the_state_dialogs_leave_the_member_row_unchanged(
    admin_client, organisation, action
):
    user = _member_holding("cohort_viewer", _cohort(organisation))
    before = _member_row(user, organisation).is_active

    _state_dialog(admin_client, organisation, user, action)

    assert _member_row(user, organisation).is_active == before


@pytest.mark.django_db
def test_the_suspend_dialog_says_they_keep_their_roles(admin_client, organisation):
    user = _member_holding(
        "cohort_viewer", _cohort(organisation), first_name="Ada", last_name="Lovelace"
    )

    text = _text(_state_dialog(admin_client, organisation, user, "deactivate"))

    assert "Deactivate Ada Lovelace" in text
    assert (
        f"They keep their roles but can do nothing in {organisation.name} "
        "until reactivated."
    ) in text


@pytest.mark.django_db
def test_suspending_stops_a_cohort_capability_and_answers_204(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    user = _member_holding("cohort_viewer", cohort)
    capability = "freedom_ls_learner_management.view_cohort"
    assert can(user, capability, cohort)

    response = _state_post(admin_client, organisation, user, "deactivate")

    assert response.status_code == 204
    assert json.loads(response["HX-Trigger"])[MEMBER_CHANGED] == {"ids": [str(user.pk)]}
    assert not _member_row(user, organisation).is_active
    assert not can(user, capability, cohort)


@pytest.mark.django_db
def test_reactivating_restores_the_capability_and_answers_204(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    user = _member_holding("cohort_viewer", cohort)
    OrganisationMember.objects.filter(user=user).update(is_active=False)

    response = _state_post(admin_client, organisation, user, "reactivate")

    assert response.status_code == 204
    assert json.loads(response["HX-Trigger"])[MEMBER_CHANGED] == {"ids": [str(user.pk)]}
    assert can(user, "freedom_ls_learner_management.view_cohort", cohort)


@pytest.mark.django_db
def test_the_reactivate_dialog_lists_the_roles_that_take_effect_again(
    admin_client, organisation
):
    user = _member_holding(
        "cohort_viewer",
        _cohort(organisation, name="Evening group"),
        first_name="Ada",
        last_name="Lovelace",
    )
    OrganisationMember.objects.filter(user=user).update(is_active=False)

    text = _text(_state_dialog(admin_client, organisation, user, "reactivate"))

    assert "Reactivate Ada Lovelace" in text
    assert "These roles take effect again: Cohort viewer on Evening group." in text


@pytest.mark.django_db
def test_reactivating_a_member_with_no_row_creates_an_active_one(
    admin_client, organisation
):
    user = _member_holding("cohort_viewer", _cohort(organisation))
    OrganisationMember.objects.filter(user=user).delete()

    response = _state_post(admin_client, organisation, user, "reactivate")

    assert response.status_code == 204
    assert _member_row(user, organisation).is_active


@pytest.mark.django_db
def test_reactivating_a_member_with_no_row_writes_member_reactivated(
    admin_client, organisation
):
    user = _member_holding("cohort_viewer", _cohort(organisation))
    OrganisationMember.objects.filter(user=user).delete()

    _state_post(admin_client, organisation, user, "reactivate")

    entry = AuditLogEntry.unscoped.get(action="member.reactivated")
    assert entry.target == _member_row(user, organisation)
    assert entry.subjects[1:] == [subject_key(user)]


@pytest.mark.django_db
def test_an_organisation_admin_suspending_the_last_organisation_admin_is_422(
    admin_client, organisation, monkeypatch
):
    sole = _member_holding("organisation_admin", organisation, first_name="Ada")
    monkeypatch.setattr(
        "freedom_ls.learner_management.role_assignment.is_last_organisation_admin",
        lambda *args: True,
    )

    response = _state_post(admin_client, organisation, sole, "deactivate")

    assert response.status_code == 422
    assert "Ada is this organisation's only organisation admin." in _text(response)
    assert _member_row(sole, organisation).is_active


@pytest.mark.django_db
def test_a_site_admin_is_warned_in_the_suspend_dialog_and_succeeds(
    mock_site_context, logged_in_client, organisation
):
    sole = _member_holding(
        "organisation_admin", organisation, first_name="Ada", last_name="Lovelace"
    )
    site_admin = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True), site_admin, "site_admin", organisation.site
    )
    client = logged_in_client(site_admin)

    dialog = _text(_state_dialog(client, organisation, sole, "deactivate"))
    response = _state_post(client, organisation, sole, "deactivate")

    assert "Ada Lovelace is the only organisation admin." in dialog
    assert response.status_code == 204
    assert not _member_row(sole, organisation).is_active


@pytest.mark.django_db
def test_the_suspend_dialog_has_no_warning_while_another_organisation_admin_remains(
    admin_client, organisation
):
    other = _member_holding("organisation_admin", organisation)

    text = _text(_state_dialog(admin_client, organisation, other, "deactivate"))

    assert "only organisation admin" not in text


@pytest.mark.django_db
def test_a_stale_suspend_of_an_inactive_row_answers_the_unavailable_fragment(
    admin_client, organisation
):
    user = _member_holding("cohort_viewer", _cohort(organisation))
    OrganisationMember.objects.filter(user=user).update(is_active=False)

    response = _state_post(admin_client, organisation, user, "deactivate")

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


@pytest.mark.django_db
def test_a_stale_suspend_of_a_member_with_no_row_answers_the_unavailable_fragment(
    admin_client, organisation
):
    user = _member_holding("cohort_viewer", _cohort(organisation))
    OrganisationMember.objects.filter(user=user).delete()

    response = _state_post(admin_client, organisation, user, "deactivate")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_stale_reactivate_of_an_active_row_answers_the_unavailable_fragment(
    admin_client, organisation
):
    user = _member_holding("cohort_viewer", _cohort(organisation))

    response = _state_post(admin_client, organisation, user, "reactivate")

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


@pytest.mark.django_db
def test_suspending_yourself_is_422_with_the_self_message(
    mock_site_context, logged_in_client, organisation
):
    client, me = _holder_client(logged_in_client, organisation)

    response = _state_post(client, organisation, me, "deactivate")

    assert response.status_code == 422
    assert "You can't change your own roles." in _text(response)
    assert _member_row(me, organisation).is_active


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["deactivate", "reactivate"])
def test_a_state_change_for_a_non_member_answers_the_unavailable_fragment(
    admin_client, organisation, action
):
    response = _state_post(admin_client, organisation, UserFactory(), action)

    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


@pytest.mark.django_db
def test_the_state_dialogs_escape_the_persons_name(admin_client, organisation):
    user = _member_holding(
        "cohort_viewer", _cohort(organisation), first_name="<b>Bold</b>"
    )

    html = _state_dialog(
        admin_client, organisation, user, "deactivate"
    ).content.decode()

    assert "<b>Bold</b>" not in html
    assert "&lt;b&gt;Bold&lt;/b&gt;" in html


def _cohort_add_member_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(
        organisation,
        cohort,
        "/__tabs/overview/__panels/educators/__actions/add_member",
    )


def _cohort_overview_lookup(client: Client, organisation: Organisation, cohort: Cohort):
    return _post(
        client,
        _cohort_add_member_url(organisation, cohort),
        {"step": "lookup", "email": "ada@example.com"},
    )


def _cohort_overview_confirm(
    client: Client, organisation: Organisation, cohort: Cohort, cohorts: list[Cohort]
):
    return client.post(
        _cohort_add_member_url(organisation, cohort),
        {
            "step": "submit",
            "email": "ada@example.com",
            "role": "cohort_viewer",
            "cohorts": [str(other.pk) for other in cohorts],
            "confirmed": "1",
        },
        HTTP_HX_REQUEST="true",
    )


def _cohort_viewer_cohorts(user: User) -> set[str]:
    return set(
        ObjectRoleAssignment.objects.filter(
            user=user, role="cohort_viewer"
        ).values_list("object_id", flat=True)
    )


@pytest.mark.django_db
def test_the_cohort_dialog_offers_only_cohort_roles(admin_client, organisation):
    cohort = _cohort(organisation)
    UserFactory(email="ada@example.com")

    response = _cohort_overview_lookup(admin_client, organisation, cohort)

    document = lxml.html.fromstring(response.content.decode())
    roles = [radio.get("value") for radio in document.cssselect("input[name='role']")]
    assert roles == ["cohort_admin", "cohort_viewer"]


@pytest.mark.django_db
def test_the_cohort_dialog_has_no_cohort_checklist(admin_client, organisation):
    cohort = _cohort(organisation)
    UserFactory(email="ada@example.com")

    response = _cohort_overview_lookup(admin_client, organisation, cohort)

    document = lxml.html.fromstring(response.content.decode())
    assert not document.cssselect("input[type='checkbox'][name='cohorts']")


@pytest.mark.django_db
def test_the_cohort_dialog_carries_the_cohort_as_a_hidden_input(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    UserFactory(email="ada@example.com")

    response = _cohort_overview_lookup(admin_client, organisation, cohort)

    document = lxml.html.fromstring(response.content.decode())
    hidden = document.cssselect("input[type='hidden'][name='cohorts']")
    assert [field.get("value") for field in hidden] == [str(cohort.pk)]


@pytest.mark.django_db
def test_confirming_on_a_cohort_page_grants_the_role_on_that_cohort_alone(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    other = _cohort(organisation)
    user = UserFactory(email="ada@example.com")

    _cohort_overview_confirm(admin_client, organisation, cohort, [cohort])

    assert _cohort_viewer_cohorts(user) == {str(cohort.pk)}
    assert str(other.pk) not in _cohort_viewer_cohorts(user)


@pytest.mark.django_db
def test_the_cohort_confirmation_names_the_cohort_as_the_scope(
    admin_client, organisation
):
    cohort = _cohort(organisation, name="Spring")
    UserFactory(email="ada@example.com")

    response = admin_client.post(
        _cohort_add_member_url(organisation, cohort),
        {
            "step": "submit",
            "email": "ada@example.com",
            "role": "cohort_viewer",
            "cohorts": [str(cohort.pk)],
        },
        HTTP_HX_REQUEST="true",
    )

    assert "Scope: Spring." in _text(response)


@pytest.mark.django_db
def test_a_post_naming_another_cohort_grants_nothing_on_it(admin_client, organisation):
    cohort = _cohort(organisation)
    other = _cohort(organisation)
    user = UserFactory(email="ada@example.com")

    _cohort_overview_confirm(admin_client, organisation, cohort, [other])

    assert _cohort_viewer_cohorts(user) == {str(cohort.pk)}


@pytest.mark.django_db
def test_the_educators_panel_offers_add_member_to_an_organisation_admin(
    admin_client, organisation
):
    cohort = _cohort(organisation)

    html = admin_client.get(_cohort_url(organisation, cohort)).content.decode()

    assert "/__panels/educators/__actions/add_member" in html


@pytest.mark.django_db
def test_the_educators_panel_hides_add_member_from_a_cohort_admin(
    mock_site_context, logged_in_client, organisation
):
    cohort = _cohort(organisation)
    client, _ = _holder_client(logged_in_client, cohort, "cohort_admin")

    html = client.get(_cohort_url(organisation, cohort)).content.decode()

    assert "/__panels/educators/__actions/add_member" not in html


@pytest.mark.django_db
def test_the_members_dialog_is_titled_add_a_member(admin_client, organisation):
    response = admin_client.get(_add_member_url(organisation), HTTP_HX_REQUEST="true")

    document = lxml.html.fromstring(response.content.decode())
    (title,) = document.cssselect("#app-modal-title")
    assert title.text_content().strip() == "Add a member"


@pytest.mark.django_db
def test_the_cohort_dialog_email_step_is_titled_with_the_cohort(
    admin_client, organisation
):
    cohort = _cohort(organisation, name="Spring")

    response = admin_client.get(
        _cohort_add_member_url(organisation, cohort), HTTP_HX_REQUEST="true"
    )

    document = lxml.html.fromstring(response.content.decode())
    (title,) = document.cssselect("#app-modal-title")
    assert title.text_content().strip() == "Add a member to Spring"


@pytest.mark.django_db
def test_the_cohort_dialog_role_step_is_titled_with_the_cohort(
    admin_client, organisation
):
    cohort = _cohort(organisation, name="Spring")
    UserFactory(email="ada@example.com")

    response = _cohort_overview_lookup(admin_client, organisation, cohort)

    document = lxml.html.fromstring(response.content.decode())
    (title,) = document.cssselect("#app-modal-title")
    assert title.text_content().strip() == "Add a member to Spring"


@pytest.mark.django_db
def test_the_cohort_dialog_does_not_tell_an_organisation_admin_about_rank(
    admin_client, organisation
):
    cohort = _cohort(organisation)
    UserFactory(email="ada@example.com")

    text = _text(_cohort_overview_lookup(admin_client, organisation, cohort))

    assert "You can only give roles at or below your own." not in text


@pytest.mark.django_db
def test_deactivating_a_learner_writes_an_entry_by_the_logged_in_user(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": f"learners/{learner.pk}/__actions/deactivate",
            },
        ),
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("learner.deactivated", actor)


# membership audit entries


@pytest.mark.django_db
def test_adding_a_learner_to_a_cohort_writes_an_entry_by_the_logged_in_user(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _add_to_cohort_url(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("cohort_membership.added", actor)


@pytest.mark.django_db
def test_removing_a_learner_from_a_cohort_writes_an_entry_by_the_logged_in_user(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _remove_url_from_learner(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("cohort_membership.removed", actor)


@pytest.mark.django_db
def test_moving_a_learner_writes_an_entry_by_the_logged_in_user(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = cast(Cohort, CohortFactory(organisation=organisation))
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(destination.pk)},
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("cohort_membership.moved", actor)


@pytest.mark.django_db
def test_adding_existing_learners_writes_one_entry_per_learner(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    first = cast(Learner, LearnerFactory(organisation=organisation))
    second = cast(Learner, LearnerFactory(organisation=organisation))
    actor = UserFactory(superuser=True)

    logged_in_client(actor).post(
        _add_learners_url(organisation, cohort),
        {"learners": [str(first.pk), str(second.pk)]},
        HTTP_HX_REQUEST="true",
    )

    entries = AuditLogEntry.unscoped.all()
    assert {(e.action, e.actor, e.target_object_id) for e in entries} == {
        ("cohort_membership.added", actor, str(first.pk)),
        ("cohort_membership.added", actor, str(second.pk)),
    }


@pytest.mark.django_db
def test_adding_learners_by_email_writes_an_entry_by_the_logged_in_user(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _add_learners_list_url(organisation),
        {"entries": "new@example.com"},
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("learner.added", actor)


# registration audit entries


@pytest.mark.django_db
def test_registering_a_learner_writes_an_entry_by_the_logged_in_user(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _learner_register_url(organisation, learner),
        {"course": str(CourseFactory().pk)},
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("registration.added", actor)


@pytest.mark.django_db
def test_reregistering_a_learner_writes_an_entry_by_the_logged_in_user(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=False)
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _learner_reregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("registration.reactivated", actor)


@pytest.mark.django_db
def test_unregistering_a_learner_writes_an_entry_by_the_logged_in_user(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner)
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _learner_unregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("registration.deactivated", actor)


@pytest.mark.django_db
def test_registering_a_cohort_writes_an_entry_by_the_logged_in_user(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0)
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _register_url(organisation, cohort),
        {"course": str(CourseFactory().pk)},
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("cohort_registration.added", actor)


@pytest.mark.django_db
def test_unregistering_a_cohort_writes_an_entry_by_the_logged_in_user(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _unregister_post_url(organisation, cohort),
        {"registration": str(registration.pk)},
    )

    entry = AuditLogEntry.unscoped.get()
    assert (entry.action, entry.actor) == ("cohort_registration.deactivated", actor)


@pytest.mark.django_db
def test_renaming_a_cohort_writes_an_entry_with_the_old_and_new_name(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, name="Old name"))
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _cohort_url(organisation, cohort, "/__actions/edit"),
        {"name": "New name"},
    )

    assert_entry(
        action="cohort.renamed",
        actor=actor,
        target=cohort,
        target_label="New name",
        organisation=organisation,
        details={"old": "Old name", "new": "New name"},
    )


@pytest.mark.django_db
def test_saving_a_cohort_under_its_own_name_writes_nothing(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, name="Same"))

    response = _post(
        staff_client,
        _cohort_url(organisation, cohort, "/__actions/edit"),
        {"name": "Same"},
    )

    assert response.status_code == 204
    assert not AuditLogEntry.unscoped.exists()


@pytest.mark.django_db
def test_renaming_a_learner_writes_an_entry_with_the_old_and_new_name(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _edit_name_url(organisation, learner),
        {"first_name": "Grace", "last_name": "Hopper"},
    )

    assert_entry(
        action="learner.renamed",
        actor=actor,
        target=learner,
        target_label="Grace Hopper",
        organisation=organisation,
        details={"old": "Ada Lovelace", "new": "Grace Hopper"},
    )


@pytest.mark.django_db
def test_saving_a_learner_under_their_own_name_writes_nothing(staff_client: Client):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)

    response = _post(
        staff_client,
        _edit_name_url(organisation, learner),
        {"first_name": "Ada", "last_name": "Lovelace"},
    )

    assert response.status_code == 204
    assert not AuditLogEntry.unscoped.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("action_name", "code", "start_active"),
    [
        ("deactivate", "cohort.deactivated", True),
        ("reactivate", "cohort.reactivated", False),
    ],
)
def test_changing_a_cohorts_state_writes_an_entry(
    mock_site_context, logged_in_client, action_name: str, code: str, start_active: bool
):
    organisation = OrganisationFactory()
    cohort = cast(
        Cohort,
        CohortFactory(
            organisation=organisation, name="Evening", is_active=start_active
        ),
    )
    actor = UserFactory(superuser=True)

    _post(
        logged_in_client(actor),
        _cohort_url(organisation, cohort, f"/__actions/{action_name}"),
    )

    assert_entry(
        action=code,
        actor=actor,
        target=cohort,
        target_label="Evening",
        organisation=organisation,
    )


@pytest.mark.django_db
def test_a_stale_state_change_on_an_inactive_cohort_writes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))

    response = _post(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    assert response.status_code == 422
    assert not AuditLogEntry.unscoped.exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_resending_a_setup_email_writes_an_entry(
    mock_site_context, logged_in_client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)
    actor = UserFactory(superuser=True)

    with django_capture_on_commit_callbacks(execute=True):
        _post(logged_in_client(actor), _resend_url(organisation, learner))

    assert_entry(
        action="learner.setup_email_resent",
        actor=actor,
        target=learner,
        target_label=learner.user.display_name,
        organisation=organisation,
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_a_refused_resend_writes_nothing(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    set_up = LearnerFactory(organisation=organisation)
    recent = _pending_learner(organisation)
    with django_capture_on_commit_callbacks(execute=True):
        _post(staff_client, _resend_url(organisation, recent))
    entries_before = AuditLogEntry.unscoped.count()

    with django_capture_on_commit_callbacks(execute=True):
        too_soon = _post(staff_client, _resend_url(organisation, recent))
        already = _post(staff_client, _resend_url(organisation, set_up))

    assert (too_soon.status_code, already.status_code) == (422, 422)
    assert AuditLogEntry.unscoped.count() == entries_before


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_a_failed_entry_sends_no_email_and_leaves_the_resend_open(
    staff_client: Client, django_capture_on_commit_callbacks, monkeypatch
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)
    url = _resend_url(organisation, learner)

    def fail(*args: object, **kwargs: object) -> None:
        raise _RolledBackError

    monkeypatch.setattr(
        "freedom_ls.educator_interface.actions.record_learner_entry", fail
    )
    with (
        pytest.raises(_RolledBackError),
        django_capture_on_commit_callbacks(execute=True),
    ):
        _post(staff_client, url)
    monkeypatch.undo()
    assert mail.outbox == []

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(staff_client, url)

    assert response.status_code == 204
    assert len(mail.outbox) == 1


class _RolledBackError(Exception):
    pass


def _rename_cohort_request(organisation: Organisation) -> tuple[str, dict[str, str]]:
    cohort = cast(Cohort, CohortFactory(organisation=organisation, name="Before"))
    return _cohort_url(organisation, cohort, "/__actions/edit"), {"name": "After"}


def _rename_learner_request(organisation: Organisation) -> tuple[str, dict[str, str]]:
    return _edit_name_url(organisation, _named_learner(organisation)), {
        "first_name": "Grace",
        "last_name": "Hopper",
    }


def _deactivate_cohort_request(
    organisation: Organisation,
) -> tuple[str, dict[str, str]]:
    cohort = CohortFactory(organisation=organisation)
    return _cohort_url(organisation, cohort, "/__actions/deactivate"), {}


def _resend_request(organisation: Organisation) -> tuple[str, dict[str, str]]:
    return _resend_url(organisation, _pending_learner(organisation)), {}


def _create_cohort_request(organisation: Organisation) -> tuple[str, dict[str, str]]:
    return _interface_url(organisation.slug, "cohorts/__actions/create_cohort"), {
        "name": "Fresh"
    }


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
@pytest.mark.parametrize(
    "build_request",
    [
        _create_cohort_request,
        _rename_cohort_request,
        _rename_learner_request,
        _deactivate_cohort_request,
        _resend_request,
    ],
)
def test_a_failure_after_the_write_leaves_no_entry(
    staff_client: Client,
    build_request: Callable[[Organisation], tuple[str, dict[str, str]]],
) -> None:
    organisation = OrganisationFactory()
    url, data = build_request(organisation)

    def post_then_fail() -> None:
        with transaction.atomic():
            response = _post(staff_client, url, data)
            assert response.status_code in (204, 200)
            assert AuditLogEntry.unscoped.exists()
            raise _RolledBackError

    with pytest.raises(_RolledBackError):
        post_then_fail()

    assert not AuditLogEntry.unscoped.exists()


# the optional reason in the confirm dialogs


_DialogRequest = tuple[str, dict[str, str]]


def _reason_deactivate_cohort(organisation: Organisation) -> _DialogRequest:
    cohort = CohortFactory(organisation=organisation)
    return _cohort_url(organisation, cohort, "/__actions/deactivate"), {}


def _reason_deactivate_learner(organisation: Organisation) -> _DialogRequest:
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    return _learner_state_url(organisation, learner, "deactivate"), {}


def _reason_remove_from_cohort(organisation: Organisation) -> _DialogRequest:
    learner, cohort = _membership(organisation)
    return _remove_url_from_learner(organisation, learner), {"cohort": str(cohort.pk)}


def _reason_unregister_cohort(organisation: Organisation) -> _DialogRequest:
    cohort, registration = _registered_cohort(organisation)
    return _unregister_post_url(organisation, cohort), {
        "registration": str(registration.pk)
    }


def _reason_unregister_learner(organisation: Organisation) -> _DialogRequest:
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=True)
    return _learner_unregister_url(organisation, learner), {
        "registration": str(registration.pk)
    }


def _reason_remove_role(organisation: Organisation) -> _DialogRequest:
    user = _member_holding("cohort_admin", _cohort(organisation))
    return _remove_role_url(organisation), {
        "user": str(user.pk),
        "role": "cohort_admin",
    }


def _reason_suspend_member(organisation: Organisation) -> _DialogRequest:
    user = _member_holding("cohort_viewer", _cohort(organisation))
    return _state_url(organisation, "deactivate"), {"user": str(user.pk)}


REASON_DIALOGS = [
    _reason_deactivate_cohort,
    _reason_deactivate_learner,
    _reason_remove_from_cohort,
    _reason_unregister_cohort,
    _reason_unregister_learner,
    _reason_remove_role,
    _reason_suspend_member,
]


def _reason_post(
    client: Client, request: _DialogRequest, reason: str | None
) -> tuple[HttpResponse, list[AuditLogEntry]]:
    """POST the dialog `request` and return the response with the entries it
    wrote, leaving out those that setting the scene wrote."""
    before = set(AuditLogEntry.unscoped.values_list("pk", flat=True))
    url, params = request
    data = params if reason is None else {**params, "reason": reason}
    response = _post(client, url, data)
    written = list(AuditLogEntry.unscoped.exclude(pk__in=before))
    return response, written


@pytest.mark.django_db
@pytest.mark.parametrize("build_url", REASON_DIALOGS)
def test_a_confirm_dialog_renders_the_optional_reason_field(
    staff_client: Client, build_url: Callable[[Organisation], _DialogRequest]
) -> None:
    organisation = OrganisationFactory()
    url, params = build_url(organisation)

    response = staff_client.get(url, params, HTTP_HX_REQUEST="true")

    document = lxml.html.fromstring(response.content.decode())
    (field,) = document.cssselect("input[name='reason']")
    assert field.get("maxlength") == "500"
    label = document.cssselect(f"label[for='{field.get('id')}']")[0]
    assert label.text_content().strip() == "Reason (optional):"
    assert document.cssselect("form input[name='reason']")


@pytest.mark.django_db
@pytest.mark.parametrize("build_url", REASON_DIALOGS)
def test_a_reason_posted_with_a_confirm_dialog_reaches_the_entry(
    staff_client: Client, build_url: Callable[[Organisation], _DialogRequest]
) -> None:
    organisation = OrganisationFactory()

    response, written = _reason_post(
        staff_client, build_url(organisation), "  Left the programme  "
    )

    assert response.status_code in (200, 204)
    assert [entry.reason for entry in written] == ["Left the programme"]


@pytest.mark.django_db
@pytest.mark.parametrize("build_url", REASON_DIALOGS)
def test_a_confirm_dialog_allows_an_empty_reason(
    staff_client: Client, build_url: Callable[[Organisation], _DialogRequest]
) -> None:
    organisation = OrganisationFactory()

    response, written = _reason_post(staff_client, build_url(organisation), None)

    assert response.status_code in (200, 204)
    assert [entry.reason for entry in written] == [""]


@pytest.mark.django_db
@pytest.mark.parametrize("build_url", REASON_DIALOGS)
def test_a_reason_over_500_characters_answers_422_and_changes_nothing(
    staff_client: Client, build_url: Callable[[Organisation], _DialogRequest]
) -> None:
    organisation = OrganisationFactory()

    response, written = _reason_post(staff_client, build_url(organisation), "x" * 501)

    assert response.status_code == 422
    document = lxml.html.fromstring(response.content.decode())
    assert document.cssselect("input[name='reason']")
    assert "at most 500 characters" in document.text_content()
    assert written == []


# bulk learner state actions


def _bulk_learner(**fields: object) -> Learner:
    return cast(Learner, LearnerFactory(**fields))


def _scoped_request(user: User, organisation: Organisation) -> HttpRequest:
    """A request as `scope_request` leaves it: the user and the organisation
    the table's rows belong to."""
    request = cast(OrganisationScopedRequest, RequestFactory().post("/"))
    request.user = user
    request.organisation = organisation
    return request


def _learners_bulk_url(organisation: Organisation, action_name: str) -> str:
    return _interface_url(organisation.slug, f"learners/__actions/{action_name}")


def _bulk_post(
    client: Client,
    organisation: Organisation,
    action_name: str,
    learners: list[Learner],
    **extra: str,
):
    return client.post(
        _learners_bulk_url(organisation, action_name),
        {"keys": [str(learner.pk) for learner in learners], **extra},
        HTTP_HX_REQUEST="true",
    )


def _bulk_confirm(
    client: Client,
    organisation: Organisation,
    action_name: str,
    learners: list[Learner],
):
    return _bulk_post(
        client,
        organisation,
        action_name,
        learners,
        confirmed="on",
        expected_count=str(len(learners)),
    )


def _bulk_text(response) -> str:
    return " ".join(
        lxml.html.fromstring(response.content.decode()).text_content().split()
    )


@pytest.mark.django_db
def test_bulk_deactivate_confirm_button_uses_a_defined_destructive_button_variant(
    staff_client: Client,
):
    """The confirm button rendered the undefined `btn-destructive` class, so it looked like plain text."""
    organisation = OrganisationFactory()
    learners = [_bulk_learner(organisation=organisation)]

    response = _bulk_post(staff_client, organisation, "deactivate", learners)

    buttons = lxml.html.fromstring(response.content.decode()).cssselect(
        "button[type=submit]"
    )
    assert any("btn-error" in (button.get("class") or "") for button in buttons)


@pytest.mark.django_db
def test_bulk_deactivate_confirmation_says_what_changes_and_what_is_skipped(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    active = [_bulk_learner(organisation=organisation) for _ in range(2)]
    inactive = _bulk_learner(organisation=organisation, is_active=False)

    response = _bulk_post(staff_client, organisation, "deactivate", [*active, inactive])

    text = _bulk_text(response)
    assert "Deactivate 2 learners." in text
    assert "They lose access to this organisation's courses." in text
    assert "1 is already inactive and will be skipped." in text


@pytest.mark.django_db
def test_bulk_deactivate_changes_the_learners_and_summarises_the_run(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    active = [_bulk_learner(organisation=organisation) for _ in range(2)]
    inactive = _bulk_learner(organisation=organisation, is_active=False)

    response = _bulk_confirm(
        staff_client, organisation, "deactivate", [*active, inactive]
    )

    assert response.status_code == 200
    assert {
        learner.is_active
        for learner in Learner.objects.filter(pk__in=[learner.pk for learner in active])
    } == {False}
    assert "1 was already inactive." in _bulk_text(response)
    trigger = json.loads(response["HX-Trigger"])
    assert set(trigger[LEARNER_CHANGED]["ids"]) == {
        str(learner.pk) for learner in active
    } | {str(inactive.pk)}


@pytest.mark.django_db
def test_bulk_deactivate_records_the_run_with_its_result(staff_client: Client):
    organisation = OrganisationFactory()
    learners = [_bulk_learner(organisation=organisation) for _ in range(2)]

    _bulk_confirm(staff_client, organisation, "deactivate", learners)

    run = BulkActionRun.objects.get()
    assert (run.table_key, run.action_name, run.status) == (
        "learners",
        "deactivate",
        RunStatus.DONE,
    )
    assert sorted(run.keys) == sorted(str(learner.pk) for learner in learners)
    assert run.result is not None
    assert BulkResult.from_json(run.result).changed == 2
    assert run.finished_at is not None


@pytest.mark.django_db
def test_bulk_reactivate_changes_inactive_learners_and_skips_active_ones(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    inactive = _bulk_learner(organisation=organisation, is_active=False)
    active = _bulk_learner(organisation=organisation)

    response = _bulk_confirm(
        staff_client, organisation, "reactivate", [inactive, active]
    )

    inactive.refresh_from_db()
    assert inactive.is_active is True
    assert "1 was already active." in _bulk_text(response)


@pytest.mark.django_db
def test_bulk_reactivate_confirmation_pluralises_for_one_learner(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    inactive = _bulk_learner(organisation=organisation, is_active=False)

    response = _bulk_post(staff_client, organisation, "reactivate", [inactive])

    text = _bulk_text(response)
    assert "Reactivate 1 learner." in text
    assert (
        "Their access returns through their existing cohorts and registrations." in text
    )


@pytest.fixture
def cohort_learner_manager_role(mock_site_context: Site, settings):
    """A role that may change the learners of a cohort it is granted on, which
    no shipped role can."""
    role = Role(
        display_name="Cohort learner manager",
        permissions=frozenset({VIEW_COHORT, VIEW_LEARNER, CHANGE_LEARNER}),
        assignment_scope=SCOPE_OBJECT,
    )
    with custom_role_config(
        mock_site_context, settings, extra_roles={"cohort_learner_manager": role}
    ):
        yield "cohort_learner_manager"


@pytest.mark.django_db
def test_classify_all_counts_changed_skipped_and_not_permitted(
    cohort_learner_manager_role: str,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    member = _bulk_learner(organisation=organisation)
    outsider = _bulk_learner(organisation=organisation)
    inactive_member = _bulk_learner(organisation=organisation, is_active=False)
    for learner in (member, inactive_member):
        CohortMembershipFactory(cohort=cohort, learner=learner)
    educator = UserFactory(staff=True)
    assign_object_role(educator, cohort, cohort_learner_manager_role)
    action = DeactivateLearnersBulkAction()

    outcomes = action.classify_all(
        _scoped_request(educator, organisation),
        Learner.objects.filter(pk__in=[member.pk, outsider.pk, inactive_member.pk]),
        {},
    )

    assert outcomes == {
        str(member.pk): BulkOutcome("changed"),
        str(outsider.pk): BulkOutcome(
            "skipped", "learners you don't have permission to change"
        ),
        str(inactive_member.pk): BulkOutcome("skipped", "already inactive"),
    }


@pytest.mark.django_db
def test_a_cohort_admin_may_select_learners_but_not_deactivate_them(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    member = _bulk_learner(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=member)
    educator = UserFactory(staff=True)
    assign_object_role(educator, cohort, "cohort_admin")
    client = logged_in_client(educator)

    request = client.get(_interface_url(organisation.slug, "learners"))
    response = _bulk_post(client, organisation, "deactivate", [member])

    assert request.status_code == 200
    assert "learners/__actions/add_to_cohort" in request.content.decode()
    assert "learners/__actions/deactivate" not in request.content.decode()
    assert response.status_code == 403
    member.refresh_from_db()
    assert member.is_active is True


@pytest.mark.django_db
def test_a_run_skips_a_learner_outside_the_cohort_the_user_may_change(
    cohort_learner_manager_role: str,
):
    organisation = OrganisationFactory()
    learner = _bulk_learner(organisation=organisation)
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    educator = UserFactory(staff=True)
    assign_object_role(educator, cohort, cohort_learner_manager_role)

    result = run_apply(
        DeactivateLearnersBulkAction(),
        educator,
        organisation,
        Learner.objects.filter(pk=learner.pk),
        {},
    )

    learner.refresh_from_db()
    assert [(e.status, e.reason) for e in result.entries] == [
        ("skipped", "learners you don't have permission to change")
    ]
    assert learner.is_active is True


@pytest.mark.django_db
def test_a_run_changes_a_member_of_the_cohort_the_user_may_change(
    cohort_learner_manager_role: str,
):
    """The run checked the capability against the organisation while the
    preview checked it through the cohort, so a cohort-scoped educator was
    promised a change and then had every learner skipped."""
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    member = _bulk_learner(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=member)
    educator = UserFactory(staff=True)
    assign_object_role(educator, cohort, cohort_learner_manager_role)

    result = run_apply(
        DeactivateLearnersBulkAction(),
        educator,
        organisation,
        Learner.objects.filter(pk=member.pk),
        {},
    )

    member.refresh_from_db()
    assert result.changed == 1
    assert member.is_active is False


@pytest.mark.django_db
def test_a_run_reads_who_is_permitted_once_rather_than_per_learner(
    staff_client: Client, mocker: MockerFixture
):
    """`apply` asked `can` about every learner, four or five queries each, so
    an inline run over 250 learners cost over a thousand queries."""
    can = mocker.spy(actions_module, "can")
    organisation = OrganisationFactory()
    learners = [_bulk_learner(organisation=organisation) for _ in range(3)]

    _bulk_confirm(staff_client, organisation, "deactivate", learners)

    # Once for the preview and once for the run, never per learner.
    assert can.call_count <= 2


@pytest.mark.django_db
def test_bulk_deactivate_fires_one_event_per_changed_learner_and_none_for_skipped(
    staff_client: Client, mocker: MockerFixture
):
    fire = mocker.patch("freedom_ls.learner_management.learner_actions._fire")
    organisation = OrganisationFactory()
    active = [_bulk_learner(organisation=organisation) for _ in range(2)]
    inactive = _bulk_learner(organisation=organisation, is_active=False)

    _bulk_confirm(staff_client, organisation, "deactivate", [*active, inactive])

    fired = [(call.args[0], call.args[1].pk) for call in fire.call_args_list]
    assert sorted(fired, key=str) == sorted(
        [("learner.deactivated", learner.pk) for learner in active], key=str
    )


# bulk cohort membership actions


def _bulk_cohort_post(
    client: Client,
    organisation: Organisation,
    action_name: str,
    learners: list[Learner],
    **extra: str,
):
    return _bulk_post(client, organisation, action_name, learners, **extra)


def _bulk_cohort_confirm(
    client: Client,
    organisation: Organisation,
    action_name: str,
    learners: list[Learner],
    cohort: Cohort,
):
    return _bulk_confirm_with(
        client, organisation, action_name, learners, cohort=str(cohort.pk)
    )


def _bulk_confirm_with(
    client: Client,
    organisation: Organisation,
    action_name: str,
    learners: list[Learner],
    **extra: str,
):
    return _bulk_post(
        client,
        organisation,
        action_name,
        learners,
        confirmed="on",
        expected_count=str(len(learners)),
        **extra,
    )


def _picker_options(response) -> set[str]:
    document = lxml.html.fromstring(response.content.decode())
    return {
        option.get("value")
        for option in document.cssselect("select[name='cohort'] option")
        if option.get("value")
    }


@pytest.mark.django_db
def test_the_first_add_to_cohort_confirmation_renders_the_picker_unbound(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = _bulk_learner(organisation=organisation)

    response = _bulk_cohort_post(staff_client, organisation, "add_to_cohort", [learner])

    document = lxml.html.fromstring(response.content.decode())
    assert response.status_code == 200
    assert document.cssselect("select[name='cohort']")
    assert not document.cssselect(".text-error")
    assert document.cssselect("button[disabled]")


@pytest.mark.django_db
def test_the_picker_offers_only_active_cohorts_the_user_may_add_to(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    assigned = cast(Cohort, CohortFactory(organisation=organisation))
    CohortFactory(organisation=organisation)
    CohortFactory(organisation=organisation, is_active=False)
    educator = _cohort_admin_on(organisation, assigned)
    learner = _bulk_learner(organisation=organisation)
    CohortMembershipFactory(cohort=assigned, learner=learner)
    client = logged_in_client(educator)

    response = _bulk_cohort_post(client, organisation, "add_to_cohort", [learner])

    assert _picker_options(response) == {str(assigned.pk)}


@pytest.mark.django_db
def test_refresh_with_a_cohort_shows_what_the_cohort_would_change(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, name="Evening"))
    members = [_bulk_learner(organisation=organisation) for _ in range(2)]
    fresh = _bulk_learner(organisation=organisation)
    for learner in members:
        CohortMembershipFactory(cohort=cohort, learner=learner)

    response = _bulk_cohort_post(
        staff_client,
        organisation,
        "add_to_cohort",
        [*members, fresh],
        refresh="1",
        cohort=str(cohort.pk),
    )

    text = _bulk_text(response)
    assert response.status_code == 200
    assert "Add 1 learner to Evening." in text
    assert "2 are already in the cohort and will be skipped." in text


@pytest.mark.django_db
def test_refresh_without_a_cohort_answers_422_with_confirm_disabled(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = _bulk_learner(organisation=organisation)

    response = _bulk_cohort_post(
        staff_client, organisation, "add_to_cohort", [learner], refresh="1"
    )

    document = lxml.html.fromstring(response.content.decode())
    assert response.status_code == 422
    assert document.cssselect("button[disabled]")


@pytest.mark.django_db
def test_without_javascript_a_picked_cohort_can_be_confirmed(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    learner = _bulk_learner(organisation=organisation)
    url = _learners_bulk_url(organisation, "add_to_cohort")

    preview = staff_client.post(
        url, {"keys": [str(learner.pk)], "refresh": "1", "cohort": str(cohort.pk)}
    )

    document = lxml.html.fromstring(preview.content.decode())
    [confirm_form] = [
        form
        for form in document.cssselect("form")
        if form.cssselect("input[name='confirmed']")
    ]
    assert preview.status_code == 200
    assert not confirm_form.cssselect("button[disabled]")
    fields = {
        field.get("name"): field.get("value")
        for field in confirm_form.cssselect("input[type='hidden']")
    }
    assert fields["cohort"] == str(cohort.pk)

    staff_client.post(url, {**fields, "keys": [str(learner.pk)]})

    assert CohortMembership.objects.filter(learner=learner, cohort=cohort).exists()


@pytest.mark.django_db
def test_confirming_without_a_cohort_answers_422_and_adds_nobody(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = _bulk_learner(organisation=organisation)

    response = _bulk_confirm_with(
        staff_client, organisation, "add_to_cohort", [learner]
    )

    assert response.status_code == 422
    assert not CohortMembership.objects.filter(learner=learner).exists()


@pytest.mark.django_db
def test_a_cohort_the_user_cannot_add_to_is_not_a_valid_choice(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    assigned = cast(Cohort, CohortFactory(organisation=organisation))
    other = cast(Cohort, CohortFactory(organisation=organisation))
    educator = _cohort_admin_on(organisation, assigned)
    learner = _bulk_learner(organisation=organisation)
    CohortMembershipFactory(cohort=assigned, learner=learner)
    client = logged_in_client(educator)

    response = _bulk_cohort_confirm(
        client, organisation, "add_to_cohort", [learner], other
    )

    assert response.status_code == 422
    assert not CohortMembership.objects.filter(cohort=other).exists()


@pytest.mark.django_db
def test_classify_all_skips_every_learner_for_a_cohort_the_user_cannot_change(
    mock_site_context: Site,
):
    organisation = OrganisationFactory()
    assigned = cast(Cohort, CohortFactory(organisation=organisation))
    other = cast(Cohort, CohortFactory(organisation=organisation))
    educator = _cohort_admin_on(organisation, assigned)
    learner = _bulk_learner(organisation=organisation)

    outcomes = AddToCohortBulkAction().classify_all(
        _scoped_request(educator, organisation),
        Learner.objects.filter(pk=learner.pk),
        {"cohort": other},
    )

    assert outcomes == {
        str(learner.pk): BulkOutcome(
            "skipped", "learners you don't have permission to change"
        )
    }


@pytest.mark.django_db
def test_bulk_add_to_cohort_adds_only_the_learners_who_are_not_members(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    member = _bulk_learner(organisation=organisation)
    fresh = _bulk_learner(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=member)

    response = _bulk_cohort_confirm(
        staff_client, organisation, "add_to_cohort", [member, fresh], cohort
    )

    text = _bulk_text(response)
    assert "1 learner changed." in text
    assert "1 was already in the cohort." in text
    assert CohortMembership.objects.filter(cohort=cohort, learner=fresh).exists()


@pytest.mark.django_db
def test_bulk_add_to_cohort_fires_one_event_per_changed_learner(
    staff_client: Client, mocker: MockerFixture
):
    fire = mocker.patch("freedom_ls.learner_management.learner_actions._fire")
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    member = _bulk_learner(organisation=organisation)
    fresh = [_bulk_learner(organisation=organisation) for _ in range(2)]
    CohortMembershipFactory(cohort=cohort, learner=member)

    _bulk_cohort_confirm(
        staff_client, organisation, "add_to_cohort", [member, *fresh], cohort
    )

    fired = [(call.args[0], call.args[1].pk) for call in fire.call_args_list]
    assert sorted(fired, key=str) == sorted(
        [("cohort_membership.added", learner.pk) for learner in fresh], key=str
    )


@pytest.mark.django_db
def test_a_cohort_deactivated_after_the_confirmation_fails_each_learner_without_aborting(
    mock_site_context: Site,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))
    learner = _bulk_learner(organisation=organisation)
    run = BulkActionRun.objects.create(
        scope=organisation,
        requested_by=UserFactory(superuser=True),
        action_path=f"{AddToCohortBulkAction.__module__}.AddToCohortBulkAction",
        table_key="learners",
        action_name="add_to_cohort",
        target={"cohort": str(cohort.pk)},
        keys=[str(learner.pk)],
        status=RunStatus.QUEUED,
    )

    result = run_bulk_action(str(run.pk), mock_site_context.pk)

    assert [(c.status, c.count) for c in result.counts] == [("failed", 1)]
    assert not CohortMembership.objects.filter(learner=learner).exists()


@pytest.mark.django_db
def test_a_saved_target_in_another_organisation_does_not_resolve(
    mock_site_context: Site,
):
    organisation = OrganisationFactory()
    foreign = cast(Cohort, CohortFactory(organisation=OrganisationFactory()))

    with pytest.raises(Http404):
        AddToCohortBulkAction().resolve_target(
            organisation, {"cohort": str(foreign.pk)}
        )


@pytest.mark.django_db
def test_bulk_remove_from_cohort_confirmation_names_the_courses_lost(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 2)
    members = [_bulk_learner(organisation=organisation) for _ in range(2)]
    outsider = _bulk_learner(organisation=organisation)
    for learner in members:
        CohortMembershipFactory(cohort=cohort, learner=learner)

    response = _bulk_cohort_post(
        staff_client,
        organisation,
        "remove_from_cohort",
        [*members, outsider],
        refresh="1",
        cohort=str(cohort.pk),
    )

    text = _bulk_text(response)
    expected_titles = " and ".join(
        sorted(r.course.title for r in cohort.course_registrations.all())
    )
    assert f"They lose access to: {expected_titles}." in text
    assert "1 is not a member and will be skipped." in text


@pytest.mark.django_db
def test_bulk_remove_from_cohort_wording_costs_the_same_for_any_selection_size(
    mock_site_context: Site, django_assert_num_queries
):
    """The courses lost used to be read once per selected learner."""
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 2)
    members = [_bulk_learner(organisation=organisation) for _ in range(4)]
    for learner in members:
        CohortMembershipFactory(cohort=cohort, learner=learner)
    CohortMembershipFactory(
        cohort=_cohort_with_courses(organisation, 1), learner=members[0]
    )
    classified = {str(learner.pk): BulkOutcome("changed") for learner in members}

    with django_assert_num_queries(5):
        wording = RemoveFromCohortBulkAction().confirmation_wording(
            RequestFactory().post("/"),
            Learner.objects.filter(pk__in=[learner.pk for learner in members]),
            classified,
            {"cohort": cohort},
        )

    assert wording.sentence == f"Remove 4 learners from {cohort.name}."
    assert len(wording.consequences) == 1


@pytest.mark.django_db
def test_bulk_remove_from_cohort_deletes_memberships_and_skips_non_members(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    member = _bulk_learner(organisation=organisation)
    outsider = _bulk_learner(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=member)

    response = _bulk_cohort_confirm(
        staff_client, organisation, "remove_from_cohort", [member, outsider], cohort
    )

    text = _bulk_text(response)
    assert "1 learner changed." in text
    assert "1 was not a member." in text
    assert not CohortMembership.objects.filter(cohort=cohort).exists()


# bulk actions above the background threshold


def _task_rows():
    from django_tasks_db.models import DBTaskResult

    return DBTaskResult.objects.filter(task_path__endswith="_run_bulk_action_task")


@pytest.mark.django_db(transaction=True)
def test_bulk_confirmation_above_the_threshold_shows_only_the_total_and_runs_in_background(
    staff_client: Client, settings
):
    settings.BULK_BACKGROUND_THRESHOLD = 2
    organisation = OrganisationFactory()
    learners = [_bulk_learner(organisation=organisation) for _ in range(2)]
    inactive = _bulk_learner(organisation=organisation, is_active=False)

    response = _bulk_post(
        staff_client, organisation, "deactivate", [*learners, inactive]
    )

    text = _bulk_text(response)
    assert "This will affect 3 learners." in text
    assert "background" in text
    assert "already inactive" not in text


@pytest.mark.django_db(transaction=True)
def test_bulk_confirm_above_the_threshold_enqueues_one_task_and_keeps_the_reader_on_the_table(
    staff_client: Client, settings, database_task_backend: None
):
    settings.BULK_BACKGROUND_THRESHOLD = 2
    organisation = OrganisationFactory()
    learners = [_bulk_learner(organisation=organisation) for _ in range(3)]

    response = _bulk_confirm(staff_client, organisation, "deactivate", learners)

    run = BulkActionRun.objects.get()
    trigger = json.loads(response["HX-Trigger"])
    assert response.status_code == 204
    assert "HX-Redirect" not in response
    assert "closeModal" in trigger
    assert trigger["bulkRunStarted"]["status_url"] == reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": organisation.slug,
            "path_string": f"learners/__runs/{run.pk}",
        },
    )
    assert trigger["bulkRunStarted"]["action"] == "deactivate"
    assert run.status == RunStatus.QUEUED
    assert _task_rows().count() == 1
    assert Learner.objects.filter(is_active=False).count() == 0


@pytest.mark.django_db(transaction=True)
def test_bulk_confirm_above_the_threshold_without_javascript_returns_to_the_list(
    staff_client: Client, settings, database_task_backend: None
):
    settings.BULK_BACKGROUND_THRESHOLD = 2
    organisation = OrganisationFactory()
    learners = [_bulk_learner(organisation=organisation) for _ in range(3)]

    response = staff_client.post(
        _learners_bulk_url(organisation, "deactivate"),
        {
            "keys": [str(learner.pk) for learner in learners],
            "confirmed": "on",
            "expected_count": "3",
        },
        follow=True,
    )

    assert response.redirect_chain == [
        (
            reverse(
                "educator_interface:interface",
                kwargs={
                    "organisation_slug": organisation.slug,
                    "path_string": "learners",
                },
            ),
            303,
        )
    ]
    assert "Deactivate is running in the background." in response.content.decode()


@pytest.mark.django_db(transaction=True)
def test_bulk_confirm_at_the_threshold_still_runs_inline(
    staff_client: Client, settings, database_task_backend: None
):
    settings.BULK_BACKGROUND_THRESHOLD = 3
    organisation = OrganisationFactory()
    learners = [_bulk_learner(organisation=organisation) for _ in range(3)]

    response = _bulk_confirm(staff_client, organisation, "deactivate", learners)

    assert response.status_code == 200
    assert _task_rows().count() == 0
    assert Learner.objects.filter(is_active=False).count() == 3


# bulk course registration and setup email actions


def _course_option_values(response) -> set[str]:
    document = lxml.html.fromstring(response.content.decode())
    return {
        option.get("value")
        for option in document.cssselect("select[name='course'] option")
        if option.get("value")
    }


def _bulk_pending_learner(organisation: Organisation) -> Learner:
    user = UserFactory(last_login=None)
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return _bulk_learner(organisation=organisation, user=user)


@pytest.mark.django_db
def test_the_register_picker_offers_only_registerable_courses(staff_client: Client):
    organisation = OrganisationFactory()
    published = CourseFactory(visibility=CourseVisibility.PUBLISHED)
    CourseFactory(visibility=CourseVisibility.COMING_SOON)
    learner = _bulk_learner(organisation=organisation)

    response = _bulk_post(staff_client, organisation, "register_for_course", [learner])

    assert response.status_code == 200
    assert _course_option_values(response) == {str(published.pk)}


@pytest.mark.django_db
def test_bulk_register_confirmation_counts_changes_and_skips(staff_client: Client):
    organisation = OrganisationFactory()
    course = CourseFactory(title="Algebra")
    registered = _bulk_learner(organisation=organisation)
    fresh = _bulk_learner(organisation=organisation)
    LearnerCourseRegistrationFactory(learner=registered, course=course)

    response = _bulk_post(
        staff_client,
        organisation,
        "register_for_course",
        [registered, fresh],
        refresh="1",
        course=str(course.pk),
    )

    text = _bulk_text(response)
    assert response.status_code == 200
    assert "Register 1 learner for Algebra." in text
    assert "1 is already registered individually and will be skipped." in text


@pytest.mark.django_db
def test_bulk_register_without_a_course_answers_422(staff_client: Client):
    organisation = OrganisationFactory()
    learner = _bulk_learner(organisation=organisation)

    response = _bulk_post(
        staff_client, organisation, "register_for_course", [learner], refresh="1"
    )

    assert response.status_code == 422


@pytest.mark.django_db
def test_bulk_register_registers_only_learners_without_an_active_registration(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    course = CourseFactory()
    registered = _bulk_learner(organisation=organisation)
    fresh = _bulk_learner(organisation=organisation)
    LearnerCourseRegistrationFactory(learner=registered, course=course)

    response = _bulk_confirm_with(
        staff_client,
        organisation,
        "register_for_course",
        [registered, fresh],
        course=str(course.pk),
    )

    assert "1 learner changed." in _bulk_text(response)
    assert LearnerCourseRegistration.objects.filter(
        learner=fresh, course=course, is_active=True
    ).exists()


@pytest.mark.django_db
def test_bulk_register_records_one_course_registered_event_per_changed_learner(
    staff_client: Client,
    django_capture_on_commit_callbacks,
    mocker: MockerFixture,
):
    fire = mocker.patch("freedom_ls.webhooks.events.fire_webhook_event_for_site")
    organisation = OrganisationFactory()
    course = CourseFactory()
    registered = _bulk_learner(organisation=organisation)
    fresh = [_bulk_learner(organisation=organisation) for _ in range(2)]
    LearnerCourseRegistrationFactory(learner=registered, course=course)

    with django_capture_on_commit_callbacks(execute=True):
        _bulk_confirm_with(
            staff_client,
            organisation,
            "register_for_course",
            [registered, *fresh],
            course=str(course.pk),
        )

    fired = [call.args[1]["user_id"] for call in fire.call_args_list]
    assert sorted(fired) == sorted(learner.user_id for learner in fresh)


@pytest.mark.django_db
def test_a_cohort_admin_registers_only_learners_in_their_own_cohorts(
    mock_site_context: Site,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    educator = _cohort_admin_on(organisation, cohort)
    mine = _bulk_learner(organisation=organisation)
    theirs = _bulk_learner(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=mine)
    course = CourseFactory()

    outcomes = RegisterForCourseBulkAction().classify_all(
        _scoped_request(educator, organisation),
        Learner.objects.filter(pk__in=[mine.pk, theirs.pk]),
        {"course": course},
    )

    assert outcomes == {
        str(mine.pk): BulkOutcome("changed"),
        str(theirs.pk): BulkOutcome(
            "skipped", "learners you don't have permission to change"
        ),
    }


@pytest.mark.django_db
def test_bulk_unregister_confirmation_counts_learners_who_keep_access_through_a_cohort(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    course = CourseFactory(title="Algebra")
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    keeps = _bulk_learner(organisation=organisation)
    loses = _bulk_learner(organisation=organisation)
    unregistered = _bulk_learner(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=keeps)
    for learner in (keeps, loses):
        LearnerCourseRegistrationFactory(learner=learner, course=course)

    response = _bulk_post(
        staff_client,
        organisation,
        "unregister_from_course",
        [keeps, loses, unregistered],
        refresh="1",
        course=str(course.pk),
    )

    text = _bulk_text(response)
    assert "Unregister 2 learners from Algebra." in text
    assert "1 keeps access through a cohort." in text
    assert "1 is not registered individually and will be skipped." in text


@pytest.mark.django_db
def test_bulk_unregister_wording_costs_the_same_for_any_selection_size(
    mock_site_context: Site, django_assert_num_queries
):
    """Who keeps access through a cohort used to be read once per learner."""
    organisation = OrganisationFactory()
    course = CourseFactory(title="Algebra")
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    learners = [_bulk_learner(organisation=organisation) for _ in range(4)]
    for learner in learners:
        LearnerCourseRegistrationFactory(learner=learner, course=course)
    for learner in learners[:2]:
        CohortMembershipFactory(cohort=cohort, learner=learner)
    classified = {str(learner.pk): BulkOutcome("changed") for learner in learners}

    with django_assert_num_queries(1):
        wording = UnregisterFromCourseBulkAction().confirmation_wording(
            RequestFactory().post("/"),
            Learner.objects.filter(pk__in=[learner.pk for learner in learners]),
            classified,
            {"course": course},
        )

    assert wording.sentence == "Unregister 4 learners from Algebra."
    assert wording.consequences == ["2 keep access through a cohort."]


@pytest.mark.django_db
def test_bulk_unregister_deactivates_individual_registrations(staff_client: Client):
    organisation = OrganisationFactory()
    course = CourseFactory()
    registered = _bulk_learner(organisation=organisation)
    other = _bulk_learner(organisation=organisation)
    LearnerCourseRegistrationFactory(learner=registered, course=course)

    response = _bulk_confirm_with(
        staff_client,
        organisation,
        "unregister_from_course",
        [registered, other],
        course=str(course.pk),
    )

    assert "1 learner changed." in _bulk_text(response)
    assert not LearnerCourseRegistration.objects.get(
        learner=registered, course=course
    ).is_active


@pytest.mark.django_db
def test_bulk_resend_confirmation_skips_learners_who_set_up_their_account(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    pending = _bulk_pending_learner(organisation)
    done = _bulk_learner(organisation=organisation)

    response = _bulk_post(
        staff_client, organisation, "resend_setup_email", [pending, done]
    )

    text = _bulk_text(response)
    assert "Resend the setup email to 1 learner." in text
    assert "1 account is already set up and will be skipped." in text


@pytest.mark.django_db
def test_bulk_resend_confirmation_counts_set_up_accounts_in_the_plural(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    pending = _bulk_pending_learner(organisation)
    done = [_bulk_learner(organisation=organisation) for _ in range(2)]

    response = _bulk_post(
        staff_client, organisation, "resend_setup_email", [pending, *done]
    )

    assert "2 accounts are already set up and will be skipped." in _bulk_text(response)


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_bulk_resend_sends_one_email_per_pending_learner(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    pending = [_bulk_pending_learner(organisation) for _ in range(2)]

    with django_capture_on_commit_callbacks(execute=True):
        response = _bulk_confirm(
            staff_client, organisation, "resend_setup_email", pending
        )

    assert "2 learners changed." in _bulk_text(response)
    assert len(mail.outbox) == 2


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
@pytest.mark.parametrize(
    ("set_up", "line"),
    [(1, "1 account was already set up."), (2, "2 accounts were already set up.")],
)
def test_bulk_resend_result_counts_the_accounts_already_set_up(
    staff_client: Client, django_capture_on_commit_callbacks, set_up: int, line: str
):
    organisation = OrganisationFactory()
    pending = _bulk_pending_learner(organisation)
    done = [_bulk_learner(organisation=organisation) for _ in range(set_up)]

    with django_capture_on_commit_callbacks(execute=True):
        response = _bulk_confirm(
            staff_client, organisation, "resend_setup_email", [pending, *done]
        )

    text = _bulk_text(response)
    assert "1 learner changed." in text
    assert line in text


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_bulk_resend_skips_a_learner_emailed_inside_the_resend_window(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    recent = _bulk_pending_learner(organisation)
    fresh = _bulk_pending_learner(organisation)
    with django_capture_on_commit_callbacks(execute=True):
        _bulk_confirm(staff_client, organisation, "resend_setup_email", [recent])
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        response = _bulk_confirm(
            staff_client, organisation, "resend_setup_email", [recent, fresh]
        )

    text = _bulk_text(response)
    assert "1 learner changed." in text
    assert "1 setup email was sent recently." in text
    assert len(mail.outbox) == 1


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_bulk_resend_records_one_entry_per_email_sent_naming_the_sender(
    mock_site_context: Site, logged_in_client, django_capture_on_commit_callbacks
):
    """The bulk resend sent the emails but wrote no audit entry, while the
    single-learner resend records one; the audit log said nothing happened."""
    organisation = OrganisationFactory()
    pending = [_bulk_pending_learner(organisation) for _ in range(2)]
    done = _bulk_learner(organisation=organisation)
    sender = UserFactory(superuser=True)

    with django_capture_on_commit_callbacks(execute=True):
        _bulk_confirm(
            logged_in_client(sender),
            organisation,
            "resend_setup_email",
            [*pending, done],
        )

    entries = AuditLogEntry.unscoped.filter(action="learner.setup_email_resent")
    assert {entry.target_object_id for entry in entries} == {
        str(learner.pk) for learner in pending
    }
    assert {entry.actor for entry in entries} == {sender}


@pytest.mark.django_db
def test_bulk_deactivate_entries_name_the_educator_who_ran_it(
    mock_site_context: Site, logged_in_client
):
    """Bulk runs called the services without an actor, so every entry a bulk
    change wrote was attributed to nobody."""
    organisation = OrganisationFactory()
    learners = [_bulk_learner(organisation=organisation) for _ in range(2)]
    educator = UserFactory(superuser=True)

    _bulk_confirm(logged_in_client(educator), organisation, "deactivate", learners)

    entries = AuditLogEntry.unscoped.filter(action="learner.deactivated")
    assert entries.count() == 2
    assert {entry.actor for entry in entries} == {educator}


# cohort bulk actions


def _cohorts_bulk_post(
    client: Client,
    organisation: Organisation,
    action_name: str,
    cohorts: list[Cohort],
    **extra: str,
):
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
):
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
def test_cohort_state_action_deactivates_through_the_service(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _bulk_cohort(organisation)

    _post(staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate"))

    cohort.refresh_from_db()
    assert cohort.is_active is False


@pytest.mark.django_db
def test_cohort_state_action_reactivates_through_the_service(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _bulk_cohort(organisation, is_active=False)

    _post(staff_client, _cohort_url(organisation, cohort, "/__actions/reactivate"))

    cohort.refresh_from_db()
    assert cohort.is_active is True


@pytest.mark.django_db
def test_bulk_cohort_deactivate_confirmation_counts_changes_and_skips(
    staff_client: Client,
):
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
def test_bulk_cohort_deactivate_changes_only_active_cohorts(staff_client: Client):
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
):
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
def test_bulk_cohort_reactivate_activates_inactive_cohorts(staff_client: Client):
    organisation = OrganisationFactory()
    inactive = _bulk_cohort(organisation, is_active=False)

    _cohorts_bulk_confirm(staff_client, organisation, "reactivate", [inactive])

    inactive.refresh_from_db()
    assert inactive.is_active is True


@pytest.mark.django_db
def test_the_cohort_register_picker_offers_only_registerable_courses(
    staff_client: Client,
):
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
):
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
    assert "1 is an inactive cohort and will be skipped." in text


@pytest.mark.django_db
def test_bulk_cohort_register_registers_only_unregistered_active_cohorts(
    staff_client: Client,
):
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
def test_bulk_cohort_register_without_a_course_answers_422(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _bulk_cohort(organisation)

    response = _cohorts_bulk_post(
        staff_client, organisation, "register", [cohort], refresh="1"
    )

    assert response.status_code == 422


@pytest.mark.django_db
def test_bulk_cohort_register_fires_one_course_registered_event_per_changed_cohort(
    staff_client: Client,
    django_capture_on_commit_callbacks,
    mocker: MockerFixture,
):
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
def test_a_cohort_admin_registers_only_their_own_cohorts(mock_site_context: Site):
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
@pytest.mark.parametrize(
    "action_class",
    [RegisterCohortForCourseBulkAction, UnregisterCohortFromCourseBulkAction],
)
def test_run_skips_a_cohort_that_was_already_inactive_rather_than_failing_it(
    mock_site_context: Site, action_class: type[CohortCourseBulkAction]
):
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

    assert [(e.status, e.reason) for e in result.entries] == [
        ("skipped", "an inactive cohort")
    ]


@pytest.mark.django_db
def test_bulk_cohort_unregister_confirmation_counts_changes_and_skips(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    course = CourseFactory(title="Algebra")
    registered = _bulk_cohort(organisation)
    unregistered = _bulk_cohort(organisation)
    inactive = _bulk_cohort(organisation, is_active=False)
    CohortCourseRegistrationFactory(cohort=registered, course=course)

    response = _cohorts_bulk_post(
        staff_client,
        organisation,
        "unregister",
        [registered, unregistered, inactive],
        refresh="1",
        course=str(course.pk),
    )

    text = _bulk_text(response)
    assert "Unregister 1 cohort from Algebra." in text
    assert "1 is not registered and will be skipped." in text
    assert "1 is an inactive cohort and will be skipped." in text


@pytest.mark.django_db
def test_bulk_cohort_unregister_deactivates_the_active_registration(
    staff_client: Client, django_capture_on_commit_callbacks, mocker: MockerFixture
):
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
            "unregister",
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
def test_the_add_learners_cap_message_links_to_the_import_page(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    educator = _organisation_admin_on(organisation)
    lines = "\n".join(f"person{n}@example.com" for n in range(51))

    response = logged_in_client(educator).post(
        _add_learners_list_url(organisation),
        {"entries": lines},
        HTTP_HX_REQUEST="true",
    )

    import_url = reverse(
        "educator_interface:learner_import",
        kwargs={"organisation_slug": organisation.slug},
    )
    assert (
        response.status_code,
        f'href="{import_url}"' in response.content.decode(),
    ) == (
        422,
        True,
    )


@pytest.mark.django_db
def test_an_add_learners_error_that_is_not_the_cap_carries_no_import_link(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    educator = _organisation_admin_on(organisation)

    response = logged_in_client(educator).post(
        _add_learners_list_url(organisation),
        {"entries": ""},
        HTTP_HX_REQUEST="true",
    )

    import_url = reverse(
        "educator_interface:learner_import",
        kwargs={"organisation_slug": organisation.slug},
    )
    assert import_url not in response.content.decode()


# -- recorded runs: the organisation scope and the finished notification ----

GONE = "00000000-0000-0000-0000-000000000001"
DEACTIVATE = (
    f"{DeactivateLearnersBulkAction.__module__}.{DeactivateLearnersBulkAction.__name__}"
)


def _learner() -> Learner:
    return cast(Learner, LearnerFactory(organisation=OrganisationFactory()))


def _run_over(learner: Learner, *others: str) -> BulkActionRun:
    return cast(
        BulkActionRun,
        BulkActionRun.objects.create(
            scope=learner.organisation,
            requested_by=UserFactory(superuser=True),
            action_path=DEACTIVATE,
            table_key="learners",
            action_name="deactivate",
            keys=[str(learner.pk), *others],
        ),
    )


@pytest.mark.django_db
def test_a_learner_of_another_organisation_is_not_touched(mock_site_context: Site):
    other = _learner()
    run = _run_over(_learner(), str(other.pk))

    result = run_bulk_action(str(run.pk), mock_site_context.pk)

    other.refresh_from_db()
    assert other.is_active is True
    assert BulkCount("skipped", NOT_FOUND, 1) in result.counts


@pytest.mark.django_db
def test_a_requester_who_lost_the_grant_skips_every_object_and_the_run_is_done(
    mock_site_context: Site,
):
    learner = _learner()
    run = _run_over(learner)
    run.requested_by = UserFactory(staff=True)
    run.save(update_fields=["requested_by"])

    result = run_bulk_action(str(run.pk), mock_site_context.pk)

    learner.refresh_from_db()
    run.refresh_from_db()
    assert (result.changed, learner.is_active, run.status) == (
        0,
        True,
        RunStatus.DONE,
    )
    assert [item.reason for item in result.counts] == [
        "learners you don't have permission to change"
    ]


def _notifications_for(run: BulkActionRun) -> list[tuple[int, str]]:
    return [
        (notification.user_id, notification.message)
        for notification in Notification._base_manager.filter(
            category="bulk_action.finished", object_id=str(run.pk)
        )
    ]


@pytest.mark.django_db
def test_the_task_tells_the_requester_the_run_finished(
    mock_site_context: Site, django_capture_on_commit_callbacks
):
    run = _run_over(_learner(), GONE)

    with django_capture_on_commit_callbacks(execute=True):
        _run_bulk_action_task.func(str(run.pk), mock_site_context.pk)

    assert _notifications_for(run) == [
        (run.requested_by_id, "Deactivate finished: 1 learner changed, 1 skipped.")
    ]


@pytest.mark.django_db
def test_the_task_tells_the_requester_where_a_failed_run_stopped(
    mock_site_context: Site, django_capture_on_commit_callbacks, monkeypatch
):
    def _explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("freedom_ls.panel_framework.bulk_runs.run_apply", _explode)
    run = _run_over(_learner())

    with (
        django_capture_on_commit_callbacks(execute=True),
        pytest.raises(RuntimeError),
    ):
        _run_bulk_action_task.func(str(run.pk), mock_site_context.pk)

    assert _notifications_for(run) == [
        (run.requested_by_id, "Deactivate stopped after 0 of 1 learner.")
    ]


@pytest.mark.django_db
def test_an_inline_run_raises_no_notification(
    mock_site_context: Site, django_capture_on_commit_callbacks
):
    run = _run_over(_learner())

    with django_capture_on_commit_callbacks(execute=True):
        run_bulk_action(str(run.pk), mock_site_context.pk)

    assert _notifications_for(run) == []


@pytest.mark.django_db
def test_an_unfinished_run_is_not_notified(
    mock_site_context: Site, django_capture_on_commit_callbacks
):
    run = _run_over(_learner())

    with django_capture_on_commit_callbacks(execute=True):
        report_finished(str(run.pk), mock_site_context.pk)

    assert _notifications_for(run) == []


@pytest.mark.django_db
def test_the_summary_counts_in_the_actions_own_noun(mock_site_context: Site):
    run = _run_over(_learner())
    run.status = RunStatus.DONE
    run.result = BulkResult(
        counts=[
            BulkCount("changed", "", 3),
            BulkCount("skipped", "already inactive", 2),
            BulkCount("skipped", NOT_FOUND, 1),
            BulkCount("failed", "error", 1),
        ],
        entries=[],
        left_out=0,
    ).to_json()

    assert run_summary(run) == (
        "Deactivate finished: 3 learners changed, 3 skipped, 1 failed."
    )
