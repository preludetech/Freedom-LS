"""The attempt review page: educator_interface/panels/learner/quiz_attempt.py."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import lxml.html
import pytest
from pytest_django.fixtures import DjangoAssertNumQueries

from django.http import HttpRequest
from django.test import Client
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.learner.quiz_attempt import (
    openable_sitting_ids,
)
from freedom_ls.educator_interface.tests.helpers import (
    _get_document,
    _header_of,
    _interface_url,
    organisation_admin_viewer,
)
from freedom_ls.form_engine.factories import FormFactory
from freedom_ls.form_engine.models import FormProgress, FormStrategy
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    CourseProgressFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import assign_object_role

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("mock_site_context")]


def _sitting(
    learner: Learner,
    *,
    strategy: str = FormStrategy.QUIZ,
    completed: bool = True,
    pass_percentage: int | None = 50,
    scores: dict[str, int] | None = None,
    title: str = "Safety quiz",
    course_title: str = "Aviation basics",
    **attempt_kwargs: object,
) -> FormProgress:
    attempt = CourseFormAttemptFactory(
        form=FormFactory(
            title=title, strategy=strategy, quiz_pass_percentage=pass_percentage
        ),
        course_progress=CourseProgressFactory(
            learner=learner, course=CourseFactory(title=course_title)
        ),
        form_progress__completed_time=timezone.now() if completed else None,
        form_progress__scores=scores or {"score": 2, "max_score": 3},
        **attempt_kwargs,
    )
    return cast(FormProgress, attempt.form_progress)


def _page(
    client: Client, organisation: Organisation, sitting: FormProgress
) -> lxml.html.HtmlElement:
    return _get_document(
        client, _interface_url(organisation.slug, f"quiz-attempts/{sitting.pk}")
    )


def _admin_client(
    organisation: Organisation, logged_in_client: Callable[[User], Client]
) -> Client:
    return logged_in_client(organisation_admin_viewer(organisation))


def _text(element: lxml.html.HtmlElement) -> str:
    return " ".join(element.text_content().split())


def test_an_organisation_admin_sees_the_label_the_subtitle_and_the_summary_rows(
    logged_in_client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(
        organisation=organisation, user__first_name="Ada", user__last_name="Lovelace"
    )
    sitting = _sitting(learner)

    document = _page(
        _admin_client(organisation, logged_in_client), organisation, sitting
    )

    (heading,) = document.cssselect("#instance-title")
    assert _text(heading) == "Safety quiz, attempt 1"
    assert "Ada Lovelace · Aviation basics" in _text(_header_of(document))
    (panel,) = document.cssselect("section[data-panel='summary']")
    assert [_text(label) for label in panel.cssselect("dt")] == [
        "Started",
        "Completed",
        "Pass mark (current setting)",
    ]


def test_the_header_stats_read_the_stored_score_and_the_verdict(logged_in_client):
    organisation = OrganisationFactory()
    sitting = _sitting(
        LearnerFactory(organisation=organisation),
        pass_percentage=50,
        scores={"score": 2, "max_score": 3},
    )

    document = _page(
        _admin_client(organisation, logged_in_client), organisation, sitting
    )

    header = _text(_header_of(document))
    assert "Score 2/3" in header
    assert "Percentage 67%" in header
    assert "Result Passed" in header


def test_a_quiz_with_no_pass_mark_reads_no_pass_mark_in_the_header_and_the_summary(
    logged_in_client,
):
    organisation = OrganisationFactory()
    sitting = _sitting(LearnerFactory(organisation=organisation), pass_percentage=None)

    document = _page(
        _admin_client(organisation, logged_in_client), organisation, sitting
    )

    assert "Result No pass mark" in _text(_header_of(document))
    (panel,) = document.cssselect("section[data-panel='summary']")
    assert "Pass mark (current setting) No pass mark" in _text(panel)


def test_the_back_link_returns_to_the_learners_courses_tab(logged_in_client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(
        organisation=organisation, user__first_name="Ada", user__last_name="Lovelace"
    )
    sitting = _sitting(learner)

    document = _page(
        _admin_client(organisation, logged_in_client), organisation, sitting
    )

    (link,) = document.cssselect("#breadcrumbs a")
    assert _text(link) == "Back to Ada Lovelace"
    assert link.get("href") == _interface_url(
        organisation.slug, f"learners/{learner.pk}/__tabs/courses"
    )


def test_a_course_another_organisation_owns_names_its_owner_in_the_subtitle(
    logged_in_client,
):
    organisation = OrganisationFactory()
    owner = OrganisationFactory(name="Acme Training")
    learner = LearnerFactory(
        organisation=organisation, user__first_name="Ada", user__last_name="Lovelace"
    )
    sitting = _sitting(learner)
    course = sitting.course_attempt.course_progress.course
    course.organisations.add(owner)

    document = _page(
        _admin_client(organisation, logged_in_client), organisation, sitting
    )

    assert "Ada Lovelace · Aviation basics · Shared by Acme Training" in _text(
        _header_of(document)
    )


def _outside_cohort(organisation: Organisation) -> tuple[User, FormProgress]:
    """A cohort educator, and a learner who is in no cohort they hold."""
    educator = cast(User, UserFactory(staff=True))
    assign_object_role(
        educator, CohortFactory(organisation=organisation), "cohort_admin"
    )
    return educator, _sitting(LearnerFactory(organisation=organisation))


def _through_hidden_cohort(organisation: Organisation) -> tuple[User, FormProgress]:
    """A cohort educator, and a visible learner whose course came through a
    cohort the educator cannot see."""
    visible = CohortFactory(organisation=organisation)
    hidden = CohortFactory(organisation=organisation)
    educator = cast(User, UserFactory(staff=True))
    assign_object_role(educator, visible, "cohort_admin")
    learner = LearnerFactory(organisation=organisation)
    CohortMembershipFactory(cohort=visible, learner=learner)
    CohortMembershipFactory(cohort=hidden, learner=learner)
    course = CourseFactory(title="Aviation basics")
    registration = CohortCourseRegistrationFactory(cohort=hidden, course=course)
    attempt = CourseFormAttemptFactory(
        form=FormFactory(strategy=FormStrategy.QUIZ),
        course_progress=CourseProgressFactory(
            learner=learner,
            course=course,
            learner_registration=None,
            cohort_registration=registration,
        ),
        form_progress__completed_time=timezone.now(),
        form_progress__scores={"score": 2, "max_score": 3},
    )
    return educator, cast(FormProgress, attempt.form_progress)


def _other_organisations_educator(
    organisation: Organisation,
) -> tuple[User, FormProgress]:
    return (
        organisation_admin_viewer(OrganisationFactory()),
        _sitting(LearnerFactory(organisation=organisation)),
    )


def _without_view_learner(organisation: Organisation) -> tuple[User, FormProgress]:
    educator = cast(User, UserFactory(staff=True))
    assign_object_role(educator, organisation, "organisation_staff_viewer")
    return educator, _sitting(LearnerFactory(organisation=organisation))


def _not_a_quiz(organisation: Organisation) -> tuple[User, FormProgress]:
    return organisation_admin_viewer(organisation), _sitting(
        LearnerFactory(organisation=organisation),
        strategy=FormStrategy.CATEGORY_VALUE_SUM,
    )


def _in_progress(organisation: Organisation) -> tuple[User, FormProgress]:
    return organisation_admin_viewer(organisation), _sitting(
        LearnerFactory(organisation=organisation), completed=False
    )


def _without_a_course_attempt(organisation: Organisation) -> tuple[User, FormProgress]:
    learner = LearnerFactory(organisation=organisation)
    sitting = _sitting(learner)
    sitting.course_attempt.delete()
    return organisation_admin_viewer(organisation), FormProgress.objects.get(
        pk=sitting.pk
    )


def _sat_by_someone_else(organisation: Organisation) -> tuple[User, FormProgress]:
    sitting = _sitting(LearnerFactory(organisation=organisation))
    sitting.user = UserFactory()
    sitting.save()
    return organisation_admin_viewer(organisation), sitting


@pytest.mark.parametrize(
    "build",
    [
        _outside_cohort,
        _through_hidden_cohort,
        _other_organisations_educator,
        _without_view_learner,
        _not_a_quiz,
        _in_progress,
        _without_a_course_attempt,
        _sat_by_someone_else,
    ],
)
def test_a_sitting_the_educator_may_not_open_is_a_404(build, logged_in_client):
    organisation = OrganisationFactory()
    educator, sitting = build(organisation)

    response = logged_in_client(educator).get(
        _interface_url(organisation.slug, f"quiz-attempts/{sitting.pk}")
    )

    assert response.status_code == 404


def test_the_bare_section_path_is_a_404(logged_in_client):
    organisation = OrganisationFactory()

    response = _admin_client(organisation, logged_in_client).get(
        _interface_url(organisation.slug, "quiz-attempts")
    )

    assert response.status_code == 404


def _scoped_request(organisation: Organisation, viewer: User) -> HttpRequest:
    request = HttpRequest()
    request.user = viewer
    cast(OrganisationScopedRequest, request).organisation = organisation
    return request


def test_openable_sitting_ids_costs_no_more_queries_for_twenty_sittings_than_for_two(
    django_assert_max_num_queries: DjangoAssertNumQueries,
):
    organisation = OrganisationFactory()
    viewer = organisation_admin_viewer(organisation)
    learner = LearnerFactory(organisation=organisation)
    course_progress = CourseProgressFactory(learner=learner)
    form = FormFactory(strategy=FormStrategy.QUIZ)

    def sit(count: int) -> list[FormProgress]:
        return [
            CourseFormAttemptFactory(
                form=form,
                course_progress=course_progress,
                form_progress__completed_time=timezone.now(),
            ).form_progress
            for _ in range(count)
        ]

    two = sit(2)
    with django_assert_max_num_queries(12) as bound:
        openable_sitting_ids(
            cast(OrganisationScopedRequest, _scoped_request(organisation, viewer)),
            [s.pk for s in two],
        )
    twenty = two + sit(18)

    with django_assert_max_num_queries(len(bound.captured_queries)):
        opened = openable_sitting_ids(
            cast(OrganisationScopedRequest, _scoped_request(organisation, viewer)),
            [s.pk for s in twenty],
        )

    assert len(opened) == 20


def test_the_page_stays_under_its_query_bound(
    logged_in_client, django_assert_max_num_queries: DjangoAssertNumQueries
):
    organisation = OrganisationFactory()
    sitting = _sitting(LearnerFactory(organisation=organisation))
    client = _admin_client(organisation, logged_in_client)
    url = _interface_url(organisation.slug, f"quiz-attempts/{sitting.pk}")

    with django_assert_max_num_queries(60):
        response = client.get(url)

    assert response.status_code == 200
