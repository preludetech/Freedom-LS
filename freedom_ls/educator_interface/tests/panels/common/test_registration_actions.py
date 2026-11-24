"""The shared registration dialogs, driven through minimal subclasses whose
scope is one cohort's or one learner's registrations."""

from __future__ import annotations

from typing import cast
from unittest import mock

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
    LearnerRegistrationDeactivation,
    LearnerRegistrationReactivation,
)
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.learner.config import LearnerConfig
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
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    COURSE_NOT_OPEN_MESSAGE,
    CourseNotOpenError,
)
from freedom_ls.organisations.factories import OrganisationFactory
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


class _OneLearnerDeactivation(LearnerRegistrationDeactivation):
    def registration_scope(
        self, ctx: PanelContext
    ) -> QuerySet[LearnerCourseRegistration]:
        return LearnerCourseRegistration.objects.filter(
            learner=cast(Learner, ctx.instance)
        )


class _OneLearnerReactivation(LearnerRegistrationReactivation):
    def registration_scope(
        self, ctx: PanelContext
    ) -> QuerySet[LearnerCourseRegistration]:
        return LearnerCourseRegistration.objects.filter(
            learner=cast(Learner, ctx.instance)
        )


def _learner_ctx(
    learner: Learner, registration_pk: object, *, post: bool = False
) -> PanelContext:
    factory = RequestFactory()
    data = {"registration": str(registration_pk)}
    request = factory.post("/x", data) if post else factory.get("/x", data)
    request.user = UserFactory(superuser=True)
    cast(OrganisationScopedRequest, request).organisation = learner.organisation
    return PanelContext(
        request=request,
        instance=learner,
        base_url="/x",
        name="registrations",
        config=LearnerConfig,
        reason="No longer needed",
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("action", "is_active"),
    [(_OneLearnerDeactivation, False), (_OneLearnerReactivation, True)],
)
def test_a_learner_registration_of_the_wrong_state_is_a_404(
    mock_site_context: Site,
    action: type[LearnerRegistrationDeactivation | LearnerRegistrationReactivation],
    is_active: bool,
) -> None:
    learner = LearnerFactory()
    registration = LearnerCourseRegistrationFactory(
        learner=learner, is_active=is_active
    )

    with pytest.raises(Http404):
        action().get_row_object(_learner_ctx(learner, registration.pk))


@pytest.mark.django_db
@pytest.mark.parametrize("action", [_OneLearnerDeactivation, _OneLearnerReactivation])
def test_a_learner_registration_outside_the_scope_is_a_404(
    mock_site_context: Site,
    action: type[LearnerRegistrationDeactivation | LearnerRegistrationReactivation],
) -> None:
    learner = LearnerFactory()
    foreign = LearnerCourseRegistrationFactory(is_active=False)
    LearnerCourseRegistration.objects.filter(pk=foreign.pk).update(is_active=True)

    with pytest.raises(Http404):
        action().get_row_object(_learner_ctx(learner, foreign.pk))


@pytest.mark.django_db
def test_the_deactivation_context_comes_from_the_registrations_own_learner(
    mock_site_context: Site,
) -> None:
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    course = CourseFactory(title="Algebra")
    registration = LearnerCourseRegistrationFactory(learner=learner, course=course)
    cohort = CohortFactory(organisation=organisation, name="Year 10")
    CohortMembershipFactory(cohort=cohort, learner=learner)
    CohortCourseRegistrationFactory(cohort=cohort, course=course)

    context = _OneLearnerDeactivation().get_confirm_context(
        _learner_ctx(learner, registration.pk)
    )

    assert context["learner"] == learner
    assert context["course"] == course
    assert context["registration"] == registration
    assert context["keeps_access"] is True
    assert context["keeping_cohorts"] == "Year 10"


@pytest.mark.django_db
def test_learner_deactivation_submit_deactivates_with_the_reason(
    mock_site_context: Site,
) -> None:
    learner = LearnerFactory()
    registration = LearnerCourseRegistrationFactory(learner=learner)

    response = _OneLearnerDeactivation().handle_submit(
        _learner_ctx(learner, registration.pk, post=True)
    )

    registration.refresh_from_db()
    assert response.status_code == 204
    assert registration.is_active is False


@pytest.mark.django_db
def test_the_reactivation_context_comes_from_the_registrations_own_learner(
    mock_site_context: Site,
) -> None:
    learner = LearnerFactory()
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=False)

    context = _OneLearnerReactivation().get_confirm_context(
        _learner_ctx(learner, registration.pk)
    )

    assert context["learner"] == learner
    assert context["course"] == registration.course
    assert context["registration"] == registration


@pytest.mark.django_db
def test_learner_reactivation_submit_reactivates_the_registration(
    mock_site_context: Site,
) -> None:
    learner = LearnerFactory()
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=False)

    response = _OneLearnerReactivation().handle_submit(
        _learner_ctx(learner, registration.pk, post=True)
    )

    registration.refresh_from_db()
    assert response.status_code == 204
    assert registration.is_active is True


@pytest.mark.django_db
def test_learner_reactivation_refuses_a_course_closed_to_the_organisation(
    mock_site_context: Site,
) -> None:
    learner = LearnerFactory()
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=False)
    registration.course.organisations.add(OrganisationFactory())

    response = _OneLearnerReactivation().handle_submit(
        _learner_ctx(learner, registration.pk, post=True)
    )

    registration.refresh_from_db()
    assert response.status_code == 422
    assert COURSE_NOT_OPEN_MESSAGE in response.content.decode()
    assert registration.is_active is False


@pytest.mark.django_db
def test_learner_reactivation_refuses_a_course_the_service_finds_closed(
    mock_site_context: Site,
) -> None:
    learner = LearnerFactory()
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=False)

    with mock.patch(
        "freedom_ls.educator_interface.panels.common.registration_actions.register_for_course",
        side_effect=CourseNotOpenError("Not open to this organisation."),
    ):
        response = _OneLearnerReactivation().handle_submit(
            _learner_ctx(learner, registration.pk, post=True)
        )

    assert response.status_code == 422
    assert "Not open to this organisation." in response.content.decode()
