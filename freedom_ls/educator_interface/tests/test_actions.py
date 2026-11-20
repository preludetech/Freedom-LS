"""The educator interface's panel actions, driven through the interface URLs."""

from __future__ import annotations

import contextlib
import json
import re
import uuid
from collections.abc import Callable
from typing import cast

import lxml.html
import pytest
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
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseAudience, CourseVisibility
from freedom_ls.educator_interface import actions as actions_module
from freedom_ls.educator_interface.actions import (
    AddLearnerAction,
    AddToCohortBulkAction,
    CohortCourseBulkAction,
    DeactivateCohortRegistrationBulkAction,
    DeactivateLearnersBulkAction,
    DeactivateRegistrationBulkAction,
    RegisterCohortForCourseBulkAction,
    RegisterForCourseBulkAction,
    RemoveFromCohortAction,
    RemoveFromCohortBulkAction,
    RequiresActiveCohortMixin,
    cohort_not_empty_sentence,
)
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
    REGISTRATION_CHANGED,
)
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.tests.helpers import (
    _assert_message_dialog,
    _bulk_learner,
    _bulk_post,
    _bulk_text,
    _cohort,
    _cohort_url,
    _interface_url,
    _learners_bulk_url,
    _post,
    _remove_role_url,
    _staff_member_holding,
    _state_url,
    course_per_reach_row,
)
from freedom_ls.educator_interface.views import CohortConfig
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
    StaffMember,
)
from freedom_ls.learner_management.queries import (
    CHANGE_LEARNER,
    COURSE_NOT_OPEN_MESSAGE,
    VIEW_COHORT,
    VIEW_LEARNER,
)
from freedom_ls.learner_management.role_assignment import (
    assign_role,
)
from freedom_ls.learner_management.tests.scenario_world import custom_role_config
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.panel_framework.bulk_actions import (
    BULK_ACTIONS,
    BulkCount,
    BulkOutcome,
    BulkResult,
    run_apply,
)
from freedom_ls.panel_framework.bulk_runs import (
    run_bulk_action,
)
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.models import BulkActionRun, RunStatus
from freedom_ls.role_based_permissions.types import SCOPE_OBJECT, Role
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.tests.audit_assertions import assert_entry


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


