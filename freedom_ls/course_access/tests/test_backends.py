"""Tests for course_access backends."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
import time_machine

from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.test import RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.course_access.backends import (
    CourseAccessBackend,
    DeadlineEnforcingBackend,
    FreeOnlyCourseAccessBackend,
    VisibilityEnforcingBackend,
)
from freedom_ls.course_access.loader import get_course_access_backend
from freedom_ls.deadlines.factories import (
    CohortDeadlineOverrideFactory,
    CourseDeadlineConfigFactory,
    LearnerDeadlineOverrideFactory,
)
from freedom_ls.deadlines.models import AfterAccessEnded, DeadlineKind
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
)
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.learner_progress.tests.helpers import course_progress_record


class TestCourseAccessBackend:
    """The base class raises NotImplementedError for its abstract methods."""

    def test_get_access_raises(self):
        from freedom_ls.course_access.backends import CourseAccessBackend

        backend = CourseAccessBackend()
        with pytest.raises(NotImplementedError):
            backend.get_access(user=None, course=None)

    def test_get_access_for_request_raises(self):
        from freedom_ls.course_access.backends import CourseAccessBackend

        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        backend = CourseAccessBackend()
        with pytest.raises(NotImplementedError):
            backend.get_access_for_request(request=request, course=None)

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

    def test_get_dashboard_contributions_for_request_returns_empty_list(self):
        from freedom_ls.course_access.backends import CourseAccessBackend

        request = RequestFactory().get("/")
        request.user = AnonymousUser()

        result = CourseAccessBackend().get_dashboard_contributions_for_request(
            request=request
        )

        assert result == []

    def test_get_dashboard_contributions_for_request_keeps_anonymous_users_away(
        self,
    ):
        """A backend whose panels assume a signed-in user never sees a visitor."""
        from freedom_ls.course_access.backends import CourseAccessBackend

        class SignedInOnlyBackend(CourseAccessBackend):
            def get_dashboard_contributions(self, *, user):
                raise AssertionError("called with an anonymous user")

        request = RequestFactory().get("/")
        request.user = AnonymousUser()

        result = SignedInOnlyBackend().get_dashboard_contributions_for_request(
            request=request
        )

        assert result == []


@pytest.mark.django_db
class TestFreeOnlyCourseAccessBackendGetAccessForRequest:
    """FreeOnlyCourseAccessBackend.get_access_for_request decides by user alone."""

    def test_anonymous_request_gets_the_get_access_decision(self, mock_site_context):
        from django.contrib.auth.models import AnonymousUser

        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        course = CourseFactory(access_config={"access_type": "free"})
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        backend = FreeOnlyCourseAccessBackend()

        decision = backend.get_access_for_request(request=request, course=course)

        assert decision == backend.get_access(user=request.user, course=course)

    def test_registered_user_request_gets_the_get_access_decision(
        self, mock_site_context
    ):
        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        course = CourseFactory(access_config={"access_type": "free"})
        user = UserFactory()
        LearnerCourseRegistrationFactory(
            learner__user=user, course=course, is_active=True
        )
        request = RequestFactory().get("/")
        request.user = user
        backend = FreeOnlyCourseAccessBackend()

        decision = backend.get_access_for_request(request=request, course=course)

        assert decision == backend.get_access(user=user, course=course)


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

    def test_application_form_rejected_by_default_backend(self):
        """application_form belongs to the applications backend's key vocabulary."""
        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        backend = FreeOnlyCourseAccessBackend()
        with pytest.raises(ValueError, match="unknown key"):
            backend.validate_course_config(
                {"access_type": "free", "application_form": "../form.md"}
            )

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

    def test_anonymous_user_on_free_course_gets_enrol_for_free_cta(
        self, mock_site_context
    ):
        from django.contrib.auth.models import AnonymousUser

        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        course = CourseFactory(access_config={"access_type": "free"})
        backend = FreeOnlyCourseAccessBackend()
        decision = backend.get_access(user=AnonymousUser(), course=course)

        assert decision.cta_label == "Enrol for free"
        assert decision.can_self_register is True
        assert decision.can_access_content is False

    def test_free_decision_is_accessible_for_free(self, mock_site_context):
        from django.contrib.auth.models import AnonymousUser

        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        course = CourseFactory(access_config={"access_type": "free"})
        backend = FreeOnlyCourseAccessBackend()
        decision = backend.get_access(user=AnonymousUser(), course=course)

        assert decision.is_accessible_for_free is True

    def test_registered_free_decision_is_accessible_for_free(self, mock_site_context):
        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend
        from freedom_ls.learner_management.factories import (
            LearnerCourseRegistrationFactory,
        )

        course = CourseFactory(access_config={"access_type": "free"})
        user = UserFactory()
        LearnerCourseRegistrationFactory(
            learner__user=user, course=course, is_active=True
        )
        backend = FreeOnlyCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        assert decision.is_accessible_for_free is True

    def test_is_accessible_for_free_is_true_with_no_queries(
        self, mock_site_context, django_assert_num_queries
    ):
        """The config-only free signal returns True and issues no per-user queries."""
        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        course = CourseFactory(access_config={"access_type": "free"})
        backend = FreeOnlyCourseAccessBackend()

        with django_assert_num_queries(0):
            assert backend.is_accessible_for_free(course=course) is True

    def test_access_badge_reads_free_with_no_queries(
        self, mock_site_context, django_assert_num_queries
    ):
        """The config-only badge reads "Free" and issues no per-user queries."""
        from freedom_ls.course_access.backends import (
            AccessBadge,
            FreeOnlyCourseAccessBackend,
        )

        course = CourseFactory(access_config={"access_type": "free"})
        backend = FreeOnlyCourseAccessBackend()

        with django_assert_num_queries(0):
            assert backend.get_access_badge(course=course) == AccessBadge(label="Free")

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
            "learner_interface:initiate_course_access",
            kwargs={"course_slug": "my-course"},
        )
        assert decision.cta_url == expected_url

    def test_registered_user_gets_continue_cta(self, mock_site_context):
        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        course = CourseFactory(access_config={"access_type": "free"})
        user = UserFactory()
        LearnerCourseRegistrationFactory(
            learner__user=user, course=course, is_active=True
        )
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
        LearnerCourseRegistrationFactory(
            learner__user=user, course=course, is_active=True
        )
        backend = FreeOnlyCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        expected_url = reverse(
            "learner_interface:course_home",
            kwargs={"course_slug": "my-course"},
        )
        assert decision.cta_url == expected_url

    def test_cohort_registered_user_gets_continue(self, mock_site_context):
        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        course = CourseFactory(access_config={"access_type": "free"})
        user = UserFactory()
        cohort = CohortFactory()
        CohortMembershipFactory(learner__user=user, cohort=cohort)
        CohortCourseRegistrationFactory(cohort=cohort, course=course, is_active=True)
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

    def test_get_dashboard_contributions_for_request_returns_empty_list(
        self, mock_site_context
    ):
        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        request = RequestFactory().get("/")
        request.user = AnonymousUser()

        result = FreeOnlyCourseAccessBackend().get_dashboard_contributions_for_request(
            request=request
        )

        assert result == []


