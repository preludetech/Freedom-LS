"""The cohort list's own table filters."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
import time_machine

from django.http import HttpRequest, QueryDict
from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.educator_interface.filters import (
    AuditActionFilter,
    AuditActorFilter,
    LearnerCohortFilter,
    LearnerCourseFilter,
    LearnerStatusFilter,
    StaffRoleFilter,
    VisibleCourseFilter,
)
from freedom_ls.educator_interface.views import (
    AuditLogEntryTable,
    CohortDataTable,
    StaffDataTable,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort, Learner
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.panel_framework.filters import TableFilter, ToggleFilter
from freedom_ls.panel_framework.tables import TableQuery


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects."""


def _educator_request(site_aware_request: RequestFactory, organisation):
    educator = LearnerFactory(user__staff=True).user
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator, "organisation_admin", organisation)
    request = site_aware_request.get("/")
    request.user = educator
    request.organisation = organisation
    return request


def _any_request():
    """For a filter whose apply() reads nothing from the request."""
    return RequestFactory().get("/")


@pytest.mark.django_db
def test_visible_course_filter_offers_only_courses_visible_to_the_educator(
    site_aware_request,
):
    organisation = OrganisationFactory()
    published = CourseFactory(title="Published Course")
    CourseFactory(title="Hidden Course", visibility=CourseVisibility.HIDDEN)
    request = _educator_request(site_aware_request, organisation)

    choices = VisibleCourseFilter(
        "course", "Course", lookup="course_registrations__course"
    ).get_choices(request)

    assert choices == [(str(published.pk), "Published Course")]


@pytest.mark.django_db
def test_visible_course_filter_keeps_a_cohort_with_an_active_registration():
    course = CourseFactory()
    cohort = CohortFactory()
    CohortCourseRegistrationFactory(cohort=cohort, course=course, is_active=True)

    result = VisibleCourseFilter(
        "course", "Course", lookup="course_registrations__course"
    ).apply(_any_request(), Cohort.objects.all(), [str(course.pk)])

    assert list(result) == [cohort]


@pytest.mark.django_db
def test_visible_course_filter_drops_a_cohort_whose_registration_is_inactive():
    course = CourseFactory()
    CohortCourseRegistrationFactory(course=course, is_active=False)

    result = VisibleCourseFilter(
        "course", "Course", lookup="course_registrations__course"
    ).apply(_any_request(), Cohort.objects.all(), [str(course.pk)])

    assert list(result) == []


# the table hides inactive cohorts only while it offers the toggle


def _cohort_rows(table: type[CohortDataTable], request) -> list[Cohort]:
    query = TableQuery(key="cohorts")
    return list(table.filter_queryset(request, table.get_queryset(request), query))


@pytest.mark.django_db
def test_the_cohort_table_hides_inactive_cohorts_while_its_toggle_is_unset(
    site_aware_request: RequestFactory,
):
    organisation = OrganisationFactory()
    request = _educator_request(site_aware_request, organisation)
    active = CohortFactory(organisation=organisation)
    CohortFactory(organisation=organisation, is_active=False)

    assert _cohort_rows(CohortDataTable, request) == [active]


@pytest.mark.django_db
def test_a_cohort_table_without_the_toggle_keeps_inactive_cohorts(
    site_aware_request: RequestFactory,
):
    """Only the toggle narrows the table: another filter list, with
    nothing on the page to widen it again, must not hide rows."""
    organisation = OrganisationFactory()
    request = _educator_request(site_aware_request, organisation)
    active = CohortFactory(organisation=organisation, name="A")
    inactive = CohortFactory(organisation=organisation, name="B", is_active=False)

    class CourseOnlyCohortDataTable(CohortDataTable):
        @classmethod
        def get_filters(cls) -> list[TableFilter]:
            return [
                VisibleCourseFilter(
                    "course", "Course", lookup="course_registrations__course"
                )
            ]

    assert _cohort_rows(CourseOnlyCohortDataTable, request) == [active, inactive]


@pytest.mark.django_db
def test_the_toggle_is_read_under_whatever_key_the_table_declares_it(
    site_aware_request: RequestFactory,
):
    organisation = OrganisationFactory()
    request = _educator_request(site_aware_request, organisation)
    active = CohortFactory(organisation=organisation, name="A")
    inactive = CohortFactory(organisation=organisation, name="B", is_active=False)

    class RenamedToggleCohortDataTable(CohortDataTable):
        @classmethod
        def get_filters(cls) -> list[TableFilter]:
            return [ToggleFilter("all", "Show all")]

    unset = TableQuery(key="cohorts")
    on = TableQuery(key="cohorts", filters={"all": ["1"]})
    queryset = RenamedToggleCohortDataTable.get_queryset(request)

    assert list(
        RenamedToggleCohortDataTable.filter_queryset(request, queryset, unset)
    ) == [active]
    assert list(
        RenamedToggleCohortDataTable.filter_queryset(request, queryset, on)
    ) == [
        active,
        inactive,
    ]


