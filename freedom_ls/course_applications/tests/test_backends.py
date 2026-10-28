"""Tests for ApplicationCourseAccessBackend."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import cast

import pytest

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.form_engine.factories import FormProgressFactory
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.content_engine.models import Course
from freedom_ls.course_applications.anonymous_session import (
    remember_anonymous_applicant,
)
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import (
    AnonymousApplicant,
    CourseApplication,
)


@pytest.mark.django_db
class TestValidateCourseConfig:
    """validate_course_config on ApplicationCourseAccessBackend."""

    def test_application_gated_is_accepted(self, mock_site_context):
        """validate_course_config accepts access_type=application_gated."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        backend = ApplicationCourseAccessBackend()
        result = backend.validate_course_config({"access_type": "application_gated"})
        assert result == {"access_type": "application_gated"}

    def test_free_is_accepted(self, mock_site_context):
        """validate_course_config accepts access_type=free (inherited from parent)."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        backend = ApplicationCourseAccessBackend()
        result = backend.validate_course_config({"access_type": "free"})
        assert result == {"access_type": "free"}

    def test_absent_access_type_defaults_to_free(self, mock_site_context):
        """validate_course_config with absent access_type defaults to free."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        backend = ApplicationCourseAccessBackend()
        result = backend.validate_course_config({})
        assert result["access_type"] == "free"

    def test_unknown_access_type_raises_value_error(self, mock_site_context):
        """validate_course_config rejects an unknown access_type value."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        backend = ApplicationCourseAccessBackend()
        with pytest.raises(ValueError, match="invalid access_type"):
            backend.validate_course_config({"access_type": "subscription"})

    def test_unknown_key_raises_value_error(self, mock_site_context):
        """validate_course_config rejects unknown keys."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        backend = ApplicationCourseAccessBackend()
        with pytest.raises(ValueError, match="unknown key"):
            backend.validate_course_config({"unknown_key": "value"})

    def test_an_application_form_survives_normalisation(self, mock_site_context):
        """The content loader reads the path back off the normalised config to bind
        Course.application_form, so dropping it here would silently unbind the form.
        """
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        backend = ApplicationCourseAccessBackend()
        result = backend.validate_course_config(
            {
                "access_type": "application_gated",
                "application_form": "../application_form/form.md",
            }
        )
        assert result == {
            "access_type": "application_gated",
            "application_form": "../application_form/form.md",
        }

    def test_an_application_form_on_a_free_course_raises_value_error(
        self, mock_site_context
    ):
        """Naming a form a free course will never show anyone is an authoring
        mistake, not a harmless extra key.
        """
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        backend = ApplicationCourseAccessBackend()
        with pytest.raises(ValueError, match="only valid with access_type"):
            backend.validate_course_config(
                {"access_type": "free", "application_form": "../form.md"}
            )

    @pytest.mark.parametrize("form_path", ["", "   ", 7, None, ["../form.md"]])
    def test_an_application_form_that_is_not_a_path_raises_value_error(
        self, mock_site_context, form_path
    ):
        """Nested in the JSON blob the value gets no pydantic coercion, so this is
        the only thing standing between a mistyped path and a confusing load error.
        """
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        backend = ApplicationCourseAccessBackend()
        with pytest.raises(ValueError, match="invalid application_form"):
            backend.validate_course_config(
                {"access_type": "application_gated", "application_form": form_path}
            )

    def test_file_path_included_in_error_message(self, mock_site_context):
        """ValueError for invalid config includes the file_path context."""
        import re

        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        backend = ApplicationCourseAccessBackend()
        with pytest.raises(ValueError, match=re.escape("some/file.yaml")):
            backend.validate_course_config(
                {"access_type": "bad_value"}, file_path="some/file.yaml"
            )


