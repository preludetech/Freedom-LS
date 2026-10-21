"""The cohort list's own table filters."""

from __future__ import annotations

from typing import cast

import pytest

from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.educator_interface.filters import (
    LearnerCohortFilter,
    LearnerCourseFilter,
    LearnerStatusFilter,
    MemberRoleFilter,
    ShowInactiveFilter,
    VisibleCourseFilter,
)
from freedom_ls.educator_interface.views import CohortDataTable, MemberDataTable
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
from freedom_ls.panel_framework.filters import TableFilter
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
def test_show_inactive_filter_returns_its_queryset_unchanged():
    CohortFactory(is_active=False)
    queryset = Cohort.objects.all()

    result = ShowInactiveFilter("inactive", "Show inactive").apply(
        _any_request(), queryset, ["1"]
    )

    assert result is queryset


@pytest.mark.django_db
def test_show_inactive_filter_offers_one_choice_labelled_with_its_label():
    filter_ = ShowInactiveFilter("inactive", "Show inactive")

    assert filter_.get_choices(RequestFactory().get("/")) == [("1", "Show inactive")]


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
    """Only ShowInactiveFilter narrows the table: another filter list, with
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
            return [ShowInactiveFilter("all", "Show all")]

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
    removed = cast(Learner, LearnerFactory(organisation=organisation, is_active=False))
    return {"active": active, "pending": pending, "removed": removed}


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["active", "pending", "removed"])
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


def _member_pks(request, roles: list[str] | None = None) -> list:
    filters = {} if roles is None else {"role": roles}
    query = TableQuery(key="members", filters=filters)
    return [
        user.pk
        for user in MemberDataTable.filter_queryset(
            request, MemberDataTable.get_queryset(request), query
        )
    ]


@pytest.fixture
def members_request(site_aware_request: RequestFactory):
    organisation = OrganisationFactory()
    request = _educator_request(site_aware_request, organisation)
    return request, organisation


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role", ["organisation_admin", "cohort_admin", "cohort_viewer"]
)
def test_the_role_filter_narrows_members_to_each_role(members_request, role):
    request, organisation = members_request
    cohort = CohortFactory(organisation=organisation)
    grantor = UserFactory(superuser=True)
    holders = {}
    for held in ("organisation_admin", "cohort_admin", "cohort_viewer"):
        holders[held] = UserFactory()
        target = organisation if held == "organisation_admin" else cohort
        assign_role(grantor, holders[held], held, target)

    result = set(_member_pks(request, [role]))

    assert result & {h.pk for h in holders.values()} == {holders[role].pk}


@pytest.mark.django_db
def test_a_member_holding_two_roles_is_returned_once(members_request):
    request, organisation = members_request
    cohort = CohortFactory(organisation=organisation)
    grantor = UserFactory(superuser=True)
    both = UserFactory()
    assign_role(grantor, both, "cohort_admin", cohort)
    assign_role(grantor, both, "cohort_viewer", cohort)

    result = _member_pks(request, ["cohort_admin", "cohort_viewer"])

    assert result.count(both.pk) == 1


@pytest.mark.django_db
def test_all_roles_narrows_nothing(members_request):
    request, organisation = members_request
    cohort = CohortFactory(organisation=organisation)
    assign_role(UserFactory(superuser=True), UserFactory(), "cohort_viewer", cohort)

    assert len(_member_pks(request, [MemberRoleFilter.ALL])) == len(
        _member_pks(request)
    )
    assert len(_member_pks(request)) == 2


@pytest.mark.django_db
def test_all_roles_beside_a_role_still_means_every_role(members_request):
    request, organisation = members_request
    cohort = CohortFactory(organisation=organisation)
    assign_role(UserFactory(superuser=True), UserFactory(), "cohort_viewer", cohort)

    result = _member_pks(request, [MemberRoleFilter.ALL, "organisation_admin"])

    assert len(result) == 2


@pytest.mark.django_db
def test_the_role_filter_narrows_by_itself(members_request):
    request, organisation = members_request
    cohort = CohortFactory(organisation=organisation)
    grantor = UserFactory(superuser=True)
    admin = UserFactory()
    assign_role(grantor, admin, "cohort_admin", cohort)
    viewer = UserFactory()
    assign_role(grantor, viewer, "cohort_viewer", cohort)
    everyone = MemberDataTable.get_queryset(request)

    narrowed = MemberRoleFilter().apply(request, everyone, ["cohort_admin"])
    unchanged = MemberRoleFilter().apply(request, everyone, [MemberRoleFilter.ALL])

    assert set(narrowed) == {admin}
    assert set(unchanged) == set(everyone)


@pytest.mark.django_db
def test_all_roles_is_the_roles_default(members_request):
    assert MemberRoleFilter().default == (MemberRoleFilter.ALL,)


@pytest.mark.django_db
def test_the_role_choices_carry_the_display_names(members_request):
    request, _ = members_request

    choices = MemberRoleFilter().get_choices(request)

    assert choices == [
        ("all", "All roles"),
        ("organisation_admin", "Organisation admin"),
        ("cohort_admin", "Cohort admin"),
        ("cohort_viewer", "Cohort viewer"),
    ]
