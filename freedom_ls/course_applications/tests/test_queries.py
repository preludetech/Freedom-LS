"""Tests for course_applications query helpers."""

from __future__ import annotations

from datetime import timedelta

import pytest

from django.contrib.auth.models import AnonymousUser
from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import CourseApplication
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
        self, mock_site_context: Site
    ) -> None:
        from freedom_ls.course_applications.queries import get_application_for_course

        user = UserFactory()
        course = CourseFactory()
        active = CourseApplicationFactory(user=user, course=course)
        CourseApplicationFactory(user=user, course=course, withdrawn=True)

        assert get_application_for_course(user=user, course=course) == active

    def test_prefers_the_active_application_over_an_older_closed_one(
        self, mock_site_context: Site
    ) -> None:
        from freedom_ls.course_applications.queries import get_application_for_course

        user = UserFactory()
        course = CourseFactory()
        CourseApplicationFactory(user=user, course=course, withdrawn=True)
        active = CourseApplicationFactory(user=user, course=course)

        assert get_application_for_course(user=user, course=course) == active

    def test_returns_the_newest_closed_application_when_none_is_active(
        self, mock_site_context: Site
    ) -> None:
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


def _created_ago(application: CourseApplication, days: int) -> CourseApplication:
    """Backdate `application` so creation order is not left to the clock."""
    CourseApplication.objects.filter(pk=application.pk).update(
        created_at=timezone.now() - timedelta(days=days)
    )
    return application


@pytest.mark.django_db
class TestGetDashboardApplications:
    """get_dashboard_applications lists what the user's dashboard panel shows."""

    def test_anonymous_user_returns_empty_queryset_with_no_query(
        self, mock_site_context, django_assert_num_queries
    ):
        """Anonymous user returns an empty queryset without hitting the database."""
        from freedom_ls.course_applications.queries import get_dashboard_applications

        with django_assert_num_queries(0):
            result = list(get_dashboard_applications(AnonymousUser()))

        assert result == []

    def test_lists_every_course_the_user_applied_to(self, mock_site_context):
        from freedom_ls.course_applications.queries import get_dashboard_applications

        user = UserFactory()
        first = CourseApplicationFactory(user=user)
        second = CourseApplicationFactory(user=user)

        assert set(get_dashboard_applications(user)) == {first, second}

    def test_a_withdrawn_application_is_never_listed(
        self, mock_site_context: Site
    ) -> None:
        from freedom_ls.course_applications.queries import get_dashboard_applications

        user = UserFactory()
        CourseApplicationFactory(user=user, withdrawn=True)

        assert list(get_dashboard_applications(user)) == []

    def test_a_rejected_application_is_listed_while_nothing_newer_exists(
        self, mock_site_context: Site
    ) -> None:
        from freedom_ls.course_applications.queries import get_dashboard_applications

        user = UserFactory()
        rejected = CourseApplicationFactory(user=user, rejected=True)

        assert list(get_dashboard_applications(user)) == [rejected]

    @pytest.mark.parametrize(
        "newer_traits",
        [{}, {"approved": True}, {"rejected": True}, {"withdrawn": True}],
    )
    def test_a_newer_application_for_the_course_hides_the_rejection(
        self, mock_site_context: Site, newer_traits: dict[str, bool]
    ) -> None:
        from freedom_ls.course_applications.queries import get_dashboard_applications

        user = UserFactory()
        course = CourseFactory()
        old = _created_ago(
            CourseApplicationFactory(user=user, course=course, rejected=True), 2
        )
        CourseApplicationFactory(user=user, course=course, **newer_traits)

        assert old not in get_dashboard_applications(user)

    def test_another_users_newer_application_does_not_hide_the_rejection(
        self, mock_site_context: Site
    ) -> None:
        from freedom_ls.course_applications.queries import get_dashboard_applications

        user = UserFactory()
        course = CourseFactory()
        rejected = _created_ago(
            CourseApplicationFactory(user=user, course=course, rejected=True), 2
        )
        CourseApplicationFactory(user=UserFactory(), course=course)

        assert list(get_dashboard_applications(user)) == [rejected]

    def test_a_newer_application_on_another_course_does_not_hide_the_rejection(
        self, mock_site_context: Site
    ) -> None:
        from freedom_ls.course_applications.queries import get_dashboard_applications

        user = UserFactory()
        rejected = _created_ago(CourseApplicationFactory(user=user, rejected=True), 2)
        other = CourseApplicationFactory(user=user)

        assert set(get_dashboard_applications(user)) == {rejected, other}

    def test_another_sites_newer_application_does_not_hide_the_rejection(
        self, mock_site_context: Site
    ) -> None:
        from django.contrib.sites.models import Site

        from freedom_ls.course_applications.queries import get_dashboard_applications

        user = UserFactory()
        course = CourseFactory()
        rejected = _created_ago(
            CourseApplicationFactory(user=user, course=course, rejected=True), 2
        )
        other_site = Site.objects.create(domain="other.example.com", name="Other")
        CourseApplicationFactory(user=user, course=course, site=other_site)

        assert list(get_dashboard_applications(user)) == [rejected]

    def test_open_applications_come_first_then_approved_and_rejected_newest_first(
        self, mock_site_context: Site
    ) -> None:
        from freedom_ls.course_applications.queries import get_dashboard_applications

        user = UserFactory()
        old_open = _created_ago(CourseApplicationFactory(user=user), 5)
        new_rejected = _created_ago(
            CourseApplicationFactory(user=user, rejected=True), 1
        )
        old_approved = _created_ago(
            CourseApplicationFactory(user=user, approved=True), 4
        )
        new_open = _created_ago(
            CourseApplicationFactory(
                user=user, form_progress=FormProgressFactory(user=user)
            ),
            2,
        )

        assert list(get_dashboard_applications(user)) == [
            new_open,
            old_open,
            new_rejected,
            old_approved,
        ]