def _status_learners() -> dict[str, Learner]:
    organisation = OrganisationFactory()
    active = cast(Learner, LearnerFactory(organisation=organisation))
    pending = cast(Learner, LearnerFactory(organisation=organisation))
    pending.user.set_unusable_password()
    pending.user.save(update_fields=["password"])
    inactive = cast(Learner, LearnerFactory(organisation=organisation, is_active=False))
    return {"active": active, "pending": pending, "inactive": inactive}


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["active", "pending", "inactive"])
def test_status_filter_narrows_to_each_status(status: str) -> None:
    learners = _status_learners()

    result = LearnerStatusFilter().apply(
        _any_request(), Learner.objects.all(), [status]
    )

    assert list(result) == [learners[status]]


@pytest.mark.django_db
def test_status_filter_with_two_statuses_returns_both() -> None:
    learners = _status_learners()

    result = LearnerStatusFilter().apply(
        _any_request(), Learner.objects.all(), ["active", "pending"]
    )

    assert set(result) == {learners["active"], learners["pending"]}


@pytest.mark.django_db
def test_status_filter_defaults_to_active_and_pending() -> None:
    assert LearnerStatusFilter().default == ("active", "pending")


def _cohort_filter() -> LearnerCohortFilter:
    return LearnerCohortFilter("cohort", "Cohort", lookup="")


@pytest.mark.django_db
def test_learner_cohort_filter_labels_an_inactive_cohort_as_inactive(
    site_aware_request,
):
    organisation = OrganisationFactory()
    active = CohortFactory(organisation=organisation, name="Alpha")
    inactive = CohortFactory(organisation=organisation, name="Beta", is_active=False)
    request = _educator_request(site_aware_request, organisation)

    choices = _cohort_filter().get_choices(request)

    assert choices == [
        (str(active.pk), "Alpha"),
        (str(inactive.pk), "Beta (inactive)"),
    ]


@pytest.mark.django_db
def test_learner_cohort_filter_narrows_to_members_of_the_chosen_cohort():
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    member = LearnerFactory(organisation=organisation)
    LearnerFactory(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=member)

    result = _cohort_filter().apply(
        _any_request(), Learner.objects.all(), [str(cohort.pk)]
    )

    assert list(result) == [member]


@pytest.mark.django_db
def test_learner_cohort_filter_drops_a_cohort_outside_the_organisation(
    site_aware_request,
):
    organisation = OrganisationFactory()
    outsider = CohortFactory(organisation=OrganisationFactory())
    request = _educator_request(site_aware_request, organisation)

    values = _cohort_filter().validate([str(outsider.pk)], request)

    assert values == []


def _course_filter() -> LearnerCourseFilter:
    return LearnerCourseFilter("course", "Course", lookup="")


@pytest.mark.django_db
def test_learner_course_filter_keeps_a_learner_registered_individually():
    course = CourseFactory()
    learner = LearnerFactory()
    LearnerFactory()
    LearnerCourseRegistrationFactory(learner=learner, course=course)

    result = _course_filter().apply(
        _any_request(), Learner.objects.all(), [str(course.pk)]
    )

    assert list(result) == [learner]


@pytest.mark.django_db
def test_learner_course_filter_keeps_a_member_of_an_active_cohort_registered():
    organisation = OrganisationFactory()
    course = CourseFactory()
    cohort = CohortFactory(organisation=organisation)
    CohortCourseRegistrationFactory(cohort=cohort, course=course, is_active=True)
    member = LearnerFactory(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=member)

    result = _course_filter().apply(
        _any_request(), Learner.objects.all(), [str(course.pk)]
    )

    assert list(result) == [member]


@pytest.mark.django_db
def test_learner_course_filter_drops_a_member_of_an_inactive_cohort_registered():
    organisation = OrganisationFactory()
    course = CourseFactory()
    cohort = CohortFactory(organisation=organisation, is_active=False)
    CohortCourseRegistrationFactory(cohort=cohort, course=course, is_active=True)
    CohortMembershipFactory(
        cohort=cohort, learner=LearnerFactory(organisation=organisation)
    )

    result = _course_filter().apply(
        _any_request(), Learner.objects.all(), [str(course.pk)]
    )

    assert list(result) == []