@pytest.mark.django_db
class TestGetAccess:
    """get_access on ApplicationCourseAccessBackend."""

    def test_application_gated_course_returns_apply_now_cta(self, mock_site_context):
        """get_access for an application-gated course returns 'Apply now' CTA."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        course = CourseFactory()
        course.access_config = {"access_type": "application_gated"}
        course.save()

        backend = ApplicationCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        assert decision.cta_label == "Apply now"

    def test_application_gated_cta_url_points_to_apply_view(self, mock_site_context):
        """get_access for application-gated course CTA URL points to apply view."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        course = CourseFactory()
        course.access_config = {"access_type": "application_gated"}
        course.save()

        backend = ApplicationCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        expected_url = reverse(
            "course_applications:apply", kwargs={"course_slug": course.slug}
        )
        assert decision.cta_url == expected_url

    def test_application_gated_cannot_self_register(self, mock_site_context):
        """get_access for application-gated course sets can_self_register=False."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        course = CourseFactory()
        course.access_config = {"access_type": "application_gated"}
        course.save()

        backend = ApplicationCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        assert decision.can_self_register is False

    def test_application_gated_cannot_access_content(self, mock_site_context):
        """get_access for application-gated course sets can_access_content=False."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        course = CourseFactory()
        course.access_config = {"access_type": "application_gated"}
        course.save()

        backend = ApplicationCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        assert decision.can_access_content is False

    def test_registered_learner_on_gated_course_gets_content(self, mock_site_context):
        """A learner enrolled into a gated course (admin/cohort) bypasses the gate.

        Admin/cohort enrolment deliberately bypasses the application gate, so a
        registered learner reaches content (Continue/can_access_content) rather
        than being told to "Apply now".
        """
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )
        from freedom_ls.learner_management.factories import (
            LearnerCourseRegistrationFactory,
        )

        user = UserFactory()
        course = CourseFactory()
        course.access_config = {"access_type": "application_gated"}
        course.save()
        LearnerCourseRegistrationFactory(
            learner__user=user, course=course, is_active=True
        )

        backend = ApplicationCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        assert decision.cta_label == "Continue"
        assert decision.can_access_content is True
        assert decision.can_self_register is False

    def test_application_gated_carries_application_acquisition_copy(
        self, mock_site_context
    ):
        """A gated course's decision carries application-funnel copy, not the free copy.

        The detail page must not claim a gated course is "Free · open" with
        "One click. No credit card." The copy comes from the backend decision.
        """
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        course = CourseFactory()
        course.access_config = {"access_type": "application_gated"}
        course.save()

        backend = ApplicationCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        assert decision.enrolment_summary == "By application"
        assert decision.acquisition_heading == "Application required"
        assert decision.acquisition_subtext == "Apply and we'll review your request."

    def test_existing_applicant_gets_view_my_application_cta(self, mock_site_context):
        """An unregistered learner who has already applied sees 'View my application'."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        course = CourseFactory()
        course.access_config = {"access_type": "application_gated"}
        course.save()
        app = CourseApplicationFactory(user=user, course=course)

        backend = ApplicationCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        expected_url = reverse("course_applications:status", kwargs={"pk": app.pk})
        assert decision.cta_label == "View my application"
        assert decision.cta_url == expected_url

    def test_no_application_still_returns_apply_now(self, mock_site_context):
        """An unregistered learner without an application still sees 'Apply now'."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        course = CourseFactory()
        course.access_config = {"access_type": "application_gated"}
        course.save()

        backend = ApplicationCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        assert decision.cta_label == "Apply now"

    def test_free_course_returns_enrol_for_free_cta(self, mock_site_context):
        """get_access for free course returns 'Enrol for free' CTA (inherited from parent)."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        course = CourseFactory()
        course.access_config = {"access_type": "free"}
        course.save()

        backend = ApplicationCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        assert decision.cta_label == "Enrol for free"
        assert decision.can_self_register is True

    def test_apply_now_decision_is_not_accessible_for_free(self, mock_site_context):
        """The 'Apply now' decision signals the course is not freely accessible."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        course = CourseFactory()
        course.access_config = {"access_type": "application_gated"}
        course.save()

        backend = ApplicationCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        assert decision.cta_label == "Apply now"
        assert decision.is_accessible_for_free is False

    def test_view_my_application_decision_is_not_accessible_for_free(
        self, mock_site_context
    ):
        """The 'View my application' decision signals the course is not freely accessible."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        course = CourseFactory()
        course.access_config = {"access_type": "application_gated"}
        course.save()
        app = CourseApplicationFactory(user=user, course=course)

        backend = ApplicationCourseAccessBackend()
        decision = backend.get_access(user=user, course=course)

        assert decision.cta_label == "View my application"
        assert decision.is_accessible_for_free is False
        assert decision.cta_url == reverse(
            "course_applications:status", kwargs={"pk": app.pk}
        )


@pytest.mark.django_db
class TestGetDashboardContributions:
    """get_dashboard_contributions on ApplicationCourseAccessBackend."""

    def test_returns_one_contribution_when_learner_has_active_application(
        self, mock_site_context
    ):
        """get_dashboard_contributions returns one contribution for a learner with an application."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        CourseApplicationFactory(user=user)

        backend = ApplicationCourseAccessBackend()
        contributions = backend.get_dashboard_contributions(user=user)

        assert len(contributions) == 1

    def test_contribution_template_is_dashboard_applications_partial(
        self, mock_site_context
    ):
        """The contribution uses the dashboard_applications partial template."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        CourseApplicationFactory(user=user)

        backend = ApplicationCourseAccessBackend()
        contributions = backend.get_dashboard_contributions(user=user)

        assert (
            contributions[0].template_name
            == "course_applications/partials/dashboard_applications.html"
        )

    def test_contribution_context_contains_applications(self, mock_site_context):
        """The contribution context includes the learner's applications."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        app = CourseApplicationFactory(user=user)

        backend = ApplicationCourseAccessBackend()
        contributions = backend.get_dashboard_contributions(user=user)
        apps = list(contributions[0].context["applications"])

        assert app in apps

    def test_returns_empty_list_when_no_applications(self, mock_site_context):
        """get_dashboard_contributions returns empty list when learner has no applications."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()

        backend = ApplicationCourseAccessBackend()
        contributions = backend.get_dashboard_contributions(user=user)

        assert contributions == []


@pytest.mark.django_db
class TestDashboardPartialRendering:
    """The dashboard_applications partial renders status links."""

    def test_partial_renders_status_link(self, client, mock_site_context):
        """Dashboard applications partial renders a link to the application status page."""
        user = UserFactory()
        app = CourseApplicationFactory(user=user)

        expected_url = reverse("course_applications:status", kwargs={"pk": app.pk})
        rendered = _render_panel(app)

        assert expected_url in rendered

    def test_an_application_with_no_form_is_pending_review(self, mock_site_context):
        rendered = _render_panel(CourseApplicationFactory())

        assert "Pending review" in rendered
        assert "Incomplete" not in rendered

    def test_a_draft_application_is_incomplete_not_pending(self, mock_site_context):
        """An application nobody has submitted is not waiting on a reviewer;
        it is waiting on the applicant, and the dashboard has to say so."""
        rendered = _render_panel(_application_with_sitting())

        assert "Incomplete" in rendered
        assert "Pending review" not in rendered

    def test_a_submitted_application_is_pending_review(self, mock_site_context):
        app = _application_with_sitting()
        app.form_progress.complete()

        rendered = _render_panel(app)

        assert "Pending review" in rendered
        assert "Incomplete" not in rendered

    def test_a_submitted_row_offers_view_my_application(self, mock_site_context):
        app = _application_with_sitting()
        app.form_progress.complete()

        rendered = _render_panel(app)

        assert "View my application" in rendered
        assert "Continue application" not in rendered
        assert "Finish your application to have it reviewed." not in rendered

    def test_a_draft_row_explains_what_is_left_and_offers_to_continue(
        self, mock_site_context
    ):
        rendered = _render_panel(_application_with_sitting())

        assert "Finish your application to have it reviewed." in rendered
        assert "Continue application" in rendered
        assert "View my application" not in rendered

    def test_the_button_names_its_course_for_screen_readers(self, mock_site_context):
        app = _application_with_sitting()

        rendered = _render_panel(app)

        assert f'<span class="sr-only"> for {app.course.title}</span>' in rendered

    def test_each_row_carries_a_decorative_chevron(self, mock_site_context):
        rendered = _render_panel(CourseApplicationFactory())

        assert re.search(r'<span[^>]*aria-hidden="true"[^>]*>\s*<svg', rendered)

    def test_a_course_title_is_escaped_in_the_link_the_button_and_the_icon(
        self, mock_site_context
    ):
        course = CourseFactory(title='A <b> "quoted" title')
        rendered = _render_panel(CourseApplicationFactory(course=course))

        assert "<b>" not in rendered
        assert rendered.count("A &lt;b&gt; &quot;quoted&quot; title") >= 3


def _application_with_sitting():
    from freedom_ls.form_engine.factories import FormFactory, FormProgressFactory
    from freedom_ls.form_engine.models import FormStrategy

    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.UNSCORED)
    return CourseApplicationFactory(
        user=user, form_progress=FormProgressFactory(user=user, form=form)
    )


def _render_panel(app) -> str:
    from django.template.loader import render_to_string

    from freedom_ls.course_applications.backends import ApplicationCourseAccessBackend

    contribution = ApplicationCourseAccessBackend().get_dashboard_contributions(
        user=app.user
    )[0]
    return render_to_string(
        contribution.template_name,
        contribution.context,
        request=RequestFactory().get("/dashboard/"),
    )


@pytest.mark.django_db
class TestGetAccessAnonymousUser:
    """get_access on ApplicationCourseAccessBackend with anonymous user."""

    def test_anonymous_user_on_gated_course_returns_apply_now_with_no_query(
        self, mock_site_context, django_assert_num_queries
    ):
        """Anonymous user on an application-gated course gets 'Apply now' with no application query."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        course = CourseFactory()
        course.access_config = {"access_type": "application_gated"}
        course.save()

        backend = ApplicationCourseAccessBackend()

        with django_assert_num_queries(0):
            decision = backend.get_access(user=AnonymousUser(), course=course)

        assert decision.cta_label == "Apply now"