class TestGetAccessType:
    def test_base_class_raises(self):
        from freedom_ls.course_access.backends import CourseAccessBackend

        backend = CourseAccessBackend()
        with pytest.raises(NotImplementedError):
            backend.get_access_type(course=None)

    @pytest.mark.django_db
    def test_free_only_backend_reports_free(self, mock_site_context):
        from freedom_ls.course_access.backends import FreeOnlyCourseAccessBackend

        course = CourseFactory(access_config={"access_type": "free"})

        assert FreeOnlyCourseAccessBackend().get_access_type(course=course) == "free"


REGISTERED_AT = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
BEFORE_END = datetime(2026, 3, 20, 10, 0, tzinfo=UTC)
AFTER_END = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)


def _time_limited_course(*, items: int = 1, end_access: str = "on") -> Course:
    """A course with a 30-day time limit whose policy sets ``end_course_access``."""
    course: Course = CourseFactory(time_limit_days=30)
    for order in range(items):
        course.items.create(child=TopicFactory(), order=order)
    CourseDeadlineConfigFactory(
        course=course,
        end_course_access=end_access,
        after_access_ended=AfterAccessEnded.NOTHING,
    )
    return course


def _registered_learner(course: Course) -> User:
    user: User = UserFactory()
    course_progress_record(course, user, created_at=REGISTERED_AT)
    return user


def _deadline_backend() -> DeadlineEnforcingBackend:
    return DeadlineEnforcingBackend(FreeOnlyCourseAccessBackend())


def test_deadline_wrapper_overrides_every_backend_method():
    """A method the wrapper does not override falls back to the base default,
    skipping the inner backend's own logic without any error."""
    backend_methods = {
        name
        for name, value in vars(CourseAccessBackend).items()
        if callable(value) and not name.startswith("_")
    }

    assert backend_methods - set(vars(DeadlineEnforcingBackend)) == set()


