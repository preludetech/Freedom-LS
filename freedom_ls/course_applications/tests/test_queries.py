"""Tests for course_applications query helpers."""

from __future__ import annotations

import pytest

from django.contrib.auth.models import AnonymousUser

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.form_engine.factories import FormProgressFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.utils import get_default_organisation


@pytest.mark.django_db
class TestGetApplicationForCourse:
    """get_application_for_course returns the user's application or None."""

    def test_returns_application_when_present(self, mock_site_context):
        """Returns the application when the user has applied to the course."""
        from freedom_ls.course_applications.queries import get_application_for_course

        user = UserFactory()
        course = CourseFactory()
        app = CourseApplicationFactory(user=user, course=course)

        assert get_application_for_course(user=user, course=course) == app

    def test_returns_a_claimed_application(self, mock_site_context):
        """An application that began anonymously is the account's once claimed."""
        from freedom_ls.course_applications.queries import get_application_for_course

        user = UserFactory()
        course = CourseFactory()
        claimed = CourseApplicationFactory(anonymous=True, user=user, course=course)

        assert get_application_for_course(user=user, course=course) == claimed

    def test_prefers_the_active_application_over_a_newer_closed_one(
        self, mock_site_context
    ):
        from freedom_ls.course_applications.queries import get_application_for_course

        user = UserFactory()
        course = CourseFactory()
        active = CourseApplicationFactory(user=user, course=course)
        CourseApplicationFactory(user=user, course=course, withdrawn=True)

        assert get_application_for_course(user=user, course=course) == active

    def test_prefers_the_active_application_over_an_older_closed_one(
        self, mock_site_context
    ):
        from freedom_ls.course_applications.queries import get_application_for_course

        user = UserFactory()
        course = CourseFactory()
        CourseApplicationFactory(user=user, course=course, withdrawn=True)
        active = CourseApplicationFactory(user=user, course=course)

        assert get_application_for_course(user=user, course=course) == active

    def test_returns_the_newest_closed_application_when_none_is_active(
        self, mock_site_context
    ):
        from freedom_ls.course_applications.queries import get_application_for_course

        user = UserFactory()
        course = CourseFactory()
        CourseApplicationFactory(user=user, course=course, withdrawn=True)
        newest = CourseApplicationFactory(user=user, course=course, rejected=True)

        assert get_application_for_course(user=user, course=course) == newest

    def test_returns_none_when_absent(self, mock_site_context):
        """Returns None when the user has no application to the course."""
        from freedom_ls.course_applications.queries import get_application_for_course

        user = UserFactory()
        course = CourseFactory()

        assert get_application_for_course(user=user, course=course) is None

    def test_reads_whether_submitted_in_one_query(
        self, mock_site_context, django_assert_num_queries
    ):
        """The sitting comes with the application, so is_submitted costs nothing more."""
        from freedom_ls.course_applications.queries import get_application_for_course

        user = UserFactory()
        course = CourseFactory()
        CourseApplicationFactory(
            user=user, course=course, form_progress=FormProgressFactory(user=user)
        )

        with django_assert_num_queries(1):
            application = get_application_for_course(user=user, course=course)
            assert application is not None
            assert application.is_submitted is False

    def test_anonymous_user_returns_none_with_no_query(
        self, mock_site_context, django_assert_num_queries
    ):
        """Anonymous user returns None immediately without hitting the database."""
        from freedom_ls.course_applications.queries import get_application_for_course

        course = CourseFactory()

        with django_assert_num_queries(0):
            result = get_application_for_course(user=AnonymousUser(), course=course)

        assert result is None


@pytest.mark.django_db
class TestGetActiveApplications:
    """get_active_applications returns the user's applications."""

    def test_anonymous_user_returns_empty_queryset_with_no_query(
        self, mock_site_context, django_assert_num_queries
    ):
        """Anonymous user returns an empty queryset without hitting the database."""
        from freedom_ls.course_applications.queries import get_active_applications

        with django_assert_num_queries(0):
            result = list(get_active_applications(AnonymousUser()))

        assert result == []

    def test_lists_every_course_the_user_applied_to(self, mock_site_context):
        from freedom_ls.course_applications.queries import get_active_applications

        user = UserFactory()
        first = CourseApplicationFactory(user=user)
        second = CourseApplicationFactory(user=user)

        assert set(get_active_applications(user)) == {first, second}


@pytest.mark.django_db
class TestOrganisationForNewApplication:
    def test_a_course_with_one_owning_organisation_returns_it(self, mock_site_context):
        from freedom_ls.course_applications.queries import (
            organisation_for_new_application,
        )

        course = CourseFactory()
        owner = OrganisationFactory()
        course.organisations.add(owner)

        assert organisation_for_new_application(course) == owner

    @pytest.mark.parametrize("owner_count", [0, 2])
    def test_a_course_without_exactly_one_owner_returns_the_site_default(
        self, mock_site_context, owner_count
    ):
        from freedom_ls.course_applications.queries import (
            organisation_for_new_application,
        )

        course = CourseFactory()
        course.organisations.add(*[OrganisationFactory() for _ in range(owner_count)])

        assert organisation_for_new_application(course) == get_default_organisation(
            course.site
        )
