"""The permission rule every course-page action shares: asked about the
organisation until a row is named, then about that row's own cohort."""

from __future__ import annotations

from typing import cast
from unittest import mock

import pytest

from django.contrib.sites.models import Site
from django.db.models import Model, QuerySet
from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.panels.common.course_page import (
    CoursePageActionMixin,
)
from freedom_ls.educator_interface.panels.common.registration_actions import (
    CHANGE_COHORT_REGISTRATION,
)
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.course.config import CourseConfig
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.learner_management.models import Cohort
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.role_based_permissions.utils import assign_object_role


class _CohortRowAction(CoursePageActionMixin):
    capability = CHANGE_COHORT_REGISTRATION
    row_param = "cohort"

    def get_row_queryset(self, ctx: PanelContext) -> QuerySet[Cohort]:
        return Cohort.objects.all()

    def subject_of(self, row: Model) -> Cohort:
        return cast(Cohort, row)


def _allowed(
    user: User,
    organisation: Organisation,
    course: Course,
    cohort: Cohort | None = None,
) -> bool:
    params = {"cohort": str(cohort.pk)} if cohort else {}
    request = cast(OrganisationScopedRequest, RequestFactory().get("/x", params))
    request.user = user
    request.organisation = organisation
    ctx = PanelContext(
        request=request,
        instance=course,
        base_url="/x",
        name="cohorts",
        config=CourseConfig,
    )
    return _CohortRowAction().has_permission(ctx)


@pytest.fixture
def organisation(mock_site_context: Site) -> Organisation:
    return cast(Organisation, OrganisationFactory())


@pytest.mark.django_db
def test_without_a_row_an_organisation_grant_allows_the_action(
    organisation: Organisation,
) -> None:
    user = UserFactory(staff=True)
    assign_object_role(user, organisation, "organisation_admin")

    assert _allowed(user, organisation, CourseFactory()) is True


@pytest.mark.django_db
def test_without_a_row_a_grant_on_any_one_cohort_allows_the_action(
    organisation: Organisation,
) -> None:
    user = UserFactory(staff=True)
    assign_object_role(user, CohortFactory(organisation=organisation), "cohort_admin")

    assert _allowed(user, organisation, CourseFactory()) is True


@pytest.mark.django_db
def test_without_a_row_a_cohort_viewer_is_refused(organisation: Organisation) -> None:
    user = UserFactory(staff=True)
    assign_object_role(user, CohortFactory(organisation=organisation), "cohort_viewer")

    assert _allowed(user, organisation, CourseFactory()) is False


@pytest.mark.django_db
def test_with_a_row_only_its_own_cohort_allows_the_action(
    organisation: Organisation,
) -> None:
    own = CohortFactory(organisation=organisation)
    other = CohortFactory(organisation=organisation)
    user = UserFactory(staff=True)
    assign_object_role(user, own, "cohort_admin")
    course = CourseFactory()

    assert _allowed(user, organisation, course, own) is True
    assert _allowed(user, organisation, course, other) is False


@pytest.mark.django_db
def test_can_is_never_asked_about_the_course(organisation: Organisation) -> None:
    user = UserFactory(staff=True)
    assign_object_role(user, organisation, "organisation_admin")
    cohort = CohortFactory(organisation=organisation)
    course = CourseFactory()
    asked: list[object] = []

    def spy(asked_user: User, capability: str, scope: Model) -> bool:
        asked.append(scope)
        return can(asked_user, capability, scope)

    with (
        mock.patch("freedom_ls.educator_interface.panels.common.course_page.can", spy),
        mock.patch("freedom_ls.learner_management.queries.can", spy),
    ):
        _allowed(user, organisation, course)
        _allowed(user, organisation, course, cohort)

    assert asked
    assert not any(isinstance(scope, Course) for scope in asked)


class _OpenHereAction(CoursePageActionMixin):
    pass


def _open_here(organisation: Organisation, course: Course) -> bool:
    request = cast(OrganisationScopedRequest, RequestFactory().get("/x"))
    request.organisation = organisation
    ctx = PanelContext(
        request=request,
        instance=course,
        base_url="/x",
        name="cohorts",
        config=CourseConfig,
    )
    return _OpenHereAction().course_open_here(ctx)


@pytest.mark.django_db
def test_a_course_with_no_owning_organisation_is_open_here(
    organisation: Organisation,
) -> None:
    assert _open_here(organisation, CourseFactory()) is True


@pytest.mark.django_db
def test_a_course_owned_by_another_organisation_is_not_open_here(
    organisation: Organisation,
) -> None:
    course = CourseFactory()
    course.organisations.add(OrganisationFactory())

    assert _open_here(organisation, course) is False


@pytest.mark.django_db
def test_a_course_shared_with_the_organisation_is_open_here(
    organisation: Organisation,
) -> None:
    course = CourseFactory()
    course.organisations.add(OrganisationFactory())
    course.shared_with.add(organisation)

    assert _open_here(organisation, course) is True