@pytest.mark.django_db
class TestGetDashboardContributionsAnonymousUser:
    """get_dashboard_contributions on ApplicationCourseAccessBackend with anonymous user."""

    def test_anonymous_user_returns_empty_list(self, mock_site_context):
        """get_dashboard_contributions returns empty list for anonymous user."""
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        backend = ApplicationCourseAccessBackend()
        contributions = backend.get_dashboard_contributions(user=AnonymousUser())

        assert contributions == []


@pytest.mark.django_db
class TestIsAccessibleForFree:
    """ApplicationCourseAccessBackend.is_accessible_for_free (config-only, no queries)."""

    def test_free_course_is_accessible_for_free(
        self, mock_site_context, django_assert_num_queries
    ):
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        course = CourseFactory(access_config={"access_type": "free"})
        backend = ApplicationCourseAccessBackend()

        with django_assert_num_queries(0):
            assert backend.is_accessible_for_free(course=course) is True

    def test_gated_course_is_not_accessible_for_free(
        self, mock_site_context, django_assert_num_queries
    ):
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        course = CourseFactory(access_config={"access_type": "application_gated"})
        backend = ApplicationCourseAccessBackend()

        with django_assert_num_queries(0):
            assert backend.is_accessible_for_free(course=course) is False


@pytest.mark.django_db
class TestGetAccessBadge:
    """ApplicationCourseAccessBackend.get_access_badge (config-only, no queries)."""

    def test_free_course_badge_reads_free(
        self, mock_site_context, django_assert_num_queries
    ):
        from freedom_ls.course_access.backends import AccessBadge
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        course = CourseFactory(access_config={"access_type": "free"})
        backend = ApplicationCourseAccessBackend()

        with django_assert_num_queries(0):
            assert backend.get_access_badge(course=course) == AccessBadge(label="Free")

    def test_gated_course_badge_reads_by_application(
        self, mock_site_context, django_assert_num_queries
    ):
        from freedom_ls.course_access.backends import AccessBadge
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        course = CourseFactory(access_config={"access_type": "application_gated"})
        backend = ApplicationCourseAccessBackend()

        with django_assert_num_queries(0):
            assert backend.get_access_badge(course=course) == AccessBadge(
                label="By application"
            )