@pytest.mark.django_db
def test_loader_wraps_the_deadline_backend_inside_the_visibility_backend(
    mock_site_context,
):
    get_course_access_backend.cache_clear()

    backend = get_course_access_backend()

    assert isinstance(backend, VisibilityEnforcingBackend)
    assert isinstance(backend._inner, DeadlineEnforcingBackend)


@pytest.mark.django_db
class TestDeadlineEnforcingBackendGetAccess:
    @time_machine.travel(AFTER_END, tick=False)
    def test_an_ended_learner_loses_content_and_every_affordance(
        self, mock_site_context
    ):
        course = _time_limited_course()
        user = _registered_learner(course)

        decision = _deadline_backend().get_access(user=user, course=course)

        assert decision.can_access_content is False
        assert decision.can_self_register is False
        assert decision.cta_label is None
        assert decision.cta_url is None

    @time_machine.travel(AFTER_END, tick=False)
    def test_an_ended_decision_names_the_end_and_what_follows(self, mock_site_context):
        course = _time_limited_course()
        user = _registered_learner(course)

        decision = _deadline_backend().get_access(user=user, course=course)

        assert decision.access_ended_at == datetime(
            2026, 3, 31, 23, 59, 59, 999999, tzinfo=UTC
        )
        assert decision.after_access_ended == AfterAccessEnded.NOTHING

    @time_machine.travel(AFTER_END, tick=False)
    def test_an_ended_decision_keeps_the_inner_funnel_copy(self, mock_site_context):
        course = _time_limited_course()
        user = _registered_learner(course)
        inner = FreeOnlyCourseAccessBackend().get_access(user=user, course=course)

        decision = _deadline_backend().get_access(user=user, course=course)

        assert decision.enrolment_summary == inner.enrolment_summary
        assert decision.acquisition_heading == inner.acquisition_heading
        assert decision.acquisition_subtext == inner.acquisition_subtext

    @time_machine.travel(BEFORE_END, tick=False)
    def test_before_the_end_the_inner_decision_stands(self, mock_site_context):
        course = _time_limited_course()
        user = _registered_learner(course)

        decision = _deadline_backend().get_access(user=user, course=course)

        assert decision == FreeOnlyCourseAccessBackend().get_access(
            user=user, course=course
        )

    @time_machine.travel(AFTER_END, tick=False)
    def test_the_inner_decision_stands_while_ending_access_is_off(
        self, mock_site_context
    ):
        course = _time_limited_course(end_access="off")
        user = _registered_learner(course)

        decision = _deadline_backend().get_access(user=user, course=course)

        assert decision.can_access_content is True
        assert decision.access_ended_at is None

    @time_machine.travel(AFTER_END, tick=False)
    def test_a_completed_course_never_ends(self, mock_site_context):
        course = _time_limited_course()
        user = _registered_learner(course)
        course_progress_record(course, user, completed_time=BEFORE_END)

        decision = _deadline_backend().get_access(user=user, course=course)

        assert decision.can_access_content is True

    @time_machine.travel(AFTER_END, tick=False)
    def test_a_deactivated_registration_gets_the_inner_decision(
        self, mock_site_context
    ):
        course = _time_limited_course()
        user = _registered_learner(course)
        LearnerCourseRegistration.objects.update(is_active=False)

        decision = _deadline_backend().get_access(user=user, course=course)

        assert decision == FreeOnlyCourseAccessBackend().get_access(
            user=user, course=course
        )
        assert decision.access_ended_at is None

    @time_machine.travel(AFTER_END, tick=False)
    def test_an_unregistered_user_gets_the_inner_decision(self, mock_site_context):
        course = _time_limited_course()

        decision = _deadline_backend().get_access(user=UserFactory(), course=course)

        assert decision.access_ended_at is None
        assert decision.can_self_register is True

    @time_machine.travel(AFTER_END, tick=False)
    def test_the_free_override_bypasses_the_deadline_wrapper(self, mock_site_context):
        course = _time_limited_course()
        user = _registered_learner(course)

        with override_settings(OVERRIDE_COURSE_ACCESS_TO_FREE=True):
            get_course_access_backend.cache_clear()
            decision = get_course_access_backend().get_access(user=user, course=course)
        get_course_access_backend.cache_clear()

        assert decision.can_access_content is True
        assert decision.access_ended_at is None

    @time_machine.travel(AFTER_END, tick=False)
    def test_get_access_for_request_sees_the_ended_state(self, mock_site_context):
        course = _time_limited_course()
        request = RequestFactory().get("/")
        request.user = _registered_learner(course)

        decision = _deadline_backend().get_access_for_request(
            request=request, course=course
        )

        assert decision.can_access_content is False
        assert decision.access_ended_at is not None

    def test_an_anonymous_request_goes_straight_to_the_inner_backend(
        self, mock_site_context
    ):
        course = CourseFactory()
        request = RequestFactory().get("/")
        request.user = AnonymousUser()

        decision = _deadline_backend().get_access_for_request(
            request=request, course=course
        )

        assert decision == FreeOnlyCourseAccessBackend().get_access_for_request(
            request=request, course=course
        )

    @time_machine.travel(AFTER_END, tick=False)
    @pytest.mark.parametrize("items", [1, 30])
    def test_get_access_stays_within_a_fixed_query_budget(
        self, mock_site_context, django_assert_max_num_queries, items
    ):
        course = _time_limited_course(items=items)
        user = _registered_learner(course)

        with django_assert_max_num_queries(18):
            _deadline_backend().get_access(user=user, course=course)

    @time_machine.travel(AFTER_END, tick=False)
    def test_a_refused_decision_costs_no_more_than_the_inner_backend(
        self, mock_site_context
    ):
        course = _time_limited_course()
        user = UserFactory()
        with CaptureQueriesContext(connection) as inner_queries:
            FreeOnlyCourseAccessBackend().get_access(user=user, course=course)

        with CaptureQueriesContext(connection) as wrapped_queries:
            _deadline_backend().get_access(user=user, course=course)

        assert len(wrapped_queries) <= len(inner_queries)


