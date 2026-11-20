"""Tests for the staff role filter."""

from __future__ import annotations

import pytest

from django.http import HttpRequest
from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.educator_interface.panels.staff.filters import StaffRoleFilter
from freedom_ls.educator_interface.tests.helpers import _educator_request
from freedom_ls.educator_interface.views import StaffDataTable
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.panel_framework.tables import TableQuery

pytestmark = pytest.mark.usefixtures("_site_context")


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