@pytest.mark.django_db
class TestGetAccessType:
    """ApplicationCourseAccessBackend.get_access_type (config-only, no queries)."""

    def test_free_course_reports_free(
        self, mock_site_context, django_assert_num_queries
    ):
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        course = CourseFactory(access_config={"access_type": "free"})
        backend = ApplicationCourseAccessBackend()

        with django_assert_num_queries(0):
            assert backend.get_access_type(course=course) == "free"

    def test_gated_course_reports_application_gated(
        self, mock_site_context, django_assert_num_queries
    ):
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        course = CourseFactory(access_config={"access_type": "application_gated"})
        backend = ApplicationCourseAccessBackend()

        with django_assert_num_queries(0):
            assert backend.get_access_type(course=course) == "application_gated"

    def test_invalid_config_reports_free(self, mock_site_context):
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        course = CourseFactory(access_config={"access_type": "no_such_type"})
        backend = ApplicationCourseAccessBackend()

        assert backend.get_access_type(course=course) == "free"


def _anonymous_request(*applicants: AnonymousApplicant):
    """An anonymous request whose session remembers each applicant."""
    request = RequestFactory().get("/")
    request.user = AnonymousUser()
    request.session = {}
    for applicant in applicants:
        remember_anonymous_applicant(request, applicant)
    return request