@pytest.mark.django_db
class TestDeadlineEnforcingBackendGetAccessMany:
    @time_machine.travel(AFTER_END, tick=False)
    def test_each_course_gets_the_decision_get_access_would_give(
        self, mock_site_context
    ):
        ending = _time_limited_course()
        open_ended = _time_limited_course(end_access="off")
        user = _registered_learner(ending)
        course_progress_record(open_ended, user, created_at=REGISTERED_AT)
        unregistered = CourseFactory()
        courses = [ending, open_ended, unregistered]
        backend = _deadline_backend()

        many = backend.get_access_many(user=user, courses=courses)

        assert many == {
            course.pk: backend.get_access(user=user, course=course)
            for course in courses
        }
        assert many[ending.pk].access_ended_at is not None

    @time_machine.travel(AFTER_END, tick=False)
    def test_query_count_does_not_grow_with_the_number_of_courses(
        self, mock_site_context, django_assert_max_num_queries
    ):
        user = UserFactory()
        courses = []
        for _ in range(6):
            course = _time_limited_course()
            course_progress_record(course, user, created_at=REGISTERED_AT)
            courses.append(course)

        with django_assert_max_num_queries(25):
            _deadline_backend().get_access_many(user=user, courses=courses)


@pytest.mark.django_db
class TestDeadlineEnforcingBackendRestore:
    """A later fixed-date time limit restores access with no write to the record."""

    @time_machine.travel(AFTER_END, tick=False)
    def test_a_learner_override_restores_access(self, mock_site_context):
        course = _time_limited_course()
        user = _registered_learner(course)
        record = course_progress_record(course, user)
        LearnerDeadlineOverrideFactory(
            course_progress=record,
            kind=DeadlineKind.FIXED,
            due_date=date(2999, 1, 1),
            due_days_after_registration=None,
        )

        decision = _deadline_backend().get_access(user=user, course=course)

        assert decision.can_access_content is True
        assert decision.access_ended_at is None

    @time_machine.travel(AFTER_END, tick=False)
    def test_a_cohort_override_restores_a_cohort_member(self, mock_site_context):
        course = _time_limited_course()
        cohort = CohortFactory()
        user = UserFactory()
        CohortMembershipFactory(
            learner__user=user, learner__organisation=cohort.organisation, cohort=cohort
        )
        registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
        course_progress_record(course, user, created_at=REGISTERED_AT)
        assert _deadline_backend().get_access(user=user, course=course).access_ended_at
        CohortDeadlineOverrideFactory(
            cohort_registration=registration,
            kind=DeadlineKind.FIXED,
            due_date=date(2999, 1, 1),
            due_days_after_registration=None,
        )

        decision = _deadline_backend().get_access(user=user, course=course)

        assert decision.can_access_content is True
