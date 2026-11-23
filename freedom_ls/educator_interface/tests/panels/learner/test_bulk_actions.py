"""The learners table's bulk actions, driven through the interface URLs."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, cast

import lxml.html
import pytest
from pytest_mock import MockerFixture

from django.contrib.sites.models import Site
from django.core import mail
from django.http import Http404
from django.test import Client, RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.educator_interface.events import (
    LEARNER_CHANGED,
)
from freedom_ls.educator_interface.panels.learner.bulk_actions import (
    AddToCohortBulkAction,
    DeactivateLearnersBulkAction,
    DeactivateRegistrationBulkAction,
    RegisterForCourseBulkAction,
    RemoveFromCohortBulkAction,
)
from freedom_ls.educator_interface.tests.helpers import (
    _bulk_cohort_confirm,
    _bulk_confirm,
    _bulk_confirm_with,
    _bulk_learner,
    _bulk_pending_learner,
    _bulk_post,
    _bulk_text,
    _cohort_admin_on,
    _cohort_with_courses,
    _course_option_values,
    _interface_url,
    _learners_bulk_url,
    _scoped_request,
)
from freedom_ls.learner_management import queries as queries_module
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    CHANGE_LEARNER,
    VIEW_COHORT,
    VIEW_LEARNER,
)
from freedom_ls.learner_management.tests.scenario_world import custom_role_config
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.bulk_actions import (
    BulkCount,
    BulkOutcome,
    BulkResult,
    run_apply,
)
from freedom_ls.panel_framework.bulk_runs import (
    run_bulk_action,
)
from freedom_ls.panel_framework.models import BulkActionRun, RunStatus
from freedom_ls.role_based_permissions.types import SCOPE_OBJECT, Role
from freedom_ls.role_based_permissions.utils import assign_object_role

if TYPE_CHECKING:
    pass


# bulk learner state actions


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
    can = mocker.spy(queries_module, "can")
    organisation = OrganisationFactory()
    learners = [_bulk_learner(organisation=organisation) for _ in range(3)]
    _bulk_confirm(staff_client, organisation, "deactivate", learners)
    calls_for_three = can.call_count
    # The spy is on the path the run takes.
    assert calls_for_three > 0
    can.reset_mock()
    larger_organisation = OrganisationFactory()
    more_learners = [_bulk_learner(organisation=larger_organisation) for _ in range(8)]

    _bulk_confirm(staff_client, larger_organisation, "deactivate", more_learners)

    # The count is the same however many learners the run covers.
    assert can.call_count == calls_for_three


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


# bulk course registration and setup email actions


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