@pytest.mark.django_db
class TestGetAccessForRequest:
    """get_access_for_request on ApplicationCourseAccessBackend."""

    def test_session_holding_a_draft_gets_view_my_application(self, mock_site_context):
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        application = _application_with_sitting_anonymous()
        request = _anonymous_request(application.anonymous_applicant)

        decision = ApplicationCourseAccessBackend().get_access_for_request(
            request=request, course=application.course
        )

        assert decision.cta_label == "View my application"

    def test_session_holding_a_draft_points_at_the_status_page(self, mock_site_context):
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        application = _application_with_sitting_anonymous()
        request = _anonymous_request(application.anonymous_applicant)

        decision = ApplicationCourseAccessBackend().get_access_for_request(
            request=request, course=application.course
        )

        assert decision.cta_url == reverse(
            "course_applications:status", kwargs={"pk": application.pk}
        )

    def test_session_holding_a_submitted_application_gets_view_my_application(
        self, mock_site_context
    ):
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        application = CourseApplicationFactory(anonymous=True, course=_gated_course())
        request = _anonymous_request(application.anonymous_applicant)

        decision = ApplicationCourseAccessBackend().get_access_for_request(
            request=request, course=application.course
        )

        assert decision.cta_label == "View my application"

    def test_session_with_no_entry_gets_apply_now_without_a_query(
        self, mock_site_context, django_assert_max_num_queries
    ):
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        course = _gated_course()
        request = _anonymous_request()

        with django_assert_max_num_queries(0):
            decision = ApplicationCourseAccessBackend().get_access_for_request(
                request=request, course=course
            )

        assert decision.cta_label == "Apply now"

    def test_signed_in_request_gets_the_get_access_decision(self, mock_site_context):
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        application = CourseApplicationFactory(course=_gated_course())
        request = RequestFactory().get("/")
        request.user = application.user
        backend = ApplicationCourseAccessBackend()

        decision = backend.get_access_for_request(
            request=request, course=application.course
        )

        assert decision == backend.get_access(
            user=application.user, course=application.course
        )


def _gated_course() -> Course:
    return cast(
        Course, CourseFactory(access_config={"access_type": "application_gated"})
    )


def _application_with_sitting_anonymous() -> CourseApplication:
    return cast(
        CourseApplication,
        CourseApplicationFactory(
            anonymous=True,
            course=_gated_course(),
            form_progress=FormProgressFactory(user=None),
        ),
    )


def _anonymous_draft(*, created_at=None) -> CourseApplication:
    application = _application_with_sitting_anonymous()
    if created_at is not None:
        CourseApplication.objects.filter(pk=application.pk).update(
            created_at=created_at
        )
    return application


def _contributed_applications(request) -> list[CourseApplication]:
    from freedom_ls.course_applications.backends import ApplicationCourseAccessBackend

    contributions = (
        ApplicationCourseAccessBackend().get_dashboard_contributions_for_request(
            request=request
        )
    )
    return [a for c in contributions for a in c.context["applications"]]


