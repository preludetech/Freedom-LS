"""The shared cohort-registration Deactivate dialog, driven through a minimal
subclass whose scope is one cohort's registrations."""

from __future__ import annotations

from typing import cast

import pytest

from django.contrib.sites.models import Site
from django.db.models import QuerySet
from django.http import Http404, HttpResponse
from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.educator_interface.panels.cohort.config import CohortConfig
from freedom_ls.educator_interface.panels.common.registration_actions import (
    CohortRegistrationDeactivation,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.learner_management.models import Cohort, CohortCourseRegistration
from freedom_ls.panel_framework.context import PanelContext


class _OneCohortDeactivation(CohortRegistrationDeactivation):
    def registration_scope(
        self, ctx: PanelContext
    ) -> QuerySet[CohortCourseRegistration]:
        return cast(Cohort, ctx.instance).course_registrations.all()

    def success_response(
        self, ctx: PanelContext, registration: CohortCourseRegistration
    ) -> HttpResponse:
        return HttpResponse(f"done {registration.pk}", status=299)


def _ctx(
    cohort: Cohort, registration_pk: object, *, post: bool = False
) -> PanelContext:
    factory = RequestFactory()
    data = {"registration": str(registration_pk)}
    request = factory.post("/x", data) if post else factory.get("/x", data)
    request.user = UserFactory(superuser=True)
    return PanelContext(
        request=request,
        instance=cohort,
        base_url="/x",
        name="courses",
        config=CohortConfig,
        reason="No longer needed",
    )


@pytest.mark.django_db
def test_a_registration_outside_the_scope_is_a_404(mock_site_context: Site) -> None:
    cohort = CohortFactory()
    foreign = CohortCourseRegistrationFactory()

    with pytest.raises(Http404):
        _OneCohortDeactivation().get_row_object(_ctx(cohort, foreign.pk))


@pytest.mark.django_db
def test_an_inactive_registration_is_a_404(mock_site_context: Site) -> None:
    cohort = CohortFactory()
    registration = CohortCourseRegistrationFactory(cohort=cohort, is_active=False)

    with pytest.raises(Http404):
        _OneCohortDeactivation().get_row_object(_ctx(cohort, registration.pk))


@pytest.mark.django_db
def test_the_confirm_context_names_the_registrations_own_cohort_and_course(
    mock_site_context: Site,
) -> None:
    cohort = CohortFactory()
    course = CourseFactory(title="Algebra")
    registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
    CohortMembershipFactory(cohort=cohort)
    CohortMembershipFactory(cohort=cohort)

    context = _OneCohortDeactivation().get_confirm_context(
        _ctx(cohort, registration.pk)
    )

    assert context["cohort"] == cohort
    assert context["course"] == course
    assert context["registration"] == registration
    assert context["losing_count"] == 2
    assert context["losing_phrase"] == "2 learners"


@pytest.mark.django_db
def test_submit_deactivates_with_the_reason_and_returns_the_subclass_response(
    mock_site_context: Site,
) -> None:
    cohort = CohortFactory()
    registration = CohortCourseRegistrationFactory(cohort=cohort)

    response = _OneCohortDeactivation().handle_submit(
        _ctx(cohort, registration.pk, post=True)
    )

    registration.refresh_from_db()
    assert registration.is_active is False
    assert response.status_code == 299
    assert response.content == f"done {registration.pk}".encode()


@pytest.mark.django_db
def test_submit_refuses_an_inactive_cohort_with_422_and_changes_nothing(
    mock_site_context: Site,
) -> None:
    cohort = CohortFactory(is_active=False)
    registration = CohortCourseRegistrationFactory(cohort=cohort)

    response = _OneCohortDeactivation().handle_submit(
        _ctx(cohort, registration.pk, post=True)
    )

    registration.refresh_from_db()
    assert response.status_code == 422
    assert registration.is_active is True
