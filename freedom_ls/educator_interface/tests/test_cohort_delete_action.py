"""Deleting a cohort from its page header.

The delete action belongs to the cohort page as a whole, so it renders and
submits through the instance URL rather than any one panel's.

The cohort panel also renders for a cohort whose registrations granted progress.

CourseProgress protects its grant FKs, so Django's Collector raises rather than
returning a cascade preview. DeleteAction renders that preview on every GET, for
every viewer holding delete_cohort — which turned the whole panel into a 500 for
site admins and superusers, while educators (who never see the delete button)
saw nothing wrong.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.panel_framework.events import build_hx_trigger
from freedom_ls.role_based_permissions.utils import assign_object_role


@pytest.fixture
def cohort_with_granted_progress(
    mock_site_context: Site, course_with_topic: Callable[..., Course]
) -> Cohort:
    """A cohort holding a registration that has already granted a record."""
    organisation = OrganisationFactory()
    cohort: Cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")
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


def _delete_url(client: Client, cohort: Cohort) -> str:
    """The delete action's URL: it belongs to the cohort page as a whole."""
    return f"{_panel_url(cohort)}/__actions/delete"


@pytest.mark.django_db
def test_an_empty_cohort_is_deleted_from_its_details_panel(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory(), name="Empty Cohort")
    cohort_pk = cohort.pk
    client = logged_in_client(UserFactory(superuser=True))
    url = _delete_url(client, cohort)

    response = client.delete(url)

    assert response.status_code == 204
    assert json.loads(response["HX-Location"])["path"].endswith("/cohorts")
    # No cohortChanged: the cohort page's own panels listen for it, and would
    # refetch the deleted cohort before the navigation replaced them.
    assert response["HX-Trigger"] == build_hx_trigger({}, close_modal=True)
    assert "HX-Redirect" not in response
    assert not Cohort.objects.filter(pk=cohort_pk).exists()


@pytest.mark.django_db
def test_the_cohort_pages_panels_refresh_on_cohort_changed(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory(), name="Watched Cohort")
    client = logged_in_client(UserFactory(superuser=True))

    body = client.get(_panel_url(cohort)).content.decode()

    # The Details tab holds the details and course registration panels; the
    # learners panel on the other tab listens the same way.
    assert body.count('hx-trigger="cohortChanged from:body"') >= 2


@pytest.mark.django_db
def test_the_cohort_page_renders_the_delete_trigger(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory(), name="Empty Cohort")
    client = logged_in_client(UserFactory(superuser=True))
    url = _delete_url(client, cohort)

    body = client.get(_panel_url(cohort)).content.decode()

    assert f'hx-get="{url}"' in body
    assert f'hx-delete="{url}"' in client.get(url).content.decode()


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
    url = _delete_url(client, cohort_with_granted_progress)

    body = client.get(url).content.decode()

    assert "cannot be deleted because it still has" in body
    assert "course progress record" in body


@pytest.mark.django_db
def test_the_delete_dialog_has_a_heading_naming_the_cohort_and_cancel_then_delete(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory(), name="Empty Cohort")
    client = logged_in_client(UserFactory(superuser=True))
    url = _delete_url(client, cohort)

    document = lxml.html.fromstring(client.get(url).content)

    (heading,) = document.cssselect("#app-modal-title")
    assert heading.text_content().strip() == "Delete Empty Cohort"
    names = [
        el.text_content().split()[0]
        for el in document.iter("button")
        if el.text_content().strip()
    ]
    assert names[-2:] == ["Cancel", "Delete"]


@pytest.mark.django_db
def test_submitting_the_blocked_delete_answers_instead_of_erroring(
    cohort_with_granted_progress: Cohort, logged_in_client: Callable[[User], Client]
) -> None:
    client = logged_in_client(UserFactory(superuser=True))
    url = _delete_url(client, cohort_with_granted_progress)

    response = client.delete(url)

    assert response.status_code == 422
    assert "cannot be deleted because it still has" in response.content.decode()
    assert CourseProgress.objects.filter(
        cohort_registration__cohort=cohort_with_granted_progress
    ).exists()


@pytest.mark.django_db
def test_a_pasted_delete_url_shows_the_site_403_page_to_an_educator(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
) -> None:
    """A cohort viewer can open the cohort but not delete it. Pasting the
    action URL gets the site's own 403 page, not an empty 403 body."""
    cohort = CohortFactory(organisation=OrganisationFactory())
    url = _delete_url(logged_in_client(UserFactory(superuser=True)), cohort)
    educator = UserFactory(staff=True)
    assign_object_role(educator, cohort, "cohort_viewer")
    client = logged_in_client(educator)
    assert client.get(_panel_url(cohort)).status_code == 200

    response = client.get(url)

    assert response.status_code == 403
    assert "You do not have access to this page" in response.content.decode()
    assert Cohort.objects.filter(pk=cohort.pk).exists()


@pytest.mark.django_db
def test_the_delete_dialog_body_says_the_delete_cannot_be_undone(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory(), name="Empty Cohort")
    client = logged_in_client(UserFactory(superuser=True))
    url = _delete_url(client, cohort)

    document = lxml.html.fromstring(client.get(url).content)

    (body,) = document.cssselect("header + div")
    assert "cannot be undone" in body.text_content()
    assert "cohort" in body.text_content()