@pytest.mark.django_db
class TestGetDashboardContributionsForRequest:
    """get_dashboard_contributions_for_request on ApplicationCourseAccessBackend."""

    def test_anonymous_session_gets_one_contribution(self, mock_site_context):
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        request = _anonymous_request(
            _anonymous_draft().anonymous_applicant,
            _anonymous_draft().anonymous_applicant,
        )

        contributions = (
            ApplicationCourseAccessBackend().get_dashboard_contributions_for_request(
                request=request
            )
        )

        assert len(contributions) == 1

    def test_anonymous_session_lists_its_drafts_newest_first(self, mock_site_context):
        older = _anonymous_draft(created_at=timezone.now() - timedelta(days=2))
        newer = _anonymous_draft(created_at=timezone.now() - timedelta(days=1))
        request = _anonymous_request(
            older.anonymous_applicant, newer.anonymous_applicant
        )

        assert _contributed_applications(request) == [newer, older]

    def test_submitted_application_is_absent(self, mock_site_context):
        submitted = CourseApplicationFactory(anonymous=True, course=_gated_course())
        request = _anonymous_request(submitted.anonymous_applicant)

        assert _contributed_applications(request) == []

    def test_completed_sitting_is_absent(self, mock_site_context):
        application = _anonymous_draft()
        FormProgress.objects.filter(pk=application.form_progress_id).update(
            completed_time=timezone.now()
        )
        request = _anonymous_request(application.anonymous_applicant)

        assert _contributed_applications(request) == []

    def test_claimed_application_is_absent(self, mock_site_context):
        application = _anonymous_draft()
        request = _anonymous_request(application.anonymous_applicant)
        CourseApplication.objects.filter(pk=application.pk).update(user=UserFactory())

        assert _contributed_applications(request) == []

    def test_erased_application_is_absent(self, mock_site_context):
        from freedom_ls.course_applications.erasure import erase_anonymous_applicant

        application = _anonymous_draft()
        request = _anonymous_request(application.anonymous_applicant)
        erase_anonymous_applicant(application.anonymous_applicant)

        assert _contributed_applications(request) == []

    def test_application_of_another_session_is_absent(self, mock_site_context):
        _anonymous_draft()
        request = _anonymous_request(_anonymous_draft().anonymous_applicant)

        assert len(_contributed_applications(request)) == 1

    def test_session_with_no_map_gets_nothing_without_a_query(
        self, mock_site_context, django_assert_max_num_queries
    ):
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        request = _anonymous_request()

        with django_assert_max_num_queries(0):
            contributions = ApplicationCourseAccessBackend().get_dashboard_contributions_for_request(
                request=request
            )

        assert contributions == []

    def test_signed_in_request_gets_the_users_applications(self, mock_site_context):
        application = CourseApplicationFactory()
        request = RequestFactory().get("/")
        request.user = application.user

        assert _contributed_applications(request) == [application]


def _signed_in_request(user, query: str = "", **headers: str):
    request = RequestFactory().get(f"/{query}", **headers)
    request.user = user
    return request


def _contributions_for(request):
    from freedom_ls.course_applications.backends import ApplicationCourseAccessBackend

    return ApplicationCourseAccessBackend().get_dashboard_contributions_for_request(
        request=request
    )


def _render_contribution(contribution, request=None) -> str:
    from django.template.loader import render_to_string

    return render_to_string(
        contribution.template_name,
        contribution.context,
        request=request or RequestFactory().get("/dashboard/"),
    )


def _applications_created_in_order(user, count: int) -> list[CourseApplication]:
    """Applications for one user, oldest first, with distinct creation times."""
    now = timezone.now()
    applications = []
    for index in range(count):
        application = CourseApplicationFactory(user=user)
        CourseApplication.objects.filter(pk=application.pk).update(
            created_at=now - timedelta(days=count - index)
        )
        applications.append(cast(CourseApplication, application))
    return applications


