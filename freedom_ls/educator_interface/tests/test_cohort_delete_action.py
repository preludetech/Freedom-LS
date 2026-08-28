"""The cohort panel renders for a cohort whose registrations granted progress.

CourseProgress protects its grant FKs, so Django's Collector raises rather than
returning a cascade preview. DeleteAction renders that preview on every GET, for
every viewer holding delete_cohort — which turned the whole panel into a 500 for
site admins and superusers, while educators (who never see the delete button)
saw nothing wrong.
"""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory


@pytest.fixture
def cohort_with_granted_progress(mock_site_context, course_with_topic):
    """A cohort holding a registration that has already granted a record."""
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")
    course = course_with_topic()
    registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
    learner = LearnerFactory(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    # The receivers that would mint this defer to transaction.on_commit, which a
    # rolled-back test transaction never reaches.
    ensure_course_progress_record(learner, course, registration)
    return cohort


def _panel_url(cohort) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": cohort.organisation.slug,
            "path_string": f"cohorts/{cohort.pk}",
        },
    )


@pytest.mark.django_db
def test_cohort_panel_renders_for_a_viewer_who_can_delete_it(
    cohort_with_granted_progress, logged_in_client
):
    client = logged_in_client(UserFactory(superuser=True))

    response = client.get(_panel_url(cohort_with_granted_progress))

    assert response.status_code == 200


@pytest.mark.django_db
def test_the_delete_dialog_says_why_the_cohort_cannot_go(
    cohort_with_granted_progress, logged_in_client
):
    client = logged_in_client(UserFactory(superuser=True))

    body = client.get(_panel_url(cohort_with_granted_progress)).content.decode()

    assert "cannot be deleted because it still has" in body
    assert "course progress record" in body


@pytest.mark.django_db
def test_submitting_the_blocked_delete_answers_instead_of_erroring(
    cohort_with_granted_progress, logged_in_client
):
    client = logged_in_client(UserFactory(superuser=True))
    url = f"{_panel_url(cohort_with_granted_progress)}/__actions/delete"

    response = client.delete(url)

    assert response.status_code == 422
    assert "cannot be deleted because it still has" in response.content.decode()
    assert CourseProgress.objects.filter(
        cohort_registration__cohort=cohort_with_granted_progress
    ).exists()
