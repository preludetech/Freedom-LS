"""Educator surfaces that show a person's profile picture, and the ones that stay on initials."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.comms.factories import ConversationFactory, MessageFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.educator_interface.tests.test_reporting import (
    _body_region,
    _body_url,
    _seeded_report_cohort,
)
from freedom_ls.learner_management.factories import (
    CohortFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import assign_object_role

pytestmark = pytest.mark.django_db

Surface = Callable[[Organisation, User], str]


@pytest.fixture(autouse=True)
def _site_context(mock_site_context: Site) -> None:
    """Every test here builds site-aware objects and assigns roles."""


@pytest.fixture(autouse=True)
def _messaging_on(settings) -> None:
    settings.MESSAGING_ENABLED = True


def _url(organisation: Organisation, path_string: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": path_string},
    )


def _viewer(organisation: Organisation) -> User:
    viewer = cast(User, UserFactory(staff=True))
    assign_object_role(viewer, organisation, "organisation_admin")
    return viewer


def _get(organisation: Organisation, path_string: str, viewer: User) -> str:
    client = Client()
    client.force_login(viewer)
    response = client.get(_url(organisation, path_string))
    assert response.status_code == 200
    return str(response.content.decode())


def _pictures(content: str) -> list[str]:
    return [
        image.get("src")
        for image in lxml.html.fromstring(content).cssselect(
            "img[data-profile-picture]"
        )
    ]


def _learners_table(organisation: Organisation, person: User) -> str:
    LearnerFactory(organisation=organisation, user=person)
    return _get(organisation, "learners", _viewer(organisation))


def _registrations_table(organisation: Organisation, person: User) -> str:
    course = CourseFactory()
    learner = LearnerFactory(organisation=organisation, user=person)
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=True)
    return _get(
        organisation, f"courses/{course.pk}/__panels/learners", _viewer(organisation)
    )


def _staff_table(organisation: Organisation, person: User) -> str:
    assign_role(UserFactory(superuser=True), person, "organisation_admin", organisation)
    return _get(organisation, "staff", _viewer(organisation))


def _cohort_settings(organisation: Organisation, person: User) -> str:
    cohort = CohortFactory(organisation=organisation)
    assign_role(UserFactory(superuser=True), person, "cohort_admin", cohort)
    return _get(
        organisation, f"cohorts/{cohort.pk}/__tabs/settings", _viewer(organisation)
    )


def _learner_messages(organisation: Organisation, person: User) -> str:
    learner = cast(Learner, LearnerFactory(organisation=organisation, user=person))
    viewer = _viewer(organisation)
    conversation = ConversationFactory(between=(viewer, person))
    MessageFactory(conversation=conversation, sender=person)
    return _get(organisation, f"learners/{learner.pk}/__tabs/messages", viewer)


SURFACES = [
    pytest.param(_learners_table, id="learners-table"),
    pytest.param(_registrations_table, id="course-registrations-table"),
    pytest.param(_staff_table, id="staff-table"),
    pytest.param(_cohort_settings, id="cohort-settings"),
    pytest.param(_learner_messages, id="learner-messages"),
]


@pytest.mark.parametrize("surface", SURFACES)
def test_a_person_with_a_picture_shows_it(surface: Surface) -> None:
    person = cast(User, UserFactory(with_profile_picture=True))

    content = surface(OrganisationFactory(), person)

    assert person.profile_picture_url in _pictures(content)


@pytest.mark.parametrize("surface", SURFACES)
def test_a_person_without_a_picture_shows_initials_alone(surface: Surface) -> None:
    content = surface(OrganisationFactory(), cast(User, UserFactory()))

    assert _pictures(content) == []
    assert 'src="None"' not in content


def _add_learner_rows(organisation: Organisation, count: int) -> None:
    for _ in range(count):
        LearnerFactory(
            organisation=organisation, user=UserFactory(with_profile_picture=True)
        )


def _add_staff_rows(organisation: Organisation, count: int) -> None:
    grantor = UserFactory(superuser=True)
    for _ in range(count):
        assign_role(
            grantor,
            UserFactory(with_profile_picture=True),
            "organisation_admin",
            organisation,
        )


@pytest.mark.parametrize(
    ("add_rows", "path_string"),
    [
        pytest.param(_add_learner_rows, "learners", id="learners-table"),
        pytest.param(_add_staff_rows, "staff", id="staff-table"),
    ],
)
def test_more_rows_with_pictures_cost_no_more_queries(
    add_rows: Callable[[Organisation, int], None],
    path_string: str,
    django_assert_max_num_queries,
) -> None:
    organisation = OrganisationFactory()
    viewer = _viewer(organisation)
    add_rows(organisation, 1)
    with CaptureQueriesContext(connection) as one_row:
        _get(organisation, path_string, viewer)
    add_rows(organisation, 4)

    with django_assert_max_num_queries(len(one_row.captured_queries)):
        content = _get(organisation, path_string, viewer)

    assert len(_pictures(content)) >= 5


def test_the_audit_log_names_a_person_with_initials_alone() -> None:
    organisation = OrganisationFactory()
    person = cast(User, UserFactory(with_profile_picture=True))
    AuditLogEntryFactory(
        organisation=organisation,
        actor=person,
        actor_label=person.display_name,
        target=person,
        target_label=person.display_name,
    )

    content = _get(organisation, "audit-log", _viewer(organisation))

    assert person.display_name in content
    assert _pictures(content) == []


def test_the_cohort_report_body_names_a_learner_with_initials_alone() -> None:
    cohort = _seeded_report_cohort()
    for membership in cohort.cohortmembership_set.select_related("learner__user"):
        UserFactory._meta.model.objects.filter(pk=membership.learner.user_id).update(
            profile_picture="profile_pictures/x.webp"
        )
    client = Client()
    client.force_login(_viewer(cohort.organisation))

    region = _body_region(client, _body_url(cohort.organisation.slug, cohort.pk))

    assert region.cssselect("tbody a")
    assert region.cssselect("img[data-profile-picture]") == []