@pytest.mark.django_db
class TestApplicationsPaging:
    """The Your applications panel pages three at a time, newest first."""

    def test_page_one_holds_the_three_newest(self, mock_site_context):
        user = UserFactory()
        oldest_first = _applications_created_in_order(user, 7)

        contribution = _contributions_for(_signed_in_request(user))[0]

        assert contribution.context["applications"] == oldest_first[::-1][:3]
        assert contribution.context["applications_page"].paginator.num_pages == 3

    def test_the_last_page_holds_the_remainder(self, mock_site_context):
        user = UserFactory()
        oldest_first = _applications_created_in_order(user, 7)

        contribution = _contributions_for(
            _signed_in_request(user, "?page_applications=3")
        )[0]

        assert contribution.context["applications"] == [oldest_first[0]]

    def test_a_junk_page_number_gives_page_one(self, mock_site_context):
        user = UserFactory()
        _applications_created_in_order(user, 7)

        contribution = _contributions_for(
            _signed_in_request(user, "?page_applications=junk")
        )[0]

        assert contribution.context["applications_page"].number == 1

    def test_anonymous_drafts_page_the_same_way(self, mock_site_context):
        drafts = [_anonymous_draft() for _ in range(7)]
        request = _anonymous_request(*(d.anonymous_applicant for d in drafts))
        request.GET = request.GET.copy()
        request.GET["page_applications"] = "3"

        contribution = _contributions_for(request)[0]

        assert len(contribution.context["applications"]) == 1
        assert contribution.context["applications_page"].paginator.num_pages == 3

    @pytest.mark.parametrize(
        ("headers", "expected"),
        [
            ({}, False),
            ({"HTTP_HX_TARGET": "section-page-available"}, False),
            ({"HTTP_HX_TARGET": "applications-page"}, True),
        ],
    )
    def test_only_a_swap_of_the_panels_own_page_is_announced(
        self, mock_site_context, headers, expected
    ):
        user = UserFactory()
        CourseApplicationFactory(user=user)

        contribution = _contributions_for(_signed_in_request(user, **headers))[0]

        assert contribution.context["announce_page"] is expected

    def test_without_a_request_page_one_is_shown_and_not_announced(
        self, mock_site_context
    ):
        from django.template.loader import render_to_string

        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()
        oldest_first = _applications_created_in_order(user, 4)

        contribution = ApplicationCourseAccessBackend().get_dashboard_contributions(
            user=user
        )[0]
        rendered = render_to_string(contribution.template_name, contribution.context)

        assert contribution.context["applications"] == oldest_first[::-1][:3]
        assert contribution.context["announce_page"] is False
        # No request to copy a URL from, so the pager links by query string alone.
        assert 'href="?page_applications=2"' in rendered

    def test_a_swap_of_the_panels_own_page_gets_the_page_fragment(
        self, mock_site_context
    ):
        user = UserFactory()
        CourseApplicationFactory(user=user)

        whole_page = _contributions_for(_signed_in_request(user))[0]
        own_swap = _contributions_for(
            _signed_in_request(user, HTTP_HX_TARGET="applications-page")
        )[0]

        assert whole_page.template_name.endswith("dashboard_applications.html")
        assert own_swap.template_name.endswith("#panel-page-response")
        assert whole_page.swap_id == own_swap.swap_id == "applications-page"

    def test_a_swap_of_an_emptied_panel_renders_an_empty_boundary(
        self, mock_site_context
    ):
        user = UserFactory()
        request = _signed_in_request(user, HTTP_HX_TARGET="applications-page")

        contributions = _contributions_for(request)
        rendered = _render_contribution(contributions[0], request)

        assert len(contributions) == 1
        assert 'id="applications-page"' in rendered
        assert "Your applications</h2>" not in rendered
        assert "Your applications: none" in rendered

    def test_only_one_page_of_applications_leaves_the_database(
        self, mock_site_context, django_assert_num_queries
    ):
        user = UserFactory()
        _applications_created_in_order(user, 7)

        # A count and the one page of rows, each with its course and sitting joined.
        with django_assert_num_queries(2):
            contribution = _contributions_for(_signed_in_request(user))[0]

        assert len(contribution.context["applications"]) == 3

    def test_no_applications_gives_no_contribution_on_both_entry_points(
        self, mock_site_context
    ):
        from freedom_ls.course_applications.backends import (
            ApplicationCourseAccessBackend,
        )

        user = UserFactory()

        assert (
            ApplicationCourseAccessBackend().get_dashboard_contributions(user=user)
            == []
        )
        assert _contributions_for(_signed_in_request(user)) == []

    def test_the_rendered_panel_states_its_position_and_disables_both_controls(
        self, mock_site_context
    ):
        user = UserFactory()
        CourseApplicationFactory.create_batch(2, user=user)

        rendered = _render_contribution(_contributions_for(_signed_in_request(user))[0])

        assert "1 to 2 of 2" in rendered
        assert rendered.count('aria-disabled="true"') == 2
        assert 'aria-label="Your applications pages"' in rendered

    def test_the_status_region_is_filled_only_when_announcing(self, mock_site_context):
        user = UserFactory()
        CourseApplicationFactory.create_batch(2, user=user)
        announced = _contributions_for(
            _signed_in_request(user, HTTP_HX_TARGET="applications-page")
        )[0]
        silent = _contributions_for(_signed_in_request(user))[0]

        announced_html = _render_contribution(announced)
        silent_html = _render_contribution(silent)

        assert "Your applications: showing 1 to 2 of 2" in announced_html
        assert "Your applications: showing" not in silent_html
        assert 'id="applications-status"' in silent_html

    def test_the_next_control_keeps_another_sections_page(self, mock_site_context):
        user = UserFactory()
        CourseApplicationFactory.create_batch(4, user=user)
        request = _signed_in_request(user, "?page_available=2")

        rendered = _render_contribution(_contributions_for(request)[0], request)

        next_control = re.search(r'<a [^>]*data-direction="next"[^>]*>', rendered)
        assert next_control is not None
        assert "page_available=2" in next_control.group(0)
        assert "page_applications=2" in next_control.group(0)
