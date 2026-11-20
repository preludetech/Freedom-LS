"""The audit log's actor and action filters."""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.educator_interface.panels.audit_log.filters import (
    AuditActionFilter,
    AuditActorFilter,
)

pytestmark = pytest.mark.usefixtures("_site_context")


def _entry_pks(request, filter_, values: list[str]) -> set:
    queryset = AuditLogEntry.objects.filter(organisation=request.organisation)
    return set(filter_.apply(request, queryset, values).values_list("pk", flat=True))


@pytest.mark.django_db
def test_actor_choices_are_system_then_this_organisations_actors_by_name(audit_request):
    request, organisation = audit_request
    zed = UserFactory(first_name="Zed", last_name="Last")
    ada = UserFactory(first_name="Ada", last_name="First")
    AuditLogEntryFactory(target=organisation, actor=zed)
    AuditLogEntryFactory(target=organisation, actor=ada)
    AuditLogEntryFactory(target=organisation, actor=ada)
    AuditLogEntryFactory(actor=UserFactory(first_name="Other"))

    choices = AuditActorFilter().get_choices(request)

    assert choices == [
        ("system", "System"),
        (str(ada.pk), "Ada First"),
        (str(zed.pk), "Zed Last"),
    ]


@pytest.mark.django_db
def test_an_actor_filter_value_outside_this_organisation_is_dropped(audit_request):
    request, organisation = audit_request
    ada = UserFactory()
    AuditLogEntryFactory(target=organisation, actor=ada)
    outsider = AuditLogEntryFactory(actor=UserFactory()).actor

    kept = AuditActorFilter().validate(
        [str(ada.pk), str(outsider.pk), "nonsense"], request
    )

    assert kept == [str(ada.pk)]


@pytest.mark.django_db
def test_the_actor_filter_selects_one_value_at_a_time():
    assert AuditActorFilter().toggled(["system"], "42") == ["42"]


@pytest.mark.django_db
def test_two_actor_values_in_the_query_string_keep_only_the_first(audit_request):
    request, organisation = audit_request
    ada = UserFactory()
    zed = UserFactory()
    AuditLogEntryFactory(target=organisation, actor=ada)
    AuditLogEntryFactory(target=organisation, actor=zed)

    kept = AuditActorFilter().validate([str(zed.pk), str(ada.pk)], request)

    assert kept == [str(zed.pk)]


@pytest.mark.django_db
def test_system_matches_entries_with_no_actor_and_no_stored_name(audit_request):
    request, organisation = audit_request
    ada = UserFactory()
    system = AuditLogEntryFactory(target=organisation, actor=None, actor_label="")
    AuditLogEntryFactory(target=organisation, actor=ada, actor_label="Ada")
    AuditLogEntryFactory(target=organisation, actor=None, actor_label="Deleted Dan")

    assert _entry_pks(request, AuditActorFilter(), ["system"]) == {system.pk}


@pytest.mark.django_db
def test_a_user_value_matches_only_that_actors_entries(audit_request):
    request, organisation = audit_request
    ada = UserFactory()
    mine = AuditLogEntryFactory(target=organisation, actor=ada)
    AuditLogEntryFactory(target=organisation, actor=UserFactory())
    AuditLogEntryFactory(target=organisation, actor=None)

    assert _entry_pks(request, AuditActorFilter(), [str(ada.pk)]) == {mine.pk}


@pytest.mark.django_db
def test_the_action_filter_narrows_by_code(audit_request):
    request, organisation = audit_request
    created = AuditLogEntryFactory(target=organisation, action="cohort.created")
    AuditLogEntryFactory(target=organisation, action="role.assigned")

    assert _entry_pks(request, AuditActionFilter(), ["cohort.created"]) == {created.pk}


@pytest.mark.django_db
def test_the_action_choices_are_the_registered_actions_with_labels(audit_request):
    request, _ = audit_request

    choices = dict(AuditActionFilter().get_choices(request))

    assert choices["cohort.created"] == "Cohort created"
    assert AuditActionFilter().validate(["cohort.created", "nope"], request) == [
        "cohort.created"
    ]


@pytest.mark.django_db
def test_the_action_choices_include_a_downstream_extra_action(audit_request, settings):
    request, _ = audit_request
    settings.AUDIT_LOG_EXTRA_ACTIONS = {"invoice.sent": "Invoice sent"}

    choices = dict(AuditActionFilter().get_choices(request))

    assert choices["invoice.sent"] == "Invoice sent"


@pytest.mark.django_db
def test_the_action_choices_are_grouped_under_the_fixed_headings_in_order(
    audit_request,
):
    request, _ = audit_request

    groups = AuditActionFilter().get_groups(request)

    assert [group for group, _ in groups] == [
        "Learners",
        "Cohort membership",
        "Course registrations",
        "Course progress",
        "Cohorts",
        "Staff and roles",
        "Other",
    ]
    assert dict(dict(groups)["Cohort membership"])["cohort_membership.moved"] == (
        "Learner moved between cohorts"
    )
    assert AuditActionFilter.widget == "grouped_checklist"
