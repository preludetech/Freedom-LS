"""The educator interface's panel actions, driven through the interface URLs."""

from __future__ import annotations

import contextlib
import json
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.core import mail
from django.db import connection, transaction
from django.http import Http404
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from freedom_ls.accounts.config import config
from freedom_ls.accounts.factories import UserFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseAudience
from freedom_ls.educator_interface.actions import (
    RequiresActiveCohortMixin,
    cohort_not_empty_sentence,
)
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
)
from freedom_ls.educator_interface.panels.cohort.bulk_actions import (
    RegisterCohortForCourseBulkAction,
)
from freedom_ls.educator_interface.panels.learner.actions import (
    AddLearnerAction,
    RemoveFromCohortAction,
)
from freedom_ls.educator_interface.panels.learner.bulk_actions import (
    RegisterForCourseBulkAction,
)
from freedom_ls.educator_interface.tests.helpers import (
    _add_learners_list_url,
    _add_to_cohort_url,
    _assert_message_dialog,
    _bulk_confirm,
    _bulk_learner,
    _bulk_post,
    _bulk_text,
    _cohort,
    _cohort_admin_on,
    _cohort_url,
    _cohort_with_courses,
    _dialog_title,
    _edit_name_url,
    _empty_picker_text,
    _get_fragment,
    _interface_url,
    _learner_register_url,
    _learner_reregister_url,
    _learner_state_url,
    _learner_unregister_url,
    _learners_bulk_url,
    _membership,
    _move_url_from_learner,
    _named_learner,
    _offered_options,
    _organisation_admin_on,
    _pending_learner,
    _picker_dialog,
    _post,
    _registered_cohort,
    _remove_role_url,
    _remove_url_from_learner,
    _resend_url,
    _staff_member_holding,
    _state_url,
    _unregister_post_url,
    _unregister_url,
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
from freedom_ls.learner_management.role_assignment import (
    assign_role,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.bulk_actions import (
    BULK_ACTIONS,
)
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.models import BulkActionRun, RunStatus
from freedom_ls.tests.audit_assertions import assert_entry

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse


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


def _member(organisation: Organisation, cohort: Cohort, first_name: str = "Ada"):
    learner = LearnerFactory(
        organisation=organisation, user__first_name=first_name, user__last_name="Lee"
    )
    CohortMembershipFactory(cohort=cohort, learner=learner)
    return learner


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


# remove from a cohort


def _remove_url_from_cohort(
    organisation: Organisation, cohort: Cohort, learner: Learner | None = None
) -> str:
    url = _cohort_url(
        organisation, cohort, "/__tabs/learners/__actions/remove_from_cohort"
    )
    return f"{url}?learner={learner.pk}" if learner is not None else url


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


# add to a cohort


def _add_learners_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(
        organisation, cohort, "/__tabs/learners/__actions/add_existing_learners"
    )


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


def _add_learners_tab_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(organisation, cohort, "/__tabs/learners/__actions/add_learner")


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


# move between cohorts


def _move_url_from_cohort(
    organisation: Organisation, source: Cohort, learner: Learner
) -> str:
    url = _cohort_url(organisation, source, "/__tabs/learners/__actions/move")
    return f"{url}?learner={learner.pk}"


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


# empty pickers


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
        "freedom_ls.educator_interface.panels.learner.actions.record_learner_entry",
        fail,
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
) -> tuple[_MonkeyPatchedWSGIResponse, list[AuditLogEntry]]:
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