def _staff_member_pks(request, roles: list[str] | None = None) -> list:
    filters = {} if roles is None else {"role": roles}
    query = TableQuery(key="staff", filters=filters)
    return [
        user.pk
        for user in StaffDataTable.filter_queryset(
            request, StaffDataTable.get_queryset(request), query
        )
    ]


@pytest.fixture
def staff_request(site_aware_request: RequestFactory):
    organisation = OrganisationFactory()
    request = _educator_request(site_aware_request, organisation)
    return request, organisation


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role", ["organisation_admin", "cohort_admin", "cohort_viewer"]
)
def test_the_role_filter_narrows_members_to_each_role(staff_request, role):
    request, organisation = staff_request
    cohort = CohortFactory(organisation=organisation)
    grantor = UserFactory(superuser=True)
    holders = {}
    for held in ("organisation_admin", "cohort_admin", "cohort_viewer"):
        holders[held] = UserFactory()
        target = organisation if held == "organisation_admin" else cohort
        assign_role(grantor, holders[held], held, target)

    result = set(_staff_member_pks(request, [role]))

    assert result & {h.pk for h in holders.values()} == {holders[role].pk}


@pytest.mark.django_db
def test_a_member_holding_two_roles_is_returned_once(staff_request):
    request, organisation = staff_request
    cohort = CohortFactory(organisation=organisation)
    grantor = UserFactory(superuser=True)
    both = UserFactory()
    assign_role(grantor, both, "cohort_admin", cohort)
    assign_role(grantor, both, "cohort_viewer", cohort)

    result = _staff_member_pks(request, ["cohort_admin", "cohort_viewer"])

    assert result.count(both.pk) == 1


@pytest.mark.django_db
def test_all_roles_narrows_nothing(staff_request):
    request, organisation = staff_request
    cohort = CohortFactory(organisation=organisation)
    assign_role(UserFactory(superuser=True), UserFactory(), "cohort_viewer", cohort)

    assert len(_staff_member_pks(request, [StaffRoleFilter.ALL])) == len(
        _staff_member_pks(request)
    )
    assert len(_staff_member_pks(request)) == 2


@pytest.mark.django_db
def test_all_roles_beside_a_role_still_means_every_role(staff_request):
    request, organisation = staff_request
    cohort = CohortFactory(organisation=organisation)
    assign_role(UserFactory(superuser=True), UserFactory(), "cohort_viewer", cohort)

    result = _staff_member_pks(request, [StaffRoleFilter.ALL, "organisation_admin"])

    assert len(result) == 2


@pytest.mark.django_db
def test_the_role_filter_narrows_by_itself(staff_request):
    request, organisation = staff_request
    cohort = CohortFactory(organisation=organisation)
    grantor = UserFactory(superuser=True)
    admin = UserFactory()
    assign_role(grantor, admin, "cohort_admin", cohort)
    viewer = UserFactory()
    assign_role(grantor, viewer, "cohort_viewer", cohort)
    everyone = StaffDataTable.get_queryset(request)

    narrowed = StaffRoleFilter().apply(request, everyone, ["cohort_admin"])
    unchanged = StaffRoleFilter().apply(request, everyone, [StaffRoleFilter.ALL])

    assert set(narrowed) == {admin}
    assert set(unchanged) == set(everyone)


@pytest.mark.django_db
def test_the_role_filter_offers_no_choices_to_a_names_only_viewer(
    site_aware_request: RequestFactory,
):
    organisation = OrganisationFactory()
    viewer = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True), viewer, "organisation_staff_viewer", organisation
    )
    request = site_aware_request.get("/")
    request.user = viewer
    request.organisation = organisation

    assert StaffRoleFilter().get_choices(request) == []


@pytest.mark.django_db
def test_the_role_filter_offers_the_usual_five_to_a_roles_viewer(
    site_aware_request: RequestFactory,
):
    organisation = OrganisationFactory()
    viewer = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True),
        viewer,
        "organisation_staff_roles_viewer",
        organisation,
    )
    request = site_aware_request.get("/")
    request.user = viewer
    request.organisation = organisation

    choices = StaffRoleFilter().get_choices(request)

    assert [value for value, _ in choices] == [
        "all",
        "organisation_admin",
        "organisation_staff_viewer",
        "organisation_staff_roles_viewer",
        "cohort_admin",
        "cohort_viewer",
    ]