@pytest.mark.django_db
class TestOrganisationForNewApplication:
    def test_a_course_with_one_owning_organisation_returns_it(
        self, mock_site_context: Site
    ) -> None:
        from freedom_ls.course_applications.queries import (
            organisation_for_new_application,
        )

        course = CourseFactory()
        owner = OrganisationFactory()
        course.organisations.add(owner)

        assert organisation_for_new_application(course) == owner

    @pytest.mark.parametrize("owner_count", [0, 2])
    def test_a_course_without_exactly_one_owner_returns_the_site_default(
        self, mock_site_context: Site, owner_count: int
    ) -> None:
        from freedom_ls.course_applications.queries import (
            organisation_for_new_application,
        )

        course = CourseFactory()
        course.organisations.add(*[OrganisationFactory() for _ in range(owner_count)])

        assert organisation_for_new_application(course) == get_default_organisation(
            course.site
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("traits", "expected"),
    [
        ({}, False),
        ({"withdrawn": True}, True),
        ({"rejected": True, "submitted_at": timezone.now()}, True),
    ],
)
def test_sitting_belongs_to_a_non_draft_application(
    mock_site_context: Site, traits: dict[str, object], expected: bool
) -> None:
    from freedom_ls.course_applications.queries import (
        sitting_belongs_to_a_non_draft_application,
    )

    sitting = FormProgressFactory(completed_time=None)
    CourseApplicationFactory(form_progress=sitting, **traits)

    assert sitting_belongs_to_a_non_draft_application(sitting) is expected


@pytest.mark.django_db
def test_a_sitting_with_no_application_is_not_locked_by_applications(
    mock_site_context: Site,
) -> None:
    from freedom_ls.course_applications.queries import (
        sitting_belongs_to_a_non_draft_application,
    )

    assert not sitting_belongs_to_a_non_draft_application(
        FormProgressFactory(completed_time=None)
    )
