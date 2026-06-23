"""Tests for course_access backends."""

from __future__ import annotations

import dataclasses

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    UserCourseRegistrationFactory,
)


class TestCourseAccessDecision:
    """The CourseAccessDecision frozen dataclass contract."""

    def test_decision_is_frozen(self):
        from freedom_ls.course_access.backends import CourseAccessDecision

        decision = CourseAccessDecision(
            cta_label="Start",
            cta_url="/enrol/",
            can_self_register=True,
            can_access_content=False,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            decision.cta_label = "Changed"

    def test_decision_fields(self):
        from freedom_ls.course_access.backends import CourseAccessDecision

        decision = CourseAccessDecision(
            cta_label=None,
            cta_url=None,
            can_self_register=False,
            can_access_content=False,
        )
        assert decision.cta_label is None
        assert decision.cta_url is None
        assert decision.can_self_register is False
        assert decision.can_access_content is False

    def test_acquisition_copy_defaults_to_none(self):
        """The acquisition-copy fields are optional and default to None.

        A backend that supplies no funnel copy (e.g. an invalid-config safe
        decision) leaves them unset and the detail page omits those lines.
        """
        from freedom_ls.course_access.backends import CourseAccessDecision

        decision = CourseAccessDecision(
            cta_label=None,
            cta_url=None,
            can_self_register=False,
            can_access_content=False,
        )
        assert decision.enrolment_summary is None
        assert decision.acquisition_heading is None
        assert decision.acquisition_subtext is None


class TestDashboardContribution:
    """The DashboardContribution dataclass."""

    def test_contribution_fields(self):
        from freedom_ls.course_access.backends import DashboardContribution

        contrib = DashboardContribution(
            template_name="myapp/partials/panel.html",
            context={"items": [1, 2, 3]},
        )
        assert contrib.template_name == "myapp/partials/panel.html"
        assert contrib.context == {"items": [1, 2, 3]}

    def test_contribution_is_frozen(self):
        from freedom_ls.course_access.backends import DashboardContribution

        contrib = DashboardContribution(template_name="a.html", context={})
        with pytest.raises(dataclasses.FrozenInstanceError):
            contrib.template_name = "b.html"


class TestCourseAccessBackend:
    """The base class raises NotImplementedError for its abstract methods."""

    def test_get_access_raises(self):
        from freedom_ls.course_access.backends import CourseAccessBackend

        backend = CourseAccessBackend()
        with pytest.raises(NotImplementedError):
            backend.get_access(user=None, course=None)

    def test_filter_visible_raises(self):
        from freedom_ls.course_access.backends import CourseAccessBackend

        backend = CourseAccessBackend()
        with pytest.raises(NotImplementedError):
            backend.filter_visible(user=None, courses=None)

    def test_validate_course_config_raises(self):
        from freedom_ls.course_access.backends import CourseAccessBackend

        backend = CourseAccessBackend()
        with pytest.raises(NotImplementedError):
            backend.validate_course_config({})

    def test_get_dashboard_contributions_returns_empty_list(self):
        """Base class returns [] by default — subclasses that add no panels need no override."""
        from freedom_ls.course_access.backends import CourseAccessBackend

        backend = CourseAccessBackend()
        result = backend.get_dashboard_contributions(user=None)
        assert result == []


class TestFreeOnlyCourseAccessBackendValidate:
    """FreeOnlyCourseAccessBackend.validate_course_config."""

    def test_empty_config_defaults_to_free(self):
        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        backend = FreeOnlyCourseAccessBackend()
        result = backend.validate_course_config({})
        assert result == {"access_type": "free"}

    def test_explicit_free_is_accepted(self):
        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        backend = FreeOnlyCourseAccessBackend()
        result = backend.validate_course_config({"access_type": "free"})
        assert result == {"access_type": "free"}

    def test_unknown_key_raises_value_error(self):
        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        backend = FreeOnlyCourseAccessBackend()
        with pytest.raises(ValueError, match="unknown key"):
            backend.validate_course_config({"access_type": "free", "unexpected": True})

    def test_unknown_access_type_raises_value_error(self):
        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        backend = FreeOnlyCourseAccessBackend()
        with pytest.raises(ValueError, match="invalid access_type"):
            backend.validate_course_config({"access_type": "not_a_real_type"})

    def test_application_gated_rejected_by_default_backend(self):
        """application_gated is NOT a core value — the applications backend extends this."""
        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        backend = FreeOnlyCourseAccessBackend()
        with pytest.raises(ValueError, match="application_gated"):
            backend.validate_course_config({"access_type": "application_gated"})

    def test_file_path_included_in_error_message(self):
        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        backend = FreeOnlyCourseAccessBackend()
        # Use re.escape pattern for the literal file path (contains regex metacharacters)
        with pytest.raises(ValueError, match=r"courses/my-course\.md"):
            backend.validate_course_config(
                {"access_type": "bad"}, file_path="courses/my-course.md"
            )


@pytest.mark.django_db
class TestFreeOnlyCourseAccessBackendGetAccess:
    """FreeOnlyCourseAccessBackend.get_access."""

    def test_anonymous_user_on_free_course_gets_start_cta(self, mock_site_context):
        from django.contrib.auth.models import AnonymousUser

        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        course = CourseFactory(access_config={"access_type": "free"})
        backend = FreeOnlyCourseAccessBackend()
        decision = backend.get_access(user=AnonymousUser(), course=course)

        assert decision.cta_label == "Start"
        assert decision.can_self_register is True
        assert decision.can_access_content is False

    def test_free_course_decision_carries_free_acquisition_copy(
        self, mock_site_context
    ):
        """A free course's decision carries the free funnel copy (not hardcoded in the template)."""
        from django.contrib.auth.models import AnonymousUser

        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        course = CourseFactory(access_config={"access_type": "free"})
        backend = FreeOnlyCourseAccessBackend()
        decision = backend.get_access(user=AnonymousUser(), course=course)

        assert decision.enrolment_summary == "Free · open"
        assert decision.acquisition_heading == "Free · open to everyone"
        assert decision.acquisition_subtext == "One click. No credit card."

    def test_anonymous_user_start_url_points_to_register(self, mock_site_context):
        from django.contrib.auth.models import AnonymousUser
        from django.urls import reverse

        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        course = CourseFactory(slug="my-course", access_config={"access_type": "free"})
        backend = FreeOnlyCourseAccessBackend()
        decision = backend.get_access(user=AnonymousUser(), course=course)

        expected_url = reverse(
            "student_interface:initiate_course_access",
            kwargs={"course_slug": "my-course"},
        )
        assert decision.cta_url == expected_url

    def test_registered_user_gets_continue_cta(self, mock_site_context):
        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        course = CourseFactory(access_config={"access_type": "free"})
        user = UserFactory()
        UserCourseRegistrationFactory(user=user, collection=course, is_active=True)
        backend = FreeOnlyCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        assert decision.cta_label == "Continue"
        assert decision.can_access_content is True
        assert decision.can_self_register is False

    def test_registered_user_continue_url_points_to_course_home(
        self, mock_site_context
    ):
        from django.urls import reverse

        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        course = CourseFactory(slug="my-course", access_config={"access_type": "free"})
        user = UserFactory()
        UserCourseRegistrationFactory(user=user, collection=course, is_active=True)
        backend = FreeOnlyCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        expected_url = reverse(
            "student_interface:course_home",
            kwargs={"course_slug": "my-course"},
        )
        assert decision.cta_url == expected_url

    def test_cohort_registered_user_gets_continue(self, mock_site_context):
        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        course = CourseFactory(access_config={"access_type": "free"})
        user = UserFactory()
        cohort = CohortFactory()
        CohortMembershipFactory(user=user, cohort=cohort)
        CohortCourseRegistrationFactory(
            cohort=cohort, collection=course, is_active=True
        )
        backend = FreeOnlyCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        assert decision.can_access_content is True

    def test_invalid_config_returns_no_action_decision(self, mock_site_context):
        from django.contrib.auth.models import AnonymousUser

        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        course = CourseFactory(access_config={"access_type": "bad_value"})
        backend = FreeOnlyCourseAccessBackend()
        decision = backend.get_access(user=AnonymousUser(), course=course)

        assert decision.cta_label is None
        assert decision.cta_url is None
        assert decision.can_self_register is False
        assert decision.can_access_content is False
        # No funnel copy on a no-action decision — the detail page omits it.
        assert decision.enrolment_summary is None
        assert decision.acquisition_heading is None
        assert decision.acquisition_subtext is None

    def test_get_dashboard_contributions_returns_empty_list(self, mock_site_context):
        from django.contrib.auth.models import AnonymousUser

        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        backend = FreeOnlyCourseAccessBackend()
        result = backend.get_dashboard_contributions(user=AnonymousUser())
        assert result == []