def _picker_dialog(client: Client, url: str) -> lxml.html.HtmlElement:
    response = client.get(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    return lxml.html.fromstring(response.content.decode())


def _dialog_title(document: lxml.html.HtmlElement) -> str:
    (title,) = document.cssselect("#app-modal-title")
    return " ".join(title.text_content().split())


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
    # The 422 is the inline form itself, holding what was typed, not a dialog.
    document = lxml.html.fromstring(f"<div>{response.content.decode()}</div>")
    (form,) = document.cssselect("form#cohort-name-form")
    assert form.cssselect("input[name=name]")[0].get("value") == "Year 10 Science"
    assert not document.cssselect("header")


@pytest.mark.django_db
def test_the_rename_fragment_is_the_inline_form_holding_the_current_name(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Year 11 Science")

    response = staff_client.get(
        _cohort_url(organisation, cohort, "/__actions/edit"), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 200
    document = lxml.html.fromstring(f"<div>{response.content.decode()}</div>")
    (form,) = document.cssselect("form#cohort-name-form")
    (name,) = form.cssselect("input[name=name]")
    assert name.get("value") == "Year 11 Science"
    assert name.get("autofocus") is None


@pytest.mark.django_db
def test_an_empty_cohort_name_shows_the_bare_message_as_an_announced_field_error(
    staff_client: Client,
):
    """A field error in the inline form used to repeat the field's label, carry
    no role and leave the input unlinked from it."""
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Year 11 Science")

    response = _post(
        staff_client,
        _cohort_url(organisation, cohort, "/__actions/edit"),
        {"name": ""},
    )

    document = lxml.html.fromstring(f"<div>{response.content.decode()}</div>")
    (name,) = document.cssselect("form#cohort-name-form input[name=name]")
    (error,) = document.cssselect("form#cohort-name-form [role=alert]")
    assert response.status_code == 422
    assert error.text_content().strip() == "This field is required."
    assert error.get("id")
    assert name.get("aria-describedby") == error.get("id")
    assert name.get("aria-invalid") == "true"
    assert not document.cssselect("[data-error-summary]")


@pytest.mark.django_db
def test_an_inline_form_field_without_an_error_is_neither_invalid_nor_described(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Year 11 Science")

    response = staff_client.get(
        _cohort_url(organisation, cohort, "/__actions/edit"), HTTP_HX_REQUEST="true"
    )

    document = lxml.html.fromstring(f"<div>{response.content.decode()}</div>")
    (name,) = document.cssselect("form#cohort-name-form input[name=name]")
    assert name.get("aria-invalid") is None
    assert name.get("aria-describedby") is None
    assert not document.cssselect("[role=alert]")


@pytest.mark.django_db
def test_the_learner_name_form_puts_each_field_error_under_its_own_field(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    client = _site_admin_client(mock_site_context, logged_in_client)

    response = _post(
        client,
        _edit_name_url(organisation, learner),
        {"first_name": "x" * 201, "last_name": "y" * 201},
    )

    document = lxml.html.fromstring(f"<div>{response.content.decode()}</div>")
    alerts = document.cssselect("form [role=alert]")
    assert response.status_code == 422
    assert len(alerts) == 2
    for field_name in ("first_name", "last_name"):
        (field,) = document.cssselect(f"form input[name={field_name}]")
        (error,) = [a for a in alerts if a.get("id") == field.get("aria-describedby")]
        assert field.get("aria-invalid") == "true"
        assert "Ensure this value has at most 200 characters" in error.text_content()
        assert "name" not in error.text_content().split("Ensure")[0].lower()


@pytest.mark.django_db
def test_a_rename_answers_204_with_the_new_title_for_the_page(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Year 11 Science")

    response = _post(
        staff_client,
        _cohort_url(organisation, cohort, "/__actions/edit"),
        {"name": "Year 12 Science"},
    )

    assert response.status_code == 204
    trigger = json.loads(response["HX-Trigger"])
    assert COHORT_CHANGED in trigger
    assert trigger["instanceTitleChanged"]["title"] == "Year 12 Science"


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
    assert "Someone else may have deactivated it already." in " ".join(
        response.content.decode().split()
    )
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
def test_reactivate_post_from_a_tab_navigates_back_to_that_tab(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1, is_active=False)
    tab_path = _cohort_url(organisation, cohort, "/courses")

    response = staff_client.post(
        _cohort_url(organisation, cohort, "/__actions/reactivate"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_CURRENT_URL=f"http://testserver{tab_path}",
    )

    assert json.loads(response["HX-Location"])["path"] == tab_path


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
    inactive_learner = LearnerFactory(organisation=organisation, is_active=False)
    CohortMembershipFactory(cohort=cohort, learner=inactive_learner)
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
def test_an_inactive_cohorts_settings_tab_renders_no_rename_form(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, is_active=False)

    response = staff_client.get(_cohort_url(organisation, cohort, "/__tabs/settings"))

    document = lxml.html.fromstring(response.content.decode())
    assert not document.cssselect("form#cohort-name-form")


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
    assert "to change its name." in " ".join(response.content.decode().split())
    assert "Old group is inactive" in response.content.decode()
    # The form targets itself, so the notice is sent to the dialog instead.
    assert response["HX-Retarget"] == "#app-modal-body"
    assert response["HX-Reswap"] == "innerHTML"


def _all_subclasses(cls: type) -> set[type]:
    found: set[type] = set()
    for subclass in cls.__subclasses__():
        found |= {subclass} | _all_subclasses(subclass)
    return found


def test_every_action_guarded_by_an_active_cohort_names_what_it_blocks() -> None:
    guarded = _all_subclasses(RequiresActiveCohortMixin)

    assert guarded
    assert all(
        isinstance(getattr(subclass, "blocked_phrase", None), str)
        for subclass in guarded
        if subclass.refuse_inactive is RequiresActiveCohortMixin.refuse_inactive
    )


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

    assert "Register Evening group for a course?" in text


@pytest.mark.django_db
def test_the_cohort_register_dialog_names_the_chosen_course(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Evening group")
    course = CourseFactory(title="Algebra")

    document = _picker_dialog(
        staff_client, _register_url(organisation, cohort) + f"?course={course.pk}"
    )

    assert _dialog_title(document) == "Register Evening group for Algebra?"


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
    assert "to register it for a course." in " ".join(response.content.decode().split())
    assert "Old group is inactive" in response.content.decode()
    assert not cohort.course_registrations.exists()


# deactivate a cohort registration


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
    assert "to deactivate one of its course registrations." in " ".join(
        response.content.decode().split()
    )
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
def test_a_site_admins_learner_settings_tab_offers_edit_name(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    client = _site_admin_client(mock_site_context, logged_in_client)

    triggers = _settings_triggers(client, organisation, learner)

    assert _edit_name_url(organisation, learner) in triggers


@pytest.mark.django_db
def test_an_organisation_admins_learner_settings_tab_offers_no_edit_name(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    user = UserFactory(staff=True)
    assign_role(UserFactory(superuser=True), user, "organisation_admin", organisation)
    client = logged_in_client(user)

    triggers = _settings_triggers(client, organisation, learner)

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


def _settings_triggers(
    client: Client, organisation: Organisation, learner: Learner
) -> set[str | None]:
    """The action URLs the learner's Settings tab offers, read as the
    instance-level URLs the actions also answer at."""
    response = client.get(
        _interface_url(organisation.slug, f"learners/{learner.pk}/__tabs/settings")
    )
    document = lxml.html.fromstring(response.content.decode())
    controls = [
        *(
            b.get("hx-get")
            for b in document.cssselect("section[data-panel] button[hx-get]")
        ),
        *(
            f.get("hx-post")
            for f in document.cssselect("section[data-panel] form[hx-post]")
        ),
    ]
    return {re.sub(r"/__tabs/settings(/__panels/[\w-]+)?", "", url) for url in controls}


@pytest.mark.django_db
def test_an_active_learners_settings_tab_offers_deactivate_not_reactivate(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=True)

    triggers = _settings_triggers(staff_client, organisation, learner)

    assert (
        _learner_state_url(organisation, learner, "deactivate") in triggers,
        _learner_state_url(organisation, learner, "reactivate") in triggers,
    ) == (True, False)


@pytest.mark.django_db
def test_a_removed_learners_settings_tab_offers_reactivate_not_deactivate(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=False)

    triggers = _settings_triggers(staff_client, organisation, learner)

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
def test_learner_header_state_action_from_a_tab_navigates_back_to_that_tab(
    staff_client: Client,
):
    """Deactivating from the history tab used to land on the Overview tab."""
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=True)
    tab_path = _interface_url(
        organisation.slug, f"learners/{learner.pk}/__tabs/history"
    )

    response = staff_client.post(
        _learner_state_url(organisation, learner, "deactivate"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_CURRENT_URL=f"http://testserver{tab_path}",
    )

    assert json.loads(response["HX-Location"])["path"] == tab_path


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
    assert "to remove learners from it." in " ".join(response.content.decode().split())
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
def test_the_add_to_cohort_dialog_asks_before_a_cohort_is_chosen(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = _ada(organisation)
    CohortFactory(organisation=organisation)

    document = _picker_dialog(staff_client, _add_to_cohort_url(organisation, learner))

    assert _dialog_title(document) == "Add Ada Lovelace to a cohort?"


@pytest.mark.django_db
def test_the_add_to_cohort_dialog_names_the_chosen_cohort_and_keeps_it_selected(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = _ada(organisation)
    cohort = CohortFactory(organisation=organisation, name="Cohort A")

    document = _picker_dialog(
        staff_client, _add_to_cohort_url(organisation, learner) + f"?cohort={cohort.pk}"
    )

    assert _dialog_title(document) == "Add Ada Lovelace to Cohort A?"
    (selected,) = document.cssselect("select[name='cohort'] option[selected]")
    assert selected.get("value") == str(cohort.pk)


@pytest.mark.django_db
def test_choosing_a_cohort_in_the_add_to_cohort_dialog_re_renders_it(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = _ada(organisation)
    CohortFactory(organisation=organisation)
    url = _add_to_cohort_url(organisation, learner)

    document = _picker_dialog(staff_client, url)

    (select,) = document.cssselect("select[name='cohort']")
    assert select.get("hx-get") == url
    assert select.get("hx-trigger") == "change"
    assert select.get("hx-target") == "#app-modal-body"


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
    assert "to add learners to it." in " ".join(response.content.decode().split())
    assert not CohortMembership.objects.filter(cohort=cohort).exists()


# add a learner


def _add_learners_list_url(organisation: Organisation) -> str:
    return _interface_url(organisation.slug, "learners/__actions/add_learner")


def _add_learners_tab_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(organisation, cohort, "/__tabs/learners/__actions/add_learner")


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
        if "__actions/add_learner" in (button.get("hx-get") or "")
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
def test_add_learner_post_without_an_email_answers_422(staff_client: Client):
    organisation = OrganisationFactory()

    response = _post(staff_client, _add_learners_list_url(organisation), {"email": ""})

    assert response.status_code == 422


@pytest.mark.django_db
def test_add_learner_post_with_an_invalid_address_answers_422_and_adds_nobody(
    staff_client: Client,
):
    organisation = OrganisationFactory()

    response = _post(
        staff_client, _add_learners_list_url(organisation), {"email": "bad-address"}
    )

    assert response.status_code == 422
    assert not Learner.objects.filter(organisation=organisation).exists()


@pytest.mark.django_db
def test_add_learner_post_answers_200_with_the_outcome_and_add_another(
    staff_client: Client,
):
    organisation = OrganisationFactory()

    response = _post(
        staff_client,
        _add_learners_list_url(organisation),
        {"email": "new@example.com", "first_name": "Nia", "last_name": "Okoye"},
    )

    assert response.status_code == 200
    document = lxml.html.fromstring(response.content.decode())
    (result,) = document.cssselect("[data-testid='add-learner-result']")
    assert "new@example.com" in result.text_content()
    assert "Account created and setup email sent." in result.text_content()
    assert "Learner added" in document.cssselect("h2")[0].text_content()
    (again,) = [
        button
        for button in document.cssselect("button[hx-get]")
        if button.text_content().strip() == "Add another"
    ]
    assert again.get("hx-get") == _add_learners_list_url(organisation)
    assert Learner.objects.filter(
        organisation=organisation,
        user__email="new@example.com",
        user__first_name="Nia",
    ).exists()


@pytest.mark.django_db
def test_add_learner_post_for_an_existing_learner_is_titled_not_added(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    LearnerFactory(organisation=organisation, user__email="here@example.com")

    response = _post(
        staff_client,
        _add_learners_list_url(organisation),
        {"email": "here@example.com"},
    )

    document = lxml.html.fromstring(response.content.decode())
    assert document.cssselect("h2")[0].text_content().strip() == "Not added"
    assert "Already a learner here." in response.content.decode()


@pytest.mark.django_db
def test_add_and_add_another_returns_an_empty_form_with_the_outcome_above_it(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, name="Wave One"))

    response = _post(
        staff_client,
        _add_learners_list_url(organisation),
        {"email": "new@example.com", "cohort": str(cohort.pk), "action": "add_another"},
    )

    assert response.status_code == 200
    document = lxml.html.fromstring(response.content.decode())
    (status,) = document.cssselect("[data-status-message]")
    assert " ".join(status.text_content().split()) == (
        "new@example.com: Account created and setup email sent. Added to the cohort."
    )
    (email,) = document.cssselect("input[name=email]")
    assert not email.get("value")
    assert document.cssselect("form[hx-post]")


@pytest.mark.django_db
def test_add_learner_post_sends_the_learner_changed_trigger(staff_client: Client):
    organisation = OrganisationFactory()

    response = _post(
        staff_client,
        _add_learners_list_url(organisation),
        {"email": "new@example.com"},
    )

    assert LEARNER_CHANGED in json.loads(response["HX-Trigger"])


@pytest.mark.django_db
def test_add_learner_post_with_a_cohort_sends_the_cohort_changed_trigger_and_adds_them(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = _post(
        staff_client,
        _add_learners_list_url(organisation),
        {"email": "new@example.com", "cohort": str(cohort.pk)},
    )

    assert COHORT_CHANGED in json.loads(response["HX-Trigger"])
    assert cohort.cohortmembership_set.count() == 1


@pytest.mark.django_db
def test_add_learner_post_on_a_cohort_tab_adds_to_that_cohort(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = _post(
        staff_client,
        _add_learners_tab_url(organisation, cohort),
        {"email": "new@example.com"},
    )

    assert response.status_code == 200
    assert cohort.cohortmembership_set.count() == 1


@pytest.mark.django_db
def test_the_cohort_tab_title_names_the_cohort(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, name="Wave One"))

    fragment = _get_fragment(staff_client, _add_learners_tab_url(organisation, cohort))

    assert "Add a learner to Wave One" in fragment


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
        "add_learner"
    ]


@pytest.mark.django_db
def test_an_inactive_cohorts_tab_offers_no_add_learners(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))

    html = staff_client.get(
        _cohort_url(organisation, cohort, "/__tabs/learners")
    ).content.decode()

    assert "__actions/add_learner" not in html


@pytest.mark.django_db
def test_a_stale_add_learners_post_on_an_inactive_cohort_answers_422_and_adds_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))

    response = _post(
        staff_client,
        _add_learners_tab_url(organisation, cohort),
        {"email": "new@example.com"},
    )

    assert response.status_code == 422
    assert "to add learners to it." in " ".join(response.content.decode().split())
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
def test_a_pending_learners_settings_tab_offers_resend_setup_email(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)

    triggers = _settings_triggers(staff_client, organisation, learner)

    assert _resend_url(organisation, learner) in triggers


@pytest.mark.django_db
def test_a_learner_who_has_set_up_their_account_is_offered_no_resend(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)

    triggers = _settings_triggers(staff_client, organisation, learner)

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
    assert "to move learners into or out of it." in " ".join(
        response.content.decode().split()
    )
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
    assert "to move learners into or out of it." in " ".join(
        response.content.decode().split()
    )
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
    ) == (422, 0, True)


@pytest.mark.django_db
def test_the_move_refusal_for_a_departed_member_is_a_message_dialog_with_close(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    name = learner.user.display_name
    CohortMembership.objects.filter(learner=learner, cohort=source).delete()
    CohortFactory(organisation=organisation)

    response = staff_client.get(
        _move_url_from_learner(organisation, learner, source), HTTP_HX_REQUEST="true"
    )

    document = lxml.html.fromstring(response.content.decode())
    assert response.status_code == 422
    assert document.cssselect("#app-modal-title")[0].text_content().strip() == (
        f"{name} is no longer in {source}"
    )
    assert f"{name} is no longer a member of {source}" in " ".join(
        document.text_content().split()
    )
    assert [b.text_content().strip() for b in document.cssselect("footer button")] == [
        "Close"
    ]


@pytest.mark.django_db
def test_the_disabled_move_states_its_reason_and_names_it_with_aria_describedby(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    CohortFactory(organisation=organisation)

    response = staff_client.get(
        _move_url_from_learner(organisation, learner, source), HTTP_HX_REQUEST="true"
    )

    document = lxml.html.fromstring(response.content.decode())
    (move,) = document.cssselect("form button[type='submit']")
    (reason,) = document.cssselect(
        "form > div[data-modal-scroll] #move-disabled-reason"
    )
    assert not document.cssselect("footer #move-disabled-reason")
    assert move.get("disabled") is not None
    assert move.get("aria-describedby") == "move-disabled-reason"
    assert reason.text_content().strip() == "Choose a cohort to move them to."


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


# register and deactivate a learner registration individually


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


def _ada(organisation: Organisation) -> Learner:
    return cast(
        Learner,
        LearnerFactory(
            organisation=organisation,
            user__first_name="Ada",
            user__last_name="Lovelace",
        ),
    )


@pytest.mark.django_db
def test_the_register_dialog_asks_before_a_course_is_chosen(staff_client: Client):
    organisation = OrganisationFactory()
    learner = _ada(organisation)
    CourseFactory()

    document = _picker_dialog(
        staff_client, _learner_register_url(organisation, learner)
    )

    assert _dialog_title(document) == "Register Ada Lovelace for a course?"


@pytest.mark.django_db
def test_the_register_dialog_names_the_chosen_course_and_keeps_it_selected(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = _ada(organisation)
    course = CourseFactory(title="Course Other")

    document = _picker_dialog(
        staff_client,
        _learner_register_url(organisation, learner) + f"?course={course.pk}",
    )

    assert _dialog_title(document) == "Register Ada Lovelace for Course Other?"
    (selected,) = document.cssselect("select[name='course'] option[selected]")
    assert selected.get("value") == str(course.pk)


@pytest.mark.django_db
def test_choosing_a_course_in_the_register_dialog_re_renders_it(staff_client: Client):
    organisation = OrganisationFactory()
    learner = _ada(organisation)
    CourseFactory()
    url = _learner_register_url(organisation, learner)

    document = _picker_dialog(staff_client, url)

    (select,) = document.cssselect("select[name='course']")
    assert select.get("hx-get") == url
    assert select.get("hx-trigger") == "change"
    assert select.get("hx-target") == "#app-modal-body"


@pytest.mark.django_db
def test_a_course_the_register_dialog_does_not_offer_leaves_the_question_open(
    staff_client: Client,
):
    """A stale choice on the refresh is not a submission, so the dialog
    neither names it nor shows an error."""
    organisation = OrganisationFactory()
    learner = _ada(organisation)
    CourseFactory()
    held = LearnerCourseRegistrationFactory(learner=learner, is_active=True).course

    document = _picker_dialog(
        staff_client,
        _learner_register_url(organisation, learner) + f"?course={held.pk}",
    )

    assert _dialog_title(document) == "Register Ada Lovelace for a course?"
    assert document.cssselect("[role='alert']") == []
    assert document.cssselect("option[selected]:not([value=''])") == []


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
@pytest.mark.parametrize(
    ("row", "reactivated"),
    [("no_owner", True), ("owned", True), ("shared", True), ("held", False)],
)
def test_reregister_post_reactivates_only_a_course_available_to_the_organisation(
    staff_client: Client, row: str, reactivated: bool
):
    organisation = OrganisationFactory()
    courses = course_per_reach_row(organisation)
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(
        learner=learner, course=courses[row], is_active=False
    )

    response = _post(
        staff_client,
        _learner_reregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    assert (response.status_code, registration.is_active) == (
        204 if reactivated else 422,
        reactivated,
    )
    assert (COURSE_NOT_OPEN_MESSAGE in response.content.decode()) is not reactivated


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
        {"email": "new@example.com"},
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
    user = _staff_member_holding("cohort_admin", _cohort(organisation))
    return _remove_role_url(organisation), {
        "user": str(user.pk),
        "role": "cohort_admin",
    }


def _reason_suspend_member(organisation: Organisation) -> _DialogRequest:
    user = _staff_member_holding("cohort_viewer", _cohort(organisation))
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


def _scoped_request(user: User, organisation: Organisation) -> HttpRequest:
    """A request as `scope_request` leaves it: the user and the organisation
    the table's rows belong to."""
    request = cast(OrganisationScopedRequest, RequestFactory().post("/"))
    request.user = user
    request.organisation = organisation
    return request


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


def _deactivate_dialog(staff_client: Client, count: int = 2) -> lxml.html.HtmlElement:
    organisation = OrganisationFactory()
    learners = [_bulk_learner(organisation=organisation) for _ in range(count)]
    response = _bulk_post(staff_client, organisation, "deactivate", learners)
    return lxml.html.fromstring(response.content.decode())


@pytest.mark.django_db
def test_a_stale_cohort_in_a_bulk_picker_answers_422_without_the_id(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learners = [_bulk_learner(organisation=organisation)]
    stale = str(uuid.uuid4())

    response = _bulk_post(
        staff_client,
        organisation,
        "add_to_cohort",
        learners,
        cohort=stale,
        confirmed="on",
        expected_count="1",
    )

    assert response.status_code == 422
    assert "Choose a cohort from the list." in _bulk_text(response)
    assert stale not in response.content.decode()


@pytest.mark.django_db
def test_a_stale_course_in_a_bulk_picker_answers_422_without_the_id(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learners = [_bulk_learner(organisation=organisation)]
    stale = str(uuid.uuid4())

    response = _bulk_post(
        staff_client,
        organisation,
        "register_for_course",
        learners,
        course=stale,
        confirmed="on",
        expected_count="1",
    )

    assert response.status_code == 422
    assert "Choose a course from the list." in _bulk_text(response)
    assert stale not in response.content.decode()


@pytest.mark.django_db
def test_a_stale_cohort_in_the_add_to_cohort_picker_answers_422_without_the_id(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    stale = str(uuid.uuid4())

    response = _post(
        staff_client, _add_to_cohort_url(organisation, learner), {"cohort": stale}
    )

    assert response.status_code == 422
    assert "Choose a cohort from the list." in _bulk_text(response)
    assert stale not in response.content.decode()


@pytest.mark.django_db
def test_a_stale_learner_in_the_learner_picker_answers_422_without_the_id(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    stale = str(uuid.uuid4())

    response = staff_client.post(
        _add_learners_url(organisation, cohort),
        {"learners": [stale]},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    assert "Choose a learner from the list." in _bulk_text(response)
    assert stale not in response.content.decode()


@pytest.mark.django_db
def test_a_stale_destination_in_the_move_picker_answers_422_without_the_id(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    CohortFactory(organisation=organisation)
    stale = str(uuid.uuid4())

    response = _post(
        staff_client,
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": stale},
    )

    assert response.status_code == 422
    assert "Choose a cohort from the list." in _bulk_text(response)
    assert stale not in response.content.decode()


@pytest.mark.django_db
def test_bulk_deactivate_dialog_title_is_a_question_with_the_count(
    staff_client: Client,
):
    document = _deactivate_dialog(staff_client, count=2)

    (title,) = document.cssselect("#app-modal-title")
    assert title.text_content().strip() == "Deactivate 2 learners?"


@pytest.mark.django_db
def test_a_bulk_dialog_title_counts_the_rows_that_will_change(staff_client: Client):
    """The sentence counts the rows the action will change; the title used to
    count the whole selection, so the two disagreed on a mixed selection."""
    organisation = OrganisationFactory()
    active = _bulk_learner(organisation=organisation)
    inactive = _bulk_learner(organisation=organisation, is_active=False)

    response = _bulk_post(staff_client, organisation, "reactivate", [active, inactive])

    document = lxml.html.fromstring(response.content.decode())
    (title,) = document.cssselect("#app-modal-title")
    assert title.text_content().strip() == "Reactivate 1 learner?"
    assert "Reactivate 1 learner." in _bulk_text(response)


@pytest.mark.django_db
def test_a_bulk_dialog_title_says_zero_when_nothing_will_change(staff_client: Client):
    organisation = OrganisationFactory()
    active = _bulk_learner(organisation=organisation)

    response = _bulk_post(staff_client, organisation, "reactivate", [active])

    document = lxml.html.fromstring(response.content.decode())
    (title,) = document.cssselect("#app-modal-title")
    assert title.text_content().strip() == "Reactivate 0 learners?"
    assert document.cssselect("button[type='submit'][disabled]")


@pytest.mark.django_db
def test_bulk_deactivate_confirm_button_is_primary_and_names_the_work_in_flight(
    staff_client: Client,
):
    document = _deactivate_dialog(staff_client)

    (confirm,) = document.cssselect("form button[type=submit]")
    assert confirm.get("data-variant") == "primary"
    assert "Deactivating\u2026" in confirm.text_content()


@pytest.mark.django_db
def test_bulk_deactivate_cancel_is_focused(staff_client: Client):
    document = _deactivate_dialog(staff_client)

    cancel = [
        button
        for button in document.cssselect("button")
        if button.text_content().strip() == "Cancel"
    ]
    assert cancel[0].get("autofocus") is not None


@pytest.mark.django_db
def test_bulk_deactivate_trigger_in_the_selection_bar_is_a_ghost_button(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    _bulk_learner(organisation=organisation)

    response = staff_client.get(_interface_url(organisation.slug, "learners"))

    document = lxml.html.fromstring(response.content.decode())
    triggers = [
        element
        for element in document.cssselect("[data-variant][formaction]")
        if (element.get("formaction") or "")
        .split("?")[0]
        .endswith("/__actions/deactivate")
    ]
    assert triggers
    assert {trigger.get("data-variant") for trigger in triggers} == {"ghost"}


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
def test_bulk_confirm_with_every_learner_skipped_names_why_it_is_disabled(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    inactive = [
        _bulk_learner(organisation=organisation, is_active=False) for _ in range(2)
    ]

    response = _bulk_post(staff_client, organisation, "deactivate", inactive)

    document = lxml.html.fromstring(response.content.decode())
    [reason] = document.cssselect("[data-modal-scroll] #bulk-confirm-reason")
    assert not document.cssselect("footer #bulk-confirm-reason")
    assert (
        " ".join(reason.text_content().split())
        == "Nothing to change: all 2 selected learners will be skipped."
    )
    [button] = document.cssselect("button[type='submit']")
    assert button.get("disabled") is not None
    assert button.get("aria-describedby") == "bulk-confirm-reason"


@pytest.mark.django_db
def test_bulk_confirm_with_the_one_learner_skipped_names_why_it_is_disabled(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    inactive = _bulk_learner(organisation=organisation, is_active=False)

    response = _bulk_post(staff_client, organisation, "deactivate", [inactive])

    assert "Nothing to change: the 1 selected learner will be skipped." in _bulk_text(
        response
    )


@pytest.mark.django_db
def test_bulk_confirm_with_a_learner_to_change_gives_no_disabled_reason(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    active = _bulk_learner(organisation=organisation)
    inactive = _bulk_learner(organisation=organisation, is_active=False)

    response = _bulk_post(staff_client, organisation, "deactivate", [active, inactive])

    document = lxml.html.fromstring(response.content.decode())
    assert not document.cssselect("#bulk-confirm-reason")
    [button] = document.cssselect("button[type='submit']")
    assert button.get("disabled") is None


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
    inactive_staff_member = _bulk_learner(organisation=organisation, is_active=False)
    for learner in (member, inactive_staff_member):
        CohortMembershipFactory(cohort=cohort, learner=learner)
    educator = UserFactory(staff=True)
    assign_object_role(educator, cohort, cohort_learner_manager_role)
    action = DeactivateLearnersBulkAction()

    outcomes = action.classify_all(
        _scoped_request(educator, organisation),
        Learner.objects.filter(
            pk__in=[member.pk, outsider.pk, inactive_staff_member.pk]
        ),
        {},
    )

    assert outcomes == {
        str(member.pk): BulkOutcome("changed"),
        str(outsider.pk): BulkOutcome(
            "skipped", "learners you don't have permission to change"
        ),
        str(inactive_staff_member.pk): BulkOutcome("skipped", "already inactive"),
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
    assert "learners/__actions/deactivate?" not in request.content.decode()
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
    assert result.counts == [
        BulkCount("skipped", "learners you don't have permission to change", 1)
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
def test_refresh_without_a_cohort_answers_200_with_confirm_disabled(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = _bulk_learner(organisation=organisation)

    response = _bulk_cohort_post(
        staff_client, organisation, "add_to_cohort", [learner], refresh="1"
    )

    document = lxml.html.fromstring(response.content.decode())
    assert response.status_code == 200
    assert document.cssselect("button[disabled]")


def _disabled_confirm_reason(response) -> str:
    document = lxml.html.fromstring(response.content.decode())
    [reason] = document.cssselect("#bulk-confirm-reason")
    [confirm_form] = [
        form
        for form in document.cssselect("form")
        if form.cssselect("input[name='confirmed']")
    ]
    [button] = confirm_form.cssselect("button[type='submit']")
    assert button.get("disabled") is not None
    assert button.get("aria-describedby") == "bulk-confirm-reason"
    return " ".join(reason.text_content().split())


@pytest.mark.django_db
def test_a_bulk_picker_with_no_cohort_chosen_says_to_choose_one(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = _bulk_learner(organisation=organisation)

    response = _bulk_cohort_post(staff_client, organisation, "add_to_cohort", [learner])

    assert response.status_code == 200
    assert _disabled_confirm_reason(response) == "Choose a cohort first."


@pytest.mark.django_db
def test_a_bulk_picker_refreshed_without_a_cohort_says_to_choose_one(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = _bulk_learner(organisation=organisation)

    response = _bulk_cohort_post(
        staff_client, organisation, "add_to_cohort", [learner], refresh="1"
    )

    assert response.status_code == 200
    assert _disabled_confirm_reason(response) == "Choose a cohort first."


@pytest.mark.django_db
def test_a_bulk_picker_with_no_course_chosen_says_to_choose_one(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = _bulk_learner(organisation=organisation)

    response = _bulk_post(staff_client, organisation, "register_for_course", [learner])

    assert _disabled_confirm_reason(response) == "Choose a course first."


@pytest.mark.django_db
def test_a_bulk_picker_with_a_cohort_chosen_gives_no_disabled_reason(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    learner = _bulk_learner(organisation=organisation)

    response = _bulk_cohort_post(
        staff_client,
        organisation,
        "add_to_cohort",
        [learner],
        refresh="1",
        cohort=str(cohort.pk),
    )

    document = lxml.html.fromstring(response.content.decode())
    assert not document.cssselect("#bulk-confirm-reason")


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
        site=organisation.site,
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

    with django_assert_num_queries(6):
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
def test_bulk_register_refreshed_without_a_course_answers_200(staff_client: Client):
    organisation = OrganisationFactory()
    learner = _bulk_learner(organisation=organisation)

    response = _bulk_post(
        staff_client, organisation, "register_for_course", [learner], refresh="1"
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_bulk_register_dialog_before_a_course_is_chosen_is_titled_by_its_label(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = _bulk_learner(organisation=organisation)

    response = _bulk_post(staff_client, organisation, "register_for_course", [learner])

    document = lxml.html.fromstring(response.content.decode())
    (title,) = document.cssselect("#app-modal-title")
    assert title.text_content().strip() == "Register for a course?"


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
    without_registration = _bulk_learner(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=keeps)
    for learner in (keeps, loses):
        LearnerCourseRegistrationFactory(learner=learner, course=course)

    response = _bulk_post(
        staff_client,
        organisation,
        "deactivate_registration",
        [keeps, loses, without_registration],
        refresh="1",
        course=str(course.pk),
    )

    text = _bulk_text(response)
    assert "Deactivate the Algebra registration for 2 learners." in text
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
        wording = DeactivateRegistrationBulkAction().confirmation_wording(
            RequestFactory().post("/"),
            Learner.objects.filter(pk__in=[learner.pk for learner in learners]),
            classified,
            {"course": course, "course_label": "Algebra"},
        )

    assert wording.sentence == "Deactivate the Algebra registration for 4 learners."
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
        "deactivate_registration",
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
    assert "1 learner is already set up and will be skipped." in text


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

    assert "2 learners are already set up and will be skipped." in _bulk_text(response)


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
    [(1, "1 learner already set up."), (2, "2 learners already set up.")],
)
def test_bulk_resend_result_counts_the_learners_already_set_up(
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
    assert "1 is inactive and will be skipped." in text


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
def test_bulk_cohort_register_refreshed_without_a_course_answers_200(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _bulk_cohort(organisation)

    response = _cohorts_bulk_post(
        staff_client, organisation, "register", [cohort], refresh="1"
    )

    assert response.status_code == 200


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
def test_an_inactive_cohort_the_educator_cannot_change_is_skipped_for_permission_first(
    mock_site_context: Site,
):
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

    assert result.counts == [BulkCount("skipped", "inactive", 1)]
    assert result.entries == []


@pytest.mark.django_db
def test_bulk_cohort_unregister_confirmation_counts_changes_and_skips(
    staff_client: Client,
):
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
def test_posting_to_the_import_link_is_not_allowed(mock_site_context, logged_in_client):
    """The import action is a link to the import page; it has no submit."""
    organisation = OrganisationFactory()
    educator = _organisation_admin_on(organisation)

    response = _post(
        logged_in_client(educator),
        _interface_url(organisation.slug, "learners/__actions/import_learners"),
    )

    assert response.status_code == 405


def _plain_post(client: Client, path: str, **extra: str):
    return client.post(path, {"keys": ["1"], **extra})


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path_template",
    ["learners/__actions/unregister_from_course", "cohorts/__actions/unregister"],
)
def test_a_retired_bulk_action_slug_answers_the_unavailable_dialog_for_htmx(
    staff_client: Client, path_template: str
):
    organisation = OrganisationFactory()

    response = staff_client.post(
        _interface_url(organisation.slug, path_template),
        {"keys": ["1"]},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 404
    assert "This is no longer available" in _bulk_text(response)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path_template",
    ["learners/__actions/unregister_from_course", "cohorts/__actions/unregister"],
)
def test_a_retired_bulk_action_slug_answers_404_for_a_plain_request(
    staff_client: Client, path_template: str
):
    organisation = OrganisationFactory()

    response = _plain_post(
        staff_client, _interface_url(organisation.slug, path_template)
    )

    assert response.status_code == 404


_BULK_ACTION_WEIGHTS: dict[str, tuple[str, str, str]] = {
    "AddToCohortBulkAction": ("secondary", "primary", "Adding…"),
    "RemoveFromCohortBulkAction": ("error", "error", "Removing…"),
    "DeactivateLearnersBulkAction": ("secondary", "primary", "Deactivating…"),
    "ReactivateLearnersBulkAction": ("secondary", "primary", "Reactivating…"),
    "RegisterForCourseBulkAction": ("secondary", "primary", "Registering…"),
    "DeactivateRegistrationBulkAction": (
        "secondary",
        "primary",
        "Deactivating…",
    ),
    "ResendSetupEmailBulkAction": ("secondary", "primary", "Sending…"),
    "RegisterCohortForCourseBulkAction": ("secondary", "primary", "Registering…"),
    "DeactivateCohortRegistrationBulkAction": (
        "secondary",
        "primary",
        "Deactivating…",
    ),
    "DeactivateCohortsBulkAction": ("secondary", "primary", "Deactivating…"),
    "ReactivateCohortsBulkAction": ("secondary", "primary", "Reactivating…"),
}


def test_every_bulk_action_has_an_expected_weight_and_loading_text():
    registered = {cls.__name__ for cls in BULK_ACTIONS.values()}

    assert registered == set(_BULK_ACTION_WEIGHTS)


@pytest.mark.parametrize("class_name", sorted(_BULK_ACTION_WEIGHTS))
def test_bulk_action_trigger_confirm_variant_and_loading_text(class_name: str):
    (action_class,) = [
        cls for cls in BULK_ACTIONS.values() if cls.__name__ == class_name
    ]

    assert (
        action_class.variant,
        action_class.confirm_variant,
        action_class.loading_text,
    ) == _BULK_ACTION_WEIGHTS[class_name]


@pytest.mark.parametrize("count", [1, 12])
@pytest.mark.parametrize("class_name", sorted(_BULK_ACTION_WEIGHTS))
def test_bulk_action_confirmation_title_is_a_question_naming_the_count(
    class_name: str, count: int
):
    (action_class,) = [
        cls for cls in BULK_ACTIONS.values() if cls.__name__ == class_name
    ]
    cleaned_data: dict[str, object] = {
        "cohort": Cohort(name="Cohort A"),
        "course": Course(title="Algebra"),
        "course_label": "Algebra",
    }

    title = action_class().confirmation_title(count, cleaned_data)

    assert title.endswith("?")
    assert str(count) in title


def _single_row_dialog_url(name: str, organisation: Organisation) -> str:
    """The URL of the confirmation dialog `name`, over records made for it."""
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    CohortMembershipFactory(cohort=cohort, learner=learner)
    if name == "deactivate_cohort":
        return _cohort_url(organisation, cohort, "/__actions/deactivate")
    if name == "reactivate_cohort":
        return _cohort_url(organisation, cohort, "/__actions/reactivate")
    if name == "delete_cohort":
        empty = cast(Cohort, CohortFactory(organisation=organisation))
        return _cohort_url(
            organisation, empty, "/__tabs/settings/__panels/status/__actions/delete"
        )
    if name == "deactivate_learner":
        return _learner_state_url(organisation, learner, "deactivate")
    if name == "reactivate_learner":
        return _learner_state_url(organisation, learner, "reactivate")
    if name == "resend_setup_email":
        return _resend_url(organisation, _pending_learner(organisation))
    if name == "remove_from_cohort":
        return _remove_url_from_cohort(organisation, cohort, learner)
    if name == "move":
        destination = CohortFactory(organisation=organisation)
        return (
            _move_url_from_cohort(organisation, cohort, learner)
            + f"&destination={destination.pk}"
        )
    if name == "deactivate_registration":
        LearnerCourseRegistrationFactory(learner=learner, is_active=True)
        return _learner_unregister_url(organisation, learner) + (
            f"?registration={learner.learnercourseregistration_set.get().pk}"
        )
    if name == "reactivate_registration":
        registration = LearnerCourseRegistrationFactory(
            learner=learner, is_active=False
        )
        return (
            _learner_reregister_url(organisation, learner)
            + f"?registration={registration.pk}"
        )
    if name == "deactivate_cohort_registration":
        registration = CohortCourseRegistrationFactory(cohort=cohort)
        return _unregister_url(organisation, cohort, registration)
    member = _staff_member_holding("cohort_viewer", cohort)
    if name == "deactivate_member":
        return f"{_state_url(organisation, 'deactivate')}?user={member.pk}"
    if name == "reactivate_member":
        StaffMember.objects.filter(user=member).update(is_active=False)
        return f"{_state_url(organisation, 'reactivate')}?user={member.pk}"
    return f"{_remove_role_url(organisation)}?user={member.pk}&role=cohort_viewer"


_SINGLE_ROW_DIALOG_WEIGHTS: dict[str, tuple[str, str]] = {
    "deactivate_cohort": ("primary", "Deactivating…"),
    "reactivate_cohort": ("primary", "Reactivating…"),
    "delete_cohort": ("error", "Deleting…"),
    "deactivate_learner": ("primary", "Deactivating…"),
    "reactivate_learner": ("primary", "Reactivating…"),
    "resend_setup_email": ("primary", "Sending…"),
    "remove_from_cohort": ("error", "Removing…"),
    "move": ("primary", "Moving…"),
    "deactivate_registration": ("primary", "Deactivating…"),
    "reactivate_registration": ("primary", "Reactivating…"),
    "deactivate_cohort_registration": ("primary", "Deactivating…"),
    "deactivate_member": ("primary", "Deactivating…"),
    "reactivate_member": ("primary", "Reactivating…"),
    "deactivate_role": ("primary", "Deactivating…"),
}


def _single_row_dialog(
    client: Client, name: str, organisation: Organisation
) -> lxml.html.HtmlElement:
    url = _single_row_dialog_url(name, organisation)
    response = client.get(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    return lxml.html.fromstring(response.content.decode())


@pytest.mark.django_db
@pytest.mark.parametrize("name", sorted(_SINGLE_ROW_DIALOG_WEIGHTS))
def test_single_row_dialog_title_is_a_question(
    name: str, staff_client: Client, organisation: Organisation
):
    """A confirmation asks; the move dialog, which is a form, names the
    action and the learner and states the current cohort in its body."""
    document = _single_row_dialog(staff_client, name, organisation)

    (title,) = document.cssselect("#app-modal-title")
    text = title.text_content().strip()
    if name == "move":
        assert text.startswith("Move ")
        assert "?" not in text
        assert "Current cohort:" in document.text_content()
    else:
        assert text.endswith("?")


@pytest.mark.django_db
@pytest.mark.parametrize("name", sorted(_SINGLE_ROW_DIALOG_WEIGHTS))
def test_single_row_dialog_focuses_cancel_or_the_move_destination(
    name: str, staff_client: Client, organisation: Organisation
):
    document = _single_row_dialog(staff_client, name, organisation)

    focused = [
        element.tag if element.tag == "select" else element.text_content().strip()
        for element in document.cssselect("[autofocus]")
    ]
    assert focused == (["select"] if name == "move" else ["Cancel"])


@pytest.mark.django_db
@pytest.mark.parametrize("name", sorted(_SINGLE_ROW_DIALOG_WEIGHTS))
def test_single_row_dialog_confirm_button_weight_and_loading_text(
    name: str, staff_client: Client, organisation: Organisation
):
    document = _single_row_dialog(staff_client, name, organisation)

    (confirm,) = document.cssselect("button[type=submit]")
    variant, loading_text = _SINGLE_ROW_DIALOG_WEIGHTS[name]
    assert confirm.get("data-variant") == variant
    assert loading_text in confirm.text_content()


@pytest.mark.django_db
def test_a_row_action_on_a_learner_from_another_organisation_answers_the_dialog(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    elsewhere = _bulk_learner(organisation=OrganisationFactory())

    response = staff_client.get(
        _learner_state_url(organisation, elsewhere, "deactivate"),
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 404
    assert "This is no longer available" in _bulk_text(response)


@pytest.mark.django_db
def test_a_row_action_on_an_unknown_learner_answers_the_dialog(staff_client: Client):
    organisation = OrganisationFactory()

    response = staff_client.get(
        _interface_url(
            organisation.slug, f"learners/{uuid.uuid4()}/__actions/deactivate"
        ),
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 404
    assert "This is no longer available" in _bulk_text(response)


@pytest.mark.django_db
def test_a_bulk_action_that_does_not_exist_answers_the_dialog(staff_client: Client):
    organisation = OrganisationFactory()

    response = staff_client.post(
        _interface_url(organisation.slug, "learners/__actions/no_such_action"),
        {"keys": [str(uuid.uuid4())]},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 404
    assert "This is no longer available" in _bulk_text(response)


@pytest.mark.django_db
def test_an_inactive_cohort_refusal_is_a_message_dialog(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1, is_active=False)

    response = _post(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    _assert_message_dialog(
        response,
        f"{cohort} is already inactive",
        "Nothing changed. Someone else may have deactivated it already.",
    )


@pytest.mark.django_db
def test_an_already_active_cohort_refusal_is_a_message_dialog(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1)

    response = _post(
        staff_client, _cohort_url(organisation, cohort, "/__actions/reactivate")
    )

    _assert_message_dialog(
        response,
        f"{cohort} is already active",
        "Nothing changed. Someone else may have reactivated it already.",
    )


@pytest.mark.django_db
def test_an_already_changed_learner_refusal_is_a_message_dialog(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=True)

    response = _post(
        staff_client, _learner_state_url(organisation, learner, "reactivate")
    )

    _assert_message_dialog(
        response,
        f"{learner.user.display_name} was already changed",
        "Nothing changed. Someone else may have already used Reactivate on this "
        "learner.",
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_a_recently_sent_setup_email_refusal_is_a_message_dialog(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)
    with django_capture_on_commit_callbacks(execute=True):
        _post(staff_client, _resend_url(organisation, learner))

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(staff_client, _resend_url(organisation, learner))

    minutes = config.SETUP_EMAIL_RESEND_SECONDS // 60
    _assert_message_dialog(
        response,
        "Setup email sent recently",
        f"{learner.user.display_name} was sent a setup email recently. "
        f"Try again in {minutes} minutes.",
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_an_already_set_up_account_refusal_is_a_message_dialog(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(staff_client, _resend_url(organisation, learner))

    name = learner.user.display_name
    _assert_message_dialog(
        response,
        f"{name} has already set up their account",
        f"Nothing was sent. {name} has signed in or set a password since this "
        "page loaded.",
    )


# one lookup per request
#
# A dialog's hooks each ask for the same row, so the second ask must not go
# back to the database.


def _superuser_get_ctx(
    organisation: Organisation, instance: Cohort | None, data: dict[str, str]
) -> PanelContext:
    request = RequestFactory().get("/", data)
    request.user = UserFactory(superuser=True)
    request.organisation = organisation
    return PanelContext(
        request=request, instance=instance, base_url="/", name="", config=CohortConfig
    )


@pytest.mark.django_db
def test_the_add_learner_dialog_reads_its_preset_cohort_once(
    organisation: Organisation, django_assert_max_num_queries
):
    cohort = _cohort(organisation)
    action = AddLearnerAction()
    ctx = _superuser_get_ctx(organisation, None, {"cohort": str(cohort.pk)})
    action._preset_cohort(ctx)

    with django_assert_max_num_queries(0):
        preset = action._preset_cohort(ctx)

    assert preset == cohort


@pytest.mark.django_db
def test_a_membership_dialog_on_a_cohort_page_reads_its_learner_once(
    organisation: Organisation, django_assert_max_num_queries
):
    cohort = _cohort(organisation)
    learner = LearnerFactory(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    action = RemoveFromCohortAction()
    ctx = _superuser_get_ctx(organisation, cohort, {"learner": str(learner.pk)})
    action._pair(ctx)

    with django_assert_max_num_queries(0):
        pair = action._pair(ctx)

    assert pair == (learner, cohort)


REGISTERABLE_ROWS = [
    ("no_owner", True),
    ("owned", True),
    ("shared", True),
    ("held", False),
    ("unreached", False),
]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action",
    [RegisterForCourseBulkAction, RegisterCohortForCourseBulkAction],
)
@pytest.mark.parametrize(
    ("row", "outcome"),
    [
        ("no_owner", contextlib.nullcontext()),
        ("owned", contextlib.nullcontext()),
        ("shared", contextlib.nullcontext()),
        ("held", pytest.raises(Http404)),
        ("unreached", pytest.raises(Http404)),
    ],
)
def test_a_bulk_register_picker_resolves_a_course_only_when_it_is_registerable(
    mock_site_context: Site,
    action: type[RegisterForCourseBulkAction | RegisterCohortForCourseBulkAction],
    row: str,
    outcome: contextlib.AbstractContextManager[object],
):
    organisation = OrganisationFactory()
    courses = course_per_reach_row(organisation)

    with outcome:
        action().resolve_target(organisation, {"course": str(courses[row].pk)})


@pytest.mark.django_db
@pytest.mark.parametrize(("row", "registered"), REGISTERABLE_ROWS)
def test_registering_a_cohort_for_a_course_works_only_when_it_is_registerable(
    staff_client: Client, row: str, registered: bool
):
    organisation = OrganisationFactory()
    courses = course_per_reach_row(organisation)
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = _post(
        staff_client,
        _register_url(organisation, cohort),
        {"course": str(courses[row].pk)},
    )

    assert (
        response.status_code,
        CohortCourseRegistration.objects.filter(
            cohort=cohort, course=courses[row]
        ).exists(),
    ) == ((204 if registered else 422), registered)


@pytest.mark.django_db
@pytest.mark.parametrize(("row", "registered"), REGISTERABLE_ROWS)
def test_registering_a_learner_for_a_course_works_only_when_it_is_registerable(
    staff_client: Client, row: str, registered: bool
):
    organisation = OrganisationFactory()
    courses = course_per_reach_row(organisation)
    learner = cast(Learner, LearnerFactory(organisation=organisation))

    response = _post(
        staff_client,
        _learner_register_url(organisation, learner),
        {"course": str(courses[row].pk)},
    )

    assert (
        response.status_code,
        LearnerCourseRegistration.objects.filter(
            learner=learner, course=courses[row]
        ).exists(),
    ) == ((204 if registered else 422), registered)