def _staff_toolbar(request: HttpRequest) -> tuple[list[str], list[str], bool]:
    """The filters on the Staff toolbar, those under Add filter, and whether
    Clear all shows."""
    context = StaffDataTable.get_context(
        request,
        StaffDataTable.parse_query(request, "staff"),
        StaffDataTable.get_queryset(request),
        base_url="/",
        page_url="/",
        region_id="staff",
    )
    return (
        [entry["filter"].label for entry in context["toolbar"]],
        [entry["filter"].label for entry in context["add_filter"]],
        bool(context["any_filter_set"]),
    )


@pytest.mark.django_db
def test_a_names_only_viewer_is_offered_no_role_filter_anywhere(
    site_aware_request: RequestFactory,
):
    organisation = OrganisationFactory()
    viewer = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True), viewer, "organisation_staff_viewer", organisation
    )
    request = site_aware_request.get("/")
    request.user = viewer
    request.organisation = organisation

    assert _staff_toolbar(request) == ([], [], False)


@pytest.mark.django_db
def test_a_roles_viewer_keeps_the_role_filter(staff_request):
    request, _ = staff_request

    assert _staff_toolbar(request) == (["Role"], [], False)


@pytest.mark.django_db
def test_a_role_parameter_from_a_names_only_viewer_narrows_nothing(
    site_aware_request: RequestFactory,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    viewer = UserFactory(staff=True)
    assign_role(
        UserFactory(superuser=True), viewer, "organisation_staff_viewer", organisation
    )
    holder = UserFactory()
    assign_role(UserFactory(superuser=True), holder, "cohort_viewer", cohort)
    request = site_aware_request.get("/")
    request.user = viewer
    request.organisation = organisation

    narrowed = _staff_member_pks(request, ["organisation_admin"])
    unfiltered = _staff_member_pks(request)

    assert holder.pk in narrowed
    assert set(narrowed) == set(unfiltered)


@pytest.mark.django_db
def test_all_roles_is_the_roles_default(staff_request):
    assert StaffRoleFilter().default == (StaffRoleFilter.ALL,)


@pytest.mark.django_db
def test_the_role_choices_carry_the_display_names(staff_request):
    request, _ = staff_request

    choices = StaffRoleFilter().get_choices(request)

    assert choices == [
        ("all", "All roles"),
        ("organisation_admin", "Organisation admin"),
        ("organisation_staff_viewer", "Organisation staff viewer"),
        ("organisation_staff_roles_viewer", "Organisation staff and roles viewer"),
        ("cohort_admin", "Cohort admin"),
        ("cohort_viewer", "Cohort viewer"),
    ]


@pytest.fixture
def audit_request(site_aware_request: RequestFactory):
    organisation = OrganisationFactory()
    request = site_aware_request.get("/")
    request.user = UserFactory(superuser=True)
    request.organisation = organisation
    return request, organisation


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
        "Cohorts",
        "Staff and roles",
        "Other",
    ]
    assert dict(dict(groups)["Cohort membership"])["cohort_membership.moved"] == (
        "Learner moved between cohorts"
    )
    assert AuditActionFilter.widget == "grouped_checklist"


@pytest.mark.django_db
def test_the_cohort_table_widens_to_inactive_cohorts_on_the_inactive_parameter(
    site_aware_request: RequestFactory,
):
    organisation = OrganisationFactory()
    request = _educator_request(site_aware_request, organisation)
    active = CohortFactory(organisation=organisation, name="A")
    inactive = CohortFactory(organisation=organisation, name="B", is_active=False)
    request.GET = QueryDict("cohorts-inactive=1")

    query = CohortDataTable.parse_query(request, "cohorts")
    rows = CohortDataTable.filter_queryset(
        request, CohortDataTable.get_queryset(request), query
    )

    assert list(rows) == [active, inactive]


@pytest.mark.django_db
def test_the_audit_log_filters_on_the_when_parameter(audit_request):
    request, organisation = audit_request
    recent = AuditLogEntryFactory(target=organisation)
    with time_machine.travel(datetime.now(UTC) - timedelta(days=30), tick=False):
        AuditLogEntryFactory(target=organisation)
    request.GET = QueryDict("audit-when=7d")

    query = AuditLogEntryTable.parse_query(request, "audit")
    rows = AuditLogEntryTable.filter_queryset(
        request,
        AuditLogEntry.objects.filter(organisation=organisation),
        query,
    )

    assert list(rows) == [recent]
