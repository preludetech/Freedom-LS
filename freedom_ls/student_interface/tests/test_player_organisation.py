"""Tests for the organisation a learner is studying a course through.

Covers organisation_for_learner_course (student_management.queries) — the
resolution order, the duplicate-registration tiebreak, and its query-count
contract — plus the co-branding chip it feeds into the course player's TOC
header.
"""

from __future__ import annotations

import io
from datetime import timedelta

import pytest
from PIL import Image

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    UserCourseRegistrationFactory,
)
from freedom_ls.student_management.models import UserCourseRegistration
from freedom_ls.student_management.queries import organisation_for_learner_course

# The TOC header's course-title paragraph, used to prove the co-branding chip
# renders above the title rather than below it.
TOC_TITLE_MARKER = '<p class="text-lg font-semibold text-on-surface">'


def _logo_upload(name: str = "logo.png") -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new("RGB", (200, 100)).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def _backdate(
    registration: UserCourseRegistration, when: object
) -> UserCourseRegistration:
    """Set registered_at directly, bypassing auto_now_add's save-time override."""
    UserCourseRegistration.objects.filter(pk=registration.pk).update(registered_at=when)
    registration.refresh_from_db()
    return registration


@pytest.mark.django_db
class TestOrganisationForLearnerCourse:
    """Cohort registration wins over an individual one; with neither, there is
    no organisation to report."""

    def test_no_registration_returns_none(self, mock_site_context, course_with_topic):
        course = course_with_topic()
        user = UserFactory()

        assert organisation_for_learner_course(user, course) is None

    def test_cohort_registration_wins_over_an_individual_one(
        self, mock_site_context, course_with_topic
    ):
        course = course_with_topic()
        user = UserFactory()
        cohort_organisation = OrganisationFactory()
        individual_organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=cohort_organisation)
        CohortMembershipFactory(user=user, cohort=cohort)
        CohortCourseRegistrationFactory(cohort=cohort, collection=course)
        UserCourseRegistrationFactory(
            user=user, collection=course, organisation=individual_organisation
        )

        assert organisation_for_learner_course(user, course) == cohort_organisation

    def test_individual_registration_only_uses_its_organisation(
        self, mock_site_context, course_with_topic
    ):
        course = course_with_topic()
        user = UserFactory()
        organisation = OrganisationFactory()
        UserCourseRegistrationFactory(
            user=user, collection=course, organisation=organisation
        )

        assert organisation_for_learner_course(user, course) == organisation

    def test_two_individual_registrations_prefer_the_most_recent_active_one(
        self, mock_site_context, course_with_topic
    ):
        """Mirrors latest_registration's own tiebreak test — this helper must
        not re-derive it."""
        course = course_with_topic()
        user = UserFactory()
        organisation_a = OrganisationFactory()
        organisation_b = OrganisationFactory()
        older = UserCourseRegistrationFactory(
            user=user, collection=course, organisation=organisation_a, is_active=True
        )
        _backdate(older, timezone.now() - timedelta(days=7))
        newer = UserCourseRegistrationFactory(
            user=user, collection=course, organisation=organisation_b, is_active=True
        )

        assert organisation_for_learner_course(user, course) == organisation_b
        assert newer.organisation == organisation_b


@pytest.mark.django_db
class TestOrganisationForLearnerCourseQueryCount:
    """The resolver's cost is a small, fixed number of queries per path — it
    must never grow with how many registrations a learner happens to hold."""

    def test_cohort_path_ignores_individual_registrations_in_a_single_query(
        self, mock_site_context, course_with_topic, django_assert_num_queries
    ):
        course = course_with_topic()
        user = UserFactory()
        cohort = CohortFactory()
        CohortMembershipFactory(user=user, cohort=cohort)
        CohortCourseRegistrationFactory(cohort=cohort, collection=course)
        # Duplicate individual registrations the cohort path must never even
        # look at — present to prove the query count does not grow with them.
        UserCourseRegistrationFactory(user=user, collection=course)
        UserCourseRegistrationFactory(user=user, collection=course)

        with django_assert_num_queries(1):
            organisation_for_learner_course(user, course)

    def test_individual_path_query_count_does_not_grow_with_duplicates(
        self, mock_site_context, course_with_topic, django_assert_num_queries
    ):
        course = course_with_topic()
        user = UserFactory()
        UserCourseRegistrationFactory(user=user, collection=course)
        UserCourseRegistrationFactory(user=user, collection=course)
        UserCourseRegistrationFactory(user=user, collection=course)

        with django_assert_num_queries(2):
            organisation_for_learner_course(user, course)


@pytest.mark.django_db
class TestCourseOrganisationChip:
    """The resolved organisation reaches the player's TOC header as a chip:
    the logo when there is one, an initials monogram otherwise, with the
    organisation's name rendered as text beside it."""

    def test_logo_renders_beside_the_organisation_name(
        self, mock_site_context, course_with_topic
    ):
        course = course_with_topic()
        user = UserFactory()
        organisation = OrganisationFactory(name="Acme Corp", logo=_logo_upload())
        UserCourseRegistrationFactory(
            user=user, collection=course, organisation=organisation
        )
        client = Client()
        client.force_login(user)

        url = reverse(
            "student_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": 1},
        )
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert organisation.logo.url in content
        assert ">Acme Corp<" in content
        # The visible name is the accessible name, so the mark is decorative.
        assert 'alt=""' in content

        assert content.index("Acme Corp") < content.index(TOC_TITLE_MARKER)

    def test_initials_monogram_renders_when_organisation_has_no_logo(
        self, mock_site_context, course_with_topic
    ):
        course = course_with_topic()
        user = UserFactory()
        organisation = OrganisationFactory(name="Beta School")
        UserCourseRegistrationFactory(
            user=user, collection=course, organisation=organisation
        )
        client = Client()
        client.force_login(user)

        url = reverse(
            "student_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": 1},
        )
        response = client.get(url)

        content = response.content.decode()
        assert organisation.initials in content
        assert ">Beta School<" in content
        # The monogram repeats the visible name, so it is hidden from AT.
        assert 'aria-hidden="true"' in content

        assert content.index("Beta School") < content.index(TOC_TITLE_MARKER)
