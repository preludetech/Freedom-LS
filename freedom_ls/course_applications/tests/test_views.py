"""Tests for course_applications views."""

from __future__ import annotations

import re
import smtplib
import threading
import time
from datetime import timedelta
from typing import TYPE_CHECKING, NamedTuple, cast
from unittest.mock import patch
from urllib.parse import urlencode

import lxml.html
import pytest
import time_machine
from allauth.account import app_settings as allauth_account_settings
from allauth.account.models import EmailAddress

from django.contrib.messages import get_messages
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sites.models import Site
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection
from django.test import Client, RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape, strip_tags

from freedom_ls.accounts.allauth_account_adapter import AccountAdapter
from freedom_ls.accounts.factories import (
    EmailAddressFactory,
    SiteSignupPolicyFactory,
    UserFactory,
)
from freedom_ls.accounts.models import LegalConsent, User
from freedom_ls.accounts.tests._auth_page_helpers import _next_param
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.referral_tracking.factories import AttributionTouchFactory
from freedom_ls.referral_tracking.models import Conversion, ConversionKind, TouchSource
from freedom_ls.tests.app_guards import app_not_installed
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.images import png_bytes
from freedom_ls.tests.site_context import site_context

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.anonymous_session import (
    ANONYMOUS_APPLICANTS_SESSION_KEY,
    anonymous_applicant_for_course,
)
from freedom_ls.course_applications.claims import claim_token, update_applicant_email
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import (
    AnonymousApplicant,
    CourseApplication,
    claim_link_max_age,
)
from freedom_ls.course_applications.queries import organisation_for_new_application
from freedom_ls.course_applications.transitions import (
    reject_application,
    submit_application,
    withdraw_application,
)
from freedom_ls.course_applications.views import (
    _details_in_flight_key,
    _start_application,
)
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
    served_paper_of,
)
from freedom_ls.form_engine.models import (
    Form,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionOption,
)
from freedom_ls.form_engine.queries import page_questions
from freedom_ls.form_engine.session_access import ANONYMOUS_FORM_PROGRESS_SESSION_KEY
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.learner_progress.models import CourseFormAttempt, CourseProgress

from .helpers import gated_course_with_form

# ---------------------------------------------------------------------------
# apply view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestApplyViewGet:
    """GET /apply/<slug>/ without an existing application — confirmation page."""

    def test_get_no_existing_app_returns_200(self, client, mock_site_context):
        """GET apply with no existing application renders a 200 confirmation page."""
        user = UserFactory()
        course = CourseFactory()
        client.force_login(user)

        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        response = client.get(url)

        assert response.status_code == 200

    def test_get_confirmation_page_contains_course_title(
        self, client, mock_site_context
    ):
        """GET apply confirmation page contains the course title."""
        user = UserFactory()
        course = CourseFactory()
        client.force_login(user)

        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        response = client.get(url)

        assert course.title in response.content.decode()

    def test_get_unauthenticated_redirects_to_applicant_details(
        self, client, mock_site_context
    ):
        """GET apply without login sends a visitor to the details step."""
        course = CourseFactory(access_config={"access_type": "application_gated"})
        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        response = client.get(url)

        assert response.status_code == 302
        assert response["Location"] == reverse(
            "course_applications:applicant_details",
            kwargs={"course_slug": course.slug},
        )

    def test_get_nonexistent_course_returns_404(self, client, mock_site_context):
        """GET apply for a non-existent course slug returns 404."""
        user = UserFactory()
        client.force_login(user)

        url = reverse(
            "course_applications:apply", kwargs={"course_slug": "no-such-course"}
        )
        response = client.get(url)

        assert response.status_code == 404


@pytest.mark.django_db
class TestApplyViewGetExistingApplication:
    """GET /apply/<slug>/ when learner already has an application — redirect to status."""

    def test_get_with_existing_app_redirects_to_status(self, client, mock_site_context):
        """GET apply when learner has an existing application redirects to status page."""
        user = UserFactory()
        course = CourseFactory()
        existing_app = CourseApplicationFactory(user=user, course=course)
        client.force_login(user)

        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        response = client.get(url)

        expected_status_url = reverse(
            "course_applications:status", kwargs={"pk": existing_app.pk}
        )
        assert response.status_code == 302
        assert response["Location"] == expected_status_url

    def test_get_with_existing_app_does_not_create_duplicate(
        self, client, mock_site_context
    ):
        """GET apply when learner already applied does not create a duplicate application."""
        user = UserFactory()
        course = CourseFactory()
        CourseApplicationFactory(user=user, course=course)
        client.force_login(user)

        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        client.get(url)

        assert CourseApplication.objects.filter(user=user, course=course).count() == 1


@pytest.mark.django_db
class TestApplyAfterAClosedApplication:
    """An account whose latest application is closed can start another."""

    def test_post_after_a_withdrawn_application_creates_a_submitted_one(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        course = CourseFactory()
        CourseApplicationFactory(user=user, course=course, withdrawn=True)
        client.force_login(user)

        response = client.post(
            reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        )

        new = CourseApplication.objects.get(
            user=user, course=course, state=CourseApplication.State.SUBMITTED
        )
        assert CourseApplication.objects.filter(user=user, course=course).count() == 2
        assert response["Location"] == reverse(
            "course_applications:status", kwargs={"pk": new.pk}
        )

    def test_post_after_a_rejected_application_creates_a_submitted_one(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        course = CourseFactory()
        CourseApplicationFactory(user=user, course=course, rejected=True)
        client.force_login(user)

        client.post(
            reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        )

        assert CourseApplication.objects.filter(
            user=user, course=course, state=CourseApplication.State.SUBMITTED
        ).exists()

    def test_get_after_a_withdrawn_application_starts_a_draft_for_a_form_course(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        course, _form = gated_course_with_form()
        CourseApplicationFactory(user=user, course=course, withdrawn=True)
        client.force_login(user)

        client.get(
            reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        )

        draft = CourseApplication.objects.get(
            user=user, course=course, state=CourseApplication.State.DRAFT
        )
        assert draft.form_progress is not None

    def test_each_new_application_records_its_own_conversion(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        course = CourseFactory()
        CourseApplicationFactory(user=user, course=course, withdrawn=True)
        client.force_login(user)
        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})

        client.post(url)

        new = CourseApplication.objects.get(
            user=user, course=course, state=CourseApplication.State.SUBMITTED
        )
        conversion = Conversion._base_manager.get(user=user)
        assert conversion.kind == ConversionKind.COURSE_APPLICATION
        assert conversion.object_id == str(new.pk)

    def test_post_with_an_active_application_redirects_to_it(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        course = CourseFactory()
        CourseApplicationFactory(user=user, course=course, withdrawn=True)
        active = CourseApplicationFactory(user=user, course=course)
        client.force_login(user)

        response = client.post(
            reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        )

        assert response["Location"] == reverse(
            "course_applications:status", kwargs={"pk": active.pk}
        )
        assert CourseApplication.objects.filter(user=user, course=course).count() == 2

    def test_post_on_a_coming_soon_course_redirects_to_the_course_detail_page(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        CourseApplicationFactory(user=user, course=course, withdrawn=True)
        client.force_login(user)

        response = client.post(
            reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        )

        assert response["Location"] == reverse(
            "learner_interface:course_detail", kwargs={"course_slug": course.slug}
        )
        assert CourseApplication.objects.filter(user=user, course=course).count() == 1

    def test_withdrawn_status_page_links_to_apply_again(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        application = CourseApplicationFactory(user=user, withdrawn=True)
        client.force_login(user)

        response = client.get(
            reverse("course_applications:status", kwargs={"pk": application.pk})
        )

        apply_url = reverse(
            "course_applications:apply",
            kwargs={"course_slug": application.course.slug},
        )
        content = response.content.decode()
        assert "Apply again" in content
        assert f'href="{apply_url}"' in content

    @pytest.mark.parametrize("closed_traits", [{"withdrawn": True}, {"rejected": True}])
    def test_a_closed_status_page_links_to_the_newer_application(
        self, client: Client, mock_site_context: Site, closed_traits: dict[str, bool]
    ) -> None:
        user = UserFactory()
        course = CourseFactory()
        old = CourseApplicationFactory(user=user, course=course, **closed_traits)
        current = CourseApplicationFactory(user=user, course=course)
        client.force_login(user)

        response = client.get(
            reverse("course_applications:status", kwargs={"pk": old.pk})
        )

        current_url = reverse("course_applications:status", kwargs={"pk": current.pk})
        content = response.content.decode()
        assert "Apply again" not in content
        assert "You can apply again." not in content
        assert "You have a newer application for this course." in content
        assert f'href="{current_url}"' in content
        assert "View my current application" in content


@pytest.mark.django_db
class TestApplyViewPost:
    """POST /apply/<slug>/ — creates application and redirects to status."""

    def test_post_for_a_no_form_course_creates_a_submitted_application(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        course = CourseFactory()
        client.force_login(user)

        with time_machine.travel("2026-03-01 10:00:00+00:00", tick=False):
            client.post(
                reverse(
                    "course_applications:apply", kwargs={"course_slug": course.slug}
                )
            )

        app = CourseApplication.objects.get(user=user, course=course)
        assert app.state == CourseApplication.State.SUBMITTED
        assert app.submitted_at is not None
        assert app.organisation == organisation_for_new_application(course)

    def test_post_for_a_form_course_creates_a_draft_application(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        course, _form = gated_course_with_form()
        client.force_login(user)

        client.post(
            reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        )

        app = CourseApplication.objects.get(user=user, course=course)
        assert app.state == CourseApplication.State.DRAFT
        assert app.submitted_at is None

    def test_post_creates_application(self, client, mock_site_context):
        """POST apply creates one CourseApplication for the learner."""
        user = UserFactory()
        course = CourseFactory()
        client.force_login(user)

        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        client.post(url)

        assert CourseApplication.objects.filter(user=user, course=course).count() == 1

    def test_post_redirects_to_status_page(self, client, mock_site_context):
        """POST apply redirects to the application status page."""
        user = UserFactory()
        course = CourseFactory()
        client.force_login(user)

        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        response = client.post(url)

        app = CourseApplication.objects.get(user=user, course=course)
        expected_status_url = reverse(
            "course_applications:status", kwargs={"pk": app.pk}
        )
        assert response.status_code == 302
        assert response["Location"] == expected_status_url

    def test_second_post_does_not_create_duplicate(self, client, mock_site_context):
        """A second POST to apply for the same course does not create a duplicate."""
        user = UserFactory()
        course = CourseFactory()
        client.force_login(user)

        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        client.post(url)
        client.post(url)

        assert CourseApplication.objects.filter(user=user, course=course).count() == 1

    def test_second_post_redirects_to_existing_status(self, client, mock_site_context):
        """A second POST redirects to the same existing application status page."""
        user = UserFactory()
        course = CourseFactory()
        client.force_login(user)

        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        client.post(url)
        response = client.post(url)

        app = CourseApplication.objects.get(user=user, course=course)
        expected_status_url = reverse(
            "course_applications:status", kwargs={"pk": app.pk}
        )
        assert response.status_code == 302
        assert response["Location"] == expected_status_url


@pytest.mark.django_db
class TestApplyViewVisibilityGate:
    """apply enforces course visibility (hidden means hidden; coming-soon not enrollable)."""

    def _apply_url(self, course):
        return reverse("course_applications:apply", kwargs={"course_slug": course.slug})

    def test_hidden_unregistered_get_returns_404(self, client, mock_site_context):
        """GET apply for a hidden course by an unregistered user 404s (no existence leak)."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        client.force_login(user)

        response = client.get(self._apply_url(course))

        assert response.status_code == 404

    def test_hidden_unregistered_post_does_not_create_application(
        self, client, mock_site_context
    ):
        """POST apply for a hidden course by an unregistered user 404s and creates nothing."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        client.force_login(user)

        response = client.post(self._apply_url(course))

        assert response.status_code == 404
        assert not CourseApplication.objects.filter(user=user, course=course).exists()

    def test_hidden_registered_get_returns_200(self, client, mock_site_context):
        """A registered learner still reaches the apply page for a hidden course."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)
        LearnerCourseRegistrationFactory(
            learner__user=user, course=course, is_active=True
        )
        client.force_login(user)

        response = client.get(self._apply_url(course))

        assert response.status_code == 200

    def test_coming_soon_post_redirects_to_detail_and_creates_nothing(
        self, client, mock_site_context
    ):
        """POST apply for a coming-soon course redirects to detail without applying."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        client.force_login(user)

        response = client.post(self._apply_url(course))

        expected = reverse(
            "learner_interface:course_detail", kwargs={"course_slug": course.slug}
        )
        assert response.status_code == 302
        assert response["Location"] == expected
        assert not CourseApplication.objects.filter(user=user, course=course).exists()

    def test_coming_soon_with_existing_application_redirects_to_status(
        self, client, mock_site_context
    ):
        """An applicant on a course later flipped to coming-soon still reaches their status page.

        The existing-application short-circuit must take precedence over the
        coming-soon detail redirect, so the applicant is never bounced to the
        express-interest CTA for a course they have already applied to.
        """
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        existing_app = CourseApplicationFactory(user=user, course=course)
        client.force_login(user)

        response = client.get(self._apply_url(course))

        expected = reverse("course_applications:status", kwargs={"pk": existing_app.pk})
        assert response.status_code == 302
        assert response["Location"] == expected


# ---------------------------------------------------------------------------
# application_status view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def _status_page(
    client: Client, application: CourseApplication
) -> lxml.html.HtmlElement:
    response = client.get(
        reverse("course_applications:status", kwargs={"pk": application.pk})
    )
    return lxml.html.fromstring(response.content.decode())


def _detail_labels(page: lxml.html.HtmlElement) -> list[str]:
    return [
        label.text_content().strip()
        for label in page.xpath('//*[@data-testid="application-details"]//dt')
    ]


@pytest.mark.django_db
class TestApplicationStatusBackLink:
    """Going back is a link above the heading, never a button among the actions."""

    def test_the_back_link_to_the_dashboard_comes_before_the_heading(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        client.force_login(user)

        page = _status_page(client, CourseApplicationFactory(user=user))

        dashboard_url = reverse("learner_interface:dashboard")
        back_links = page.xpath(f'//h1/preceding::a[@href="{dashboard_url}"]')
        assert [link.text_content().strip() for link in back_links][-1:] == ["Back"]

    def test_the_action_row_holds_withdraw_and_no_way_back(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        application = CourseApplicationFactory(user=user)
        client.force_login(user)

        page = _status_page(client, application)

        rows = page.xpath('//*[@data-testid="application-actions"]')
        assert len(rows) == 1
        dashboard_url = reverse("learner_interface:dashboard")
        withdraw_url = reverse(
            "course_applications:withdraw", kwargs={"pk": application.pk}
        )
        assert not rows[0].xpath(f'.//a[@href="{dashboard_url}"]')
        assert rows[0].xpath(f'.//form[@action="{withdraw_url}"]')
        assert "Back to dashboard" not in page.text_content()

    def test_the_withdraw_trigger_is_a_destructive_button(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        application = CourseApplicationFactory(user=user)
        client.force_login(user)

        page = _status_page(client, application)

        withdraw_url = reverse(
            "course_applications:withdraw", kwargs={"pk": application.pk}
        )
        triggers = page.xpath(f'//form[@action="{withdraw_url}"]//button')
        assert ["btn-error" in trigger.get("class") for trigger in triggers] == [True]


@pytest.mark.django_db
class TestApplicationStatusDetails:
    """The details card lists the application's facts for its state."""

    def test_a_submitted_application_lists_its_dates_and_next_step(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        client.force_login(user)

        page = _status_page(client, CourseApplicationFactory(user=user))

        assert _detail_labels(page) == [
            "Course",
            "Status",
            "Started",
            "Submitted",
            "Next step",
        ]
        assert "Nothing. We will review your application." in page.text_content()

    def test_the_course_row_links_to_the_course_page(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        application = CourseApplicationFactory(user=user)
        client.force_login(user)

        page = _status_page(client, application)

        course_url = reverse(
            "learner_interface:course_detail",
            kwargs={"course_slug": application.course.slug},
        )
        assert page.xpath(
            f'//*[@data-testid="application-details"]//a[@href="{course_url}"]'
        )

    def test_a_draft_lists_how_many_questions_are_answered(
        self, client: Client, mock_site_context: Site
    ) -> None:
        course, _form = gated_course_with_form()
        application = _applied(client, course)

        page = _status_page(client, application)

        assert _detail_labels(page) == [
            "Course",
            "Status",
            "Started",
            "Progress",
            "Next step",
        ]
        assert "0 of " in page.text_content()
        assert "Finish and submit your application." in page.text_content()

    def test_an_approved_application_lists_its_decision_date(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        client.force_login(user)

        page = _status_page(client, CourseApplicationFactory(user=user, approved=True))

        assert _detail_labels(page) == [
            "Course",
            "Status",
            "Started",
            "Submitted",
            "Decision",
            "Next step",
        ]

    def test_a_declined_application_lists_the_reason_under_its_status(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        application = CourseApplicationFactory(
            user=user, rejected=True, rejection_message="Too early."
        )
        client.force_login(user)

        page = _status_page(client, application)

        assert _detail_labels(page)[:3] == ["Course", "Status", "Reason"]
        values = page.xpath('//*[@data-testid="application-details"]//dd')
        assert values[1].text_content().strip() == "Declined"
        assert values[2].text_content().strip() == "Too early."

    def test_the_course_link_is_not_underlined_like_prose(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        client.force_login(user)

        page = _status_page(client, CourseApplicationFactory(user=user))

        links = page.xpath('//*[@data-testid="application-details"]//a')
        assert ["no-underline" in link.get("class", "").split() for link in links] == [
            True
        ]

    def test_a_withdrawn_application_lists_when_it_was_withdrawn(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        application = CourseApplicationFactory(user=user)
        withdraw_application(application)
        client.force_login(user)

        page = _status_page(client, application)

        assert "Withdrawn" in _detail_labels(page)
        assert "You can apply again." in page.text_content()


@pytest.mark.django_db
class TestApplicationStatusView:
    """Applicant status page."""

    def test_owner_gets_200(self, client, mock_site_context):
        """Application owner receives a 200 status page."""
        user = UserFactory()
        app = CourseApplicationFactory(user=user)
        client.force_login(user)

        url = reverse("course_applications:status", kwargs={"pk": app.pk})
        response = client.get(url)

        assert response.status_code == 200

    def test_status_page_of_a_submitted_application_says_it_is_waiting(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        app = CourseApplicationFactory(user=user)
        client.force_login(user)

        url = reverse("course_applications:status", kwargs={"pk": app.pk})
        response = client.get(url)

        content = response.content.decode()
        assert "is waiting for review. The decision will show here." in content
        assert "You will be notified once a decision has been made" not in content

    def test_non_owner_gets_404(self, client, mock_site_context):
        """A learner who does not own the application gets 404."""
        owner = UserFactory()
        other_user = UserFactory()
        app = CourseApplicationFactory(user=owner)
        client.force_login(other_user)

        url = reverse("course_applications:status", kwargs={"pk": app.pk})
        response = client.get(url)

        assert response.status_code == 404

    def test_unauthenticated_redirects_to_login(self, client, mock_site_context):
        """A visitor whose session holds no such application is sent to log in,
        with next set to the status URL: an owner whose session has ended is the
        usual case."""
        owner = UserFactory()
        app = CourseApplicationFactory(user=owner)

        url = reverse("course_applications:status", kwargs={"pk": app.pk})
        response = client.get(url)

        assert response.status_code == 302
        assert response["Location"] == f"{reverse('account_login')}?next={url}"


# ---------------------------------------------------------------------------
# The application form flow
# ---------------------------------------------------------------------------


def _page_url(app, page_number):
    return reverse(
        "course_applications:form_page",
        kwargs={"pk": app.pk, "page_number": page_number},
    )


def _edit_url(app, page_number):
    """A form page reached from the check-your-answers page."""
    return f"{_page_url(app, page_number)}?return=check"


def _check_url(app):
    return reverse("course_applications:check_answers", kwargs={"pk": app.pk})


def _questions_on(form, page_number):
    page = list(form.pages.all())[page_number - 1]
    return page_questions(page)


def _add_required_page_opened_by_the_search_option(form):
    """A third page, with one required question, shown only to applicants who
    picked "Search" for how they heard about the course."""
    choice = _questions_on(form, 1)[2]
    page = FormPageFactory(
        form=form,
        order=2,
        condition_option=choice.options.get(text="Search"),
    )
    FormQuestionFactory(form_page=page, type="short_text", order=0, required=True)


def _applied(client, course):
    """Log a fresh user in and take them through the apply POST."""
    user = UserFactory()
    client.force_login(user)
    client.post(
        reverse("course_applications:apply", kwargs={"course_slug": course.slug})
    )
    return CourseApplication.objects.get(user=user, course=course)


@pytest.mark.django_db
class TestApplyStartsTheForm:
    def test_applying_to_a_course_with_a_form_creates_a_sitting(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()

        app = _applied(client, course)

        assert app.form_progress.form == form

    def test_applying_to_a_course_with_a_form_lands_on_page_one(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        user = UserFactory()
        client.force_login(user)

        response = client.post(
            reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        )

        app = CourseApplication.objects.get(user=user, course=course)
        assert response["Location"] == _page_url(app, 1)

    def test_visiting_apply_for_a_course_with_a_form_starts_it(
        self, client, mock_site_context
    ):
        """The course detail CTA is a plain link, so the GET has to be enough:
        nothing is sent until the check-your-answers page, so there is nothing
        to confirm first."""
        course, form = gated_course_with_form()
        user = UserFactory()
        client.force_login(user)

        response = client.get(
            reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        )

        app = CourseApplication.objects.get(user=user, course=course)
        assert app.form_progress.form == form
        assert response["Location"] == _page_url(app, 1)

    def test_visiting_apply_for_a_course_with_no_form_still_asks_first(
        self, client, mock_site_context
    ):
        """With no form, creating the application is the submission itself, so
        the confirmation page stays."""
        course = CourseFactory()
        client.force_login(UserFactory())

        response = client.get(
            reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        )

        assert response.status_code == 200
        assert not CourseApplication.objects.filter(course=course).exists()

    def test_applying_to_a_course_with_no_form_still_reaches_the_status_page(
        self, client, mock_site_context
    ):
        course = CourseFactory()
        user = UserFactory()
        client.force_login(user)

        response = client.post(
            reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        )

        app = CourseApplication.objects.get(user=user, course=course)
        assert response["Location"] == reverse(
            "course_applications:status", kwargs={"pk": app.pk}
        )


@pytest.mark.django_db
class TestApplicationStatusResumes:
    def test_a_submitted_application_renders_its_status(
        self, client: Client, mock_site_context: Site
    ) -> None:
        course, _form = gated_course_with_form()
        app = _applied(client, course)
        submit_application(app)
        app.form_progress.complete()

        response = client.get(
            reverse("course_applications:status", kwargs={"pk": app.pk})
        )

        assert response.status_code == 200


def _gated_course_with_a_page_less_form():
    """An author can save a form with no pages, and a course can name it."""
    form = FormFactory(strategy=FormStrategy.UNSCORED)
    course = CourseFactory(access_config={"access_type": "application_gated"})
    course.application_form = form
    course.save(update_fields=["application_form"])
    return course


@pytest.mark.django_db
class TestAPageLessForm:
    """A form with no pages has no page 1 to land on, so the applicant is sent
    straight to the page they submit from rather than to a 404."""

    def test_applying_lands_on_the_check_page(self, client, mock_site_context):
        course = _gated_course_with_a_page_less_form()
        user = UserFactory()
        client.force_login(user)

        response = client.post(
            reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        )

        app = CourseApplication.objects.get(user=user, course=course)
        assert response["Location"] == _check_url(app)

    def test_the_status_page_continues_on_the_check_page(
        self, client: Client, mock_site_context: Site
    ) -> None:
        course = _gated_course_with_a_page_less_form()
        app = _applied(client, course)

        body = client.get(
            reverse("course_applications:status", kwargs={"pk": app.pk})
        ).content.decode()

        assert f'href="{_check_url(app)}"' in body

    def test_the_check_page_renders_and_submits(self, client, mock_site_context):
        course = _gated_course_with_a_page_less_form()
        app = _applied(client, course)

        assert client.get(_check_url(app)).status_code == 200
        client.post(_check_url(app))

        app.refresh_from_db()
        assert app.form_progress.completed_time is not None


def _gated_application_with_a_skippable_page(client):
    """An application whose form has page 2 open only on `yes` to page 1's
    question, with a third, always-asked page. Returns the application, the
    `yes` and `no` options and the page-one question."""
    form = FormFactory(strategy=FormStrategy.UNSCORED)
    page_one = FormPageFactory(form=form, order=0)
    choice = FormQuestionFactory(
        form_page=page_one, type="multiple_choice", order=0, required=False
    )
    yes = QuestionOptionFactory(question=choice, value="yes", order=0)
    no = QuestionOptionFactory(question=choice, value="no", order=1)
    page_two = FormPageFactory(form=form, order=1, condition_option=yes)
    FormQuestionFactory(form_page=page_two, type="short_text", order=0, required=False)
    page_three = FormPageFactory(form=form, order=2)
    FormQuestionFactory(form_page=page_three, type="short_text", order=0)
    course = CourseFactory(access_config={"access_type": "application_gated"})
    course.application_form = form
    course.save(update_fields=["application_form"])
    app = _applied(client, course)
    return app, yes, no, choice


QUERY_BUDGET = 30


@pytest.mark.django_db
class TestApplicationFormPaging:
    def test_an_off_path_page_redirects_to_the_next_page_asked(
        self, client, mock_site_context
    ):
        app, _yes, _no, _choice = _gated_application_with_a_skippable_page(client)

        response = client.get(_page_url(app, 2))

        assert response["Location"] == _page_url(app, 3)

    def test_a_post_to_an_off_path_page_redirects_and_stores_nothing(
        self, client, mock_site_context
    ):
        app, _yes, _no, _choice = _gated_application_with_a_skippable_page(client)
        hidden = app.form_progress.form.pages.get(order=1).questions.get()

        response = client.post(_page_url(app, 2), {f"question_{hidden.id}": "x"})

        assert response["Location"] == _page_url(app, 3)
        assert not app.form_progress.answers.filter(question=hidden).exists()

    def test_answering_no_skips_the_gated_page(self, client, mock_site_context):
        app, _yes, no, choice = _gated_application_with_a_skippable_page(client)

        response = client.post(_page_url(app, 1), {f"question_{choice.id}": str(no.id)})

        assert response["Location"] == _page_url(app, 3)

    def test_answering_yes_visits_the_gated_page(self, client, mock_site_context):
        app, yes, _no, choice = _gated_application_with_a_skippable_page(client)

        response = client.post(
            _page_url(app, 1), {f"question_{choice.id}": str(yes.id)}
        )

        assert response["Location"] == _page_url(app, 2)

    def test_the_page_jump_nav_omits_the_off_path_page(self, client, mock_site_context):
        app, _yes, _no, _choice = _gated_application_with_a_skippable_page(client)

        response = client.get(_page_url(app, 1))

        urls = [link["url"] for link in response.context["page_links"]]
        assert urls == [_page_url(app, 1), _page_url(app, 3)]

    def test_a_rejected_page_is_re_rendered_along_the_path_its_saved_answers_give(
        self, client, mock_site_context
    ):
        """Switching the gate to "no" is saved even though the date beside it
        is rejected, so the 422 page's nav must already omit page 2."""
        app, yes, no, choice = _gated_application_with_a_skippable_page(client)
        date = FormQuestionFactory(
            form_page=choice.form_page, type="date", order=1, required=False
        )
        client.post(_page_url(app, 1), {f"question_{choice.id}": str(yes.id)})

        response = client.post(
            _page_url(app, 1),
            {f"question_{choice.id}": str(no.id), f"question_{date.id}": "banana"},
        )

        assert response.status_code == 422
        urls = [link["url"] for link in response.context["page_links"]]
        assert urls == [_page_url(app, 1), _page_url(app, 3)]

    def test_a_submitted_application_pages_along_its_frozen_path(
        self, client, mock_site_context
    ):
        app, yes, _no, choice = _gated_application_with_a_skippable_page(client)
        form = app.form_progress.form
        answer = QuestionAnswerFactory(form_progress=app.form_progress, question=choice)
        answer.selected_options.set([yes])
        pages = list(form.pages.all())
        app.form_progress.completed_time = timezone.now()
        app.form_progress.asked = {
            "pages": [str(pages[0].id), str(pages[2].id)],
            "questions": [
                str(choice.id),
                str(pages[2].questions.get().id),
            ],
            "content": [],
        }
        app.form_progress.save()

        response = client.get(_page_url(app, 2))

        assert response["Location"] == _page_url(app, 3)

    def test_the_page_runs_within_a_query_budget(
        self, client, mock_site_context, django_assert_max_num_queries
    ):
        app, _yes, _no, _choice = _gated_application_with_a_skippable_page(client)

        with django_assert_max_num_queries(QUERY_BUDGET):
            client.get(_page_url(app, 1))


@pytest.mark.django_db
class TestApplicationFormPage:
    def test_the_owner_sees_page_one(self, client, mock_site_context):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        response = client.get(_page_url(app, 1))

        assert response.status_code == 200

    @pytest.mark.parametrize("submitted", [False, True])
    def test_a_form_page_never_shows_the_answer_key(
        self, client, mock_site_context, submitted
    ):
        course, form = gated_course_with_form()
        page = form.pages.get(order=0)
        for question_type in ("checkboxes", "dropdown"):
            question = FormQuestionFactory(form_page=page, type=question_type, order=10)
            QuestionOptionFactory(question=question, text="Right", correct=True)
        form.pages.get(order=0).questions.get(type="multiple_choice").options.filter(
            text="Search"
        ).update(correct=True)
        app = _applied(client, course)
        if submitted:
            app.form_progress.completed_time = timezone.now()
            app.form_progress.save(update_fields=["completed_time"])

        response = client.get(_page_url(app, 1))

        assert response.status_code == 200
        assert "Search" in response.content.decode()
        assert "Correct answer" not in response.content.decode()

    def test_a_form_page_is_never_cached(self, client, mock_site_context):
        """A back-nav must re-read the answers, or it shows work that has since
        changed."""
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        response = client.get(_page_url(app, 1))

        assert response.get("Cache-Control") == "no-store"

    def test_a_non_owner_gets_404(self, client, mock_site_context):
        course, _form = gated_course_with_form()
        app = _applied(client, course)
        client.force_login(UserFactory())

        response = client.get(_page_url(app, 1))

        assert response.status_code == 404

    def test_a_page_number_past_the_end_is_404(self, client, mock_site_context):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        response = client.get(_page_url(app, 9))

        assert response.status_code == 404

    def test_stepping_back_keeps_the_reached_page_clickable(
        self, client, mock_site_context
    ):
        """Page 1 holds optional questions, so answering none of them and going
        back must not re-lock the page the applicant had already reached."""
        course, _form = gated_course_with_form()
        app = _applied(client, course)
        client.get(_page_url(app, 2))

        response = client.get(_page_url(app, 1))

        accessible = [link["is_accessible"] for link in response.context["page_links"]]
        assert accessible == [True, True]

    def test_answering_a_page_advances_to_the_next(self, client, mock_site_context):
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]

        response = client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})

        assert response["Location"] == _page_url(app, 2)

    def test_answering_the_last_page_reaches_check_your_answers(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})

        response = client.post(_page_url(app, 2), {})

        assert response["Location"] == _check_url(app)

    def test_a_blank_required_question_is_refused_with_422(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        response = client.post(_page_url(app, 1), {})

        assert response.status_code == 422

    def test_saving_a_page_reached_from_the_check_page_returns_there(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]

        response = client.post(_edit_url(app, 1), {f"question_{name.id}": "Ada"})

        assert response["Location"] == _check_url(app)

    def test_a_page_reached_from_the_check_page_offers_a_return_button(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        response = client.get(_edit_url(app, 1))

        assert response.context["return_to_check"]
        assert _check_url(app) in response.content.decode()

    def test_a_page_reached_normally_offers_no_return_button(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        response = client.get(_page_url(app, 1))

        assert not response.context["return_to_check"]

    def test_a_refused_page_keeps_the_return_marker(self, client, mock_site_context):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        response = client.post(_edit_url(app, 1), {})

        assert response.status_code == 422
        assert response.context["return_to_check"]

    def test_a_refused_page_still_keeps_the_answers_that_were_given(
        self, client, mock_site_context
    ):
        """Throwing away the work someone did do, because of the one field they
        missed, is the cruellest thing a form can do.
        """
        course, form = gated_course_with_form()
        app = _applied(client, course)
        years = _questions_on(form, 1)[1]

        client.post(_page_url(app, 1), {f"question_{years.id}": "7"})

        answer = app.form_progress.answers.get(question=years)
        assert answer.text_answer == "7"

    def test_a_submitted_application_writes_nothing_more(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})
        submit_application(app)
        app.form_progress.complete()

        client.post(_page_url(app, 1), {f"question_{name.id}": "Grace"})

        answer = app.form_progress.answers.get(question=name)
        assert answer.text_answer == "Ada"

    def test_a_submitted_application_is_sent_to_its_status_page(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        submit_application(app)
        app.form_progress.complete()

        response = client.post(_page_url(app, 1), {f"question_{name.id}": "Grace"})

        assert response["Location"] == reverse(
            "course_applications:status", kwargs={"pk": app.pk}
        )

    def test_a_question_from_another_form_is_ignored(self, client, mock_site_context):
        """The page saves only the questions it lays out, so an extra key naming
        someone else's question reaches nothing.
        """
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        _other_course, other_form = gated_course_with_form()
        stranger = _questions_on(other_form, 1)[0]

        client.post(
            _page_url(app, 1),
            {f"question_{name.id}": "Ada", f"question_{stranger.id}": "Injected"},
        )

        assert app.form_progress.answers.filter(question=stranger).count() == 0


@pytest.mark.django_db
class TestCheckYourAnswers:
    def test_a_non_owner_gets_404(self, client, mock_site_context):
        course, _form = gated_course_with_form()
        app = _applied(client, course)
        client.force_login(UserFactory())

        response = client.get(_check_url(app))

        assert response.status_code == 404

    def test_every_page_gets_one_edit_link(self, client, mock_site_context):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        body = client.get(_check_url(app)).content.decode()

        assert body.count(_page_url(app, 1)) == 1
        assert body.count(_page_url(app, 2)) == 1

    def test_answers_are_grouped_under_their_page_titles(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        body = client.get(_check_url(app)).content.decode()

        assert "About you" in body
        assert "Supporting documents" in body

    def test_an_edit_link_carries_the_return_marker(self, client, mock_site_context):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        body = client.get(_check_url(app)).content.decode()

        assert _edit_url(app, 1) in body
        assert _edit_url(app, 2) in body

    def test_an_unanswered_required_question_blocks_submission(
        self, client, mock_site_context
    ):
        """The required question sits on page 1, which this applicant never
        submitted -- so only a whole-form check catches it.
        """
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        response = client.post(_check_url(app))

        assert response.status_code == 422

    def test_a_blocked_submission_stamps_nothing(self, client, mock_site_context):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        client.post(_check_url(app))

        app.form_progress.refresh_from_db()
        assert app.form_progress.completed_time is None

    def test_a_required_question_on_a_page_the_answers_close_does_not_block_submission(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        _add_required_page_opened_by_the_search_option(form)
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})

        response = client.post(_check_url(app))

        assert response.status_code == 302

    def test_a_required_question_on_a_page_the_answers_open_blocks_submission(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        _add_required_page_opened_by_the_search_option(form)
        app = _applied(client, course)
        name, _years, choice, _why = _questions_on(form, 1)
        client.post(
            _page_url(app, 1),
            {
                f"question_{name.id}": "Ada",
                f"question_{choice.id}": str(choice.options.get(text="Search").id),
            },
        )

        response = client.post(_check_url(app))

        assert response.status_code == 422
        assert "Question 6 needs an answer" in response.content.decode()

    def test_submitting_a_complete_application_stamps_it(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})

        client.post(_check_url(app))

        app.form_progress.refresh_from_db()
        assert app.form_progress.completed_time is not None

    def test_submitting_lands_on_the_dashboard(self, client, mock_site_context):
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})

        response = client.post(_check_url(app))

        assert response["Location"] == reverse("learner_interface:dashboard")

    def test_submitting_says_so_on_the_dashboard(self, client, mock_site_context):
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})

        response = client.post(_check_url(app))

        notices = [str(m) for m in get_messages(response.wsgi_request)]
        assert notices == [
            f"Your application for {course.title} has been submitted "
            "and is waiting for review."
        ]

    def test_submitting_leaves_the_application_submitted(
        self, client: Client, mock_site_context: Site
    ) -> None:
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})

        client.post(_check_url(app))

        app.refresh_from_db()
        assert app.state == CourseApplication.State.SUBMITTED
        assert app.submitted_at is not None

    def test_posting_for_an_application_that_is_not_a_draft_changes_nothing(
        self, client: Client, mock_site_context: Site
    ) -> None:
        course, _form = gated_course_with_form()
        app = _applied(client, course)
        CourseApplication.objects.filter(pk=app.pk).update(
            state=CourseApplication.State.WITHDRAWN,
            withdrawn_at=timezone.now(),
        )

        response = client.post(_check_url(app))

        app.refresh_from_db()
        app.form_progress.refresh_from_db()
        assert response["Location"] == reverse(
            "course_applications:status", kwargs={"pk": app.pk}
        )
        assert app.state == CourseApplication.State.WITHDRAWN
        assert app.form_progress.completed_time is None

    def test_losing_a_race_to_submit_leaves_the_sitting_open(
        self, client: Client, mock_site_context: Site
    ) -> None:
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})
        real_submit = submit_application

        def withdraw_then_submit(application: CourseApplication) -> CourseApplication:
            CourseApplication.objects.filter(pk=application.pk).update(
                state=CourseApplication.State.WITHDRAWN,
                withdrawn_at=timezone.now(),
            )
            return real_submit(application)

        with patch(
            "freedom_ls.course_applications.views.submit_application",
            side_effect=withdraw_then_submit,
        ):
            response = client.post(_check_url(app))

        app.form_progress.refresh_from_db()
        assert response["Location"] == reverse(
            "course_applications:status", kwargs={"pk": app.pk}
        )
        assert app.form_progress.completed_time is None

    def test_a_blocked_submission_says_nothing_about_success(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        response = client.post(_check_url(app))

        assert list(get_messages(response.wsgi_request)) == []

    def test_submitting_an_application_records_no_course_attempt(
        self, client, mock_site_context
    ):
        """An application is not coursework. Nothing about filling one in may
        show up as progress through the course it asks for.
        """
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})

        client.post(_check_url(app))

        assert CourseFormAttempt.objects.count() == 0

    def test_a_second_submission_does_not_restamp(self, client, mock_site_context):
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})
        client.post(_check_url(app))
        app.form_progress.refresh_from_db()
        first_stamp = app.form_progress.completed_time

        client.post(_check_url(app))

        app.form_progress.refresh_from_db()
        assert app.form_progress.completed_time == first_stamp


@pytest.mark.django_db
class TestCheckYourAnswersFollowsThePath:
    def test_an_off_path_page_has_no_card(self, client, mock_site_context):
        app, _yes, no, choice = _gated_application_with_a_skippable_page(client)
        client.post(_page_url(app, 1), {f"question_{choice.id}": str(no.id)})

        body = client.get(_check_url(app)).content.decode()

        assert _page_url(app, 1) in body
        assert _page_url(app, 2) not in body
        assert _page_url(app, 3) in body

    def test_an_off_path_question_has_no_row(self, client, mock_site_context):
        form = FormFactory(strategy=FormStrategy.UNSCORED)
        page = FormPageFactory(form=form, order=0, title="Only page")
        choice = FormQuestionFactory(
            form_page=page, type="multiple_choice", order=0, required=False
        )
        yes = QuestionOptionFactory(question=choice, value="yes", order=0)
        QuestionOptionFactory(question=choice, value="no", order=1)
        FormQuestionFactory(
            form_page=page,
            order=1,
            type="short_text",
            required=False,
            question="Employer name",
            condition_option=yes,
        )
        course = CourseFactory(access_config={"access_type": "application_gated"})
        course.application_form = form
        course.save(update_fields=["application_form"])
        app = _applied(client, course)

        body = client.get(_check_url(app)).content.decode()

        assert "Employer name" not in body

    def test_the_fallback_title_counts_on_the_path(self, client, mock_site_context):
        app, _yes, no, choice = _gated_application_with_a_skippable_page(client)
        client.post(_page_url(app, 1), {f"question_{choice.id}": str(no.id)})

        response = client.get(_check_url(app))

        assert [s["number"] for s in response.context["sections"]] == [1, 2]
        assert [s["edit_url"] for s in response.context["sections"]] == [
            _edit_url(app, 1),
            _edit_url(app, 3),
        ]

    def test_a_submitted_sitting_reads_its_recorded_path(
        self, client, mock_site_context
    ):
        app, yes, _no, choice = _gated_application_with_a_skippable_page(client)
        client.post(_page_url(app, 1), {f"question_{choice.id}": str(yes.id)})
        hidden = app.form_progress.form.pages.get(order=1).questions.get()
        third = app.form_progress.form.pages.get(order=2).questions.get()
        client.post(_page_url(app, 2), {f"question_{hidden.id}": "x"})
        client.post(_page_url(app, 3), {f"question_{third.id}": "y"})
        client.post(_check_url(app))
        page_two = app.form_progress.form.pages.get(order=1)
        page_two.condition_option = choice.options.get(value="no")
        page_two.save(update_fields=["condition_option"])

        response = client.get(_check_url(app))

        assert [s["number"] for s in response.context["sections"]] == [1, 2, 3]


@pytest.mark.django_db
class TestEditingFromTheCheckPageWalksNewQuestions:
    def _application(self, client):
        app, yes, no, choice = _gated_application_with_a_skippable_page(client)
        employer = app.form_progress.form.pages.get(order=1).questions.get()
        employer.required = True
        employer.save(update_fields=["required"])
        third = app.form_progress.form.pages.get(order=2).questions.get()
        client.post(_page_url(app, 1), {f"question_{choice.id}": str(no.id)})
        client.post(_page_url(app, 3), {f"question_{third.id}": "y"})
        return app, yes, no, choice, employer

    def test_opening_a_required_page_routes_through_it(self, client, mock_site_context):
        app, yes, _no, choice, _employer = self._application(client)

        response = client.post(
            _edit_url(app, 1), {f"question_{choice.id}": str(yes.id)}
        )

        assert response["Location"] == _edit_url(app, 2)

    def test_saving_the_opened_page_returns_to_review(self, client, mock_site_context):
        app, yes, _no, choice, employer = self._application(client)
        client.post(_edit_url(app, 1), {f"question_{choice.id}": str(yes.id)})

        response = client.post(_edit_url(app, 2), {f"question_{employer.id}": "Acme"})

        assert response["Location"] == _check_url(app)

    def test_closing_the_page_returns_straight_to_review(
        self, client, mock_site_context
    ):
        app, _yes, no, choice, _employer = self._application(client)

        response = client.post(_edit_url(app, 1), {f"question_{choice.id}": str(no.id)})

        assert response["Location"] == _check_url(app)


@pytest.mark.django_db
class TestApplicationFormPageMarkup:
    def test_each_question_type_on_the_page_gets_its_input(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        body = client.get(_page_url(app, 1)).content.decode()

        assert 'type="text"' in body
        assert 'type="number"' in body
        assert 'type="radio"' in body
        assert "<textarea" in body

    def test_the_page_offers_the_page_jump_nav(self, client, mock_site_context):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        body = client.get(_page_url(app, 1)).content.decode()

        assert 'aria-label="Application pages"' in body

    def test_the_last_page_still_says_next(self, client, mock_site_context):
        """The check-your-answers page is one more step, not a different kind
        of step, so the button that reaches it reads like every other one."""
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        body = client.get(_page_url(app, 2)).content.decode()

        assert "Next" in body
        assert "Check your answers" not in body

    def test_a_submitted_application_says_it_can_no_longer_be_changed(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        app = _applied(client, course)
        submit_application(app)
        app.form_progress.complete()

        body = client.get(_page_url(app, 1)).content.decode()

        assert "can no longer be changed" in body

    def test_a_submitted_application_disables_its_inputs(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        app = _applied(client, course)
        submit_application(app)
        app.form_progress.complete()

        body = client.get(_page_url(app, 1)).content.decode()

        assert "disabled" in body


@pytest.mark.django_db
class TestCheckYourAnswersMarkup:
    def test_a_file_answer_shows_its_name_and_a_download_link(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _applied(client, course)
        file_question = _questions_on(form, 2)[0]
        client.post(
            reverse(
                "form_engine:question_file_upload",
                kwargs={
                    "progress_pk": app.form_progress.pk,
                    "question_pk": file_question.pk,
                },
            ),
            {"file": SimpleUploadedFile("id-scan.png", png_bytes())},
        )

        body = client.get(_check_url(app)).content.decode()

        assert "id-scan.png" in body

    def test_an_open_application_offers_a_submit_button(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        response = client.get(_check_url(app))

        assert response.context["can_submit"]

    def test_a_submitted_application_cannot_be_submitted_again(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})
        client.post(_check_url(app))

        response = client.get(_check_url(app))

        assert not response.context["can_submit"]

    def test_a_submitted_application_offers_no_change_links(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})
        client.post(_check_url(app))

        body = client.get(_check_url(app)).content.decode()

        assert _page_url(app, 1) not in body

    def test_an_unanswered_question_says_so(self, client, mock_site_context):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        body = client.get(_check_url(app)).content.decode()

        assert "Not answered" in body


_CHECK_PAGE_INTRO = "Nothing is sent until you press Submit application."
_CHECK_PAGE_NOTICES = {
    "submitted": "This application has been submitted and is waiting for review.",
    "decided": "A decision has been made on this application, so it can no longer be changed.",
    "withdrawn": "You withdrew this application, so it can no longer be changed.",
}


@pytest.mark.django_db
class TestCheckYourAnswersWhenNotADraft:
    @pytest.mark.parametrize(
        ("state", "submitted", "notice"),
        [
            (CourseApplication.State.SUBMITTED, True, "submitted"),
            (CourseApplication.State.APPROVED, True, "decided"),
            (CourseApplication.State.REJECTED, True, "decided"),
            (CourseApplication.State.WITHDRAWN, True, "withdrawn"),
            (CourseApplication.State.WITHDRAWN, False, "withdrawn"),
        ],
    )
    def test_a_non_draft_application_is_read_only_with_a_notice_for_its_state(
        self,
        client: Client,
        mock_site_context: Site,
        state: CourseApplication.State,
        submitted: bool,
        notice: str,
    ) -> None:
        """The page used to keep inviting edits on a withdrawn draft, and told
        a decided or withdrawn application it was still waiting for review."""
        course, _form = gated_course_with_form()
        app = _applied(client, course)
        now = timezone.now()
        State = CourseApplication.State
        CourseApplication.objects.filter(pk=app.pk).update(
            state=state,
            submitted_at=now if submitted else None,
            decided_at=now if state in (State.APPROVED, State.REJECTED) else None,
            rejection_message="Not this time." if state == State.REJECTED else "",
            withdrawn_at=now if state == State.WITHDRAWN else None,
        )

        body = client.get(_check_url(app)).content.decode()

        assert _CHECK_PAGE_INTRO not in body
        assert _page_url(app, 1) not in body
        assert _CHECK_PAGE_NOTICES[notice] in body
        assert "Your application has been submitted." not in body
        assert reverse("course_applications:status", kwargs={"pk": app.pk}) in body

    def test_a_draft_shows_the_intro_edit_links_and_no_notice(
        self, client: Client, mock_site_context: Site
    ) -> None:
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        body = client.get(_check_url(app)).content.decode()

        assert _CHECK_PAGE_INTRO in body
        assert _edit_url(app, 1) in body
        assert not any(text in body for text in _CHECK_PAGE_NOTICES.values())


# ---------------------------------------------------------------------------
# Rejected (invalid) typed answers
# ---------------------------------------------------------------------------


def _course_with_single_question(question_type: str, *, required: bool = False):
    """An application-gated course whose one-page form carries a single
    question of `question_type`, isolated from the rest of the fixture form
    so a rejected answer's effect on paging and completion is unambiguous.
    """
    form = FormFactory(strategy=FormStrategy.UNSCORED)
    page = FormPageFactory(form=form, order=0, title="About you")
    question = FormQuestionFactory(
        form_page=page,
        type=question_type,
        order=0,
        question="Answer",
        required=required,
    )
    course = CourseFactory(access_config={"access_type": "application_gated"})
    course.application_form = form
    course.save(update_fields=["application_form"])
    return course, question


@pytest.mark.django_db
class TestApplicationFormPageRejectedAnswers:
    def test_an_invalid_date_answer_returns_422_and_stores_nothing(
        self, client, mock_site_context
    ):
        course, question = _course_with_single_question("date")
        app = _applied(client, course)

        response = client.post(_page_url(app, 1), {f"question_{question.id}": "banana"})

        assert response.status_code == 422
        assert app.form_progress.answers.filter(question=question).count() == 0

    def test_an_invalid_answer_names_the_question_in_the_context(
        self, client, mock_site_context
    ):
        course, question = _course_with_single_question("date")
        app = _applied(client, course)

        response = client.post(_page_url(app, 1), {f"question_{question.id}": "banana"})

        assert (
            response.context["rejected_answers_error"]
            == "Question 1 needs a valid answer."
        )

    def test_a_rejected_email_comes_back_in_the_input_value(
        self, client, mock_site_context
    ):
        course, question = _course_with_single_question("email")
        app = _applied(client, course)

        body = client.post(
            _page_url(app, 1), {f"question_{question.id}": "not-an-email"}
        ).content.decode()

        assert 'value="not-an-email"' in body

    def test_a_corrected_resubmission_advances_and_stores(
        self, client, mock_site_context
    ):
        course, question = _course_with_single_question("email")
        app = _applied(client, course)
        client.post(_page_url(app, 1), {f"question_{question.id}": "not-an-email"})

        response = client.post(
            _page_url(app, 1), {f"question_{question.id}": "ada@example.com"}
        )

        assert response["Location"] == _check_url(app)
        answer = app.form_progress.answers.get(question=question)
        assert answer.text_answer == "ada@example.com"

    def test_a_rejected_required_answer_still_blocks_final_submission(
        self, client, mock_site_context
    ):
        """The rejected date stores no row, so the whole-form check on
        check-your-answers still finds the required question unanswered."""
        course, question = _course_with_single_question("date", required=True)
        app = _applied(client, course)
        client.post(_page_url(app, 1), {f"question_{question.id}": "banana"})

        response = client.post(_check_url(app))

        assert response.status_code == 422
        app.form_progress.refresh_from_db()
        assert app.form_progress.completed_time is None


# ---------------------------------------------------------------------------
# GA4 generate_lead flag
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestApplyAnalyticsEvent:
    def test_post_apply_for_a_no_form_course_records_the_access_request(
        self, client, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory(
            slug="no-form-course", access_config={"access_type": "application_gated"}
        )
        client.force_login(user)

        client.post(
            reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        )

        assert client.session["google_analytics_events"] == [
            {
                "name": "course_access_requested",
                "params": {
                    "course_slug": "no-form-course",
                    "course_id": str(course.id),
                    "access_type": "application_gated",
                    "request_kind": "application",
                },
            }
        ]

    def test_apply_for_a_course_with_a_form_does_not_record_an_event(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        user = UserFactory()
        client.force_login(user)

        client.get(
            reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        )

        assert "google_analytics_events" not in client.session

    def test_apply_for_an_existing_application_does_not_record_an_event(
        self, client, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory()
        CourseApplicationFactory(user=user, course=course)
        client.force_login(user)

        client.get(
            reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        )

        assert "google_analytics_events" not in client.session


@pytest.mark.django_db
class TestCheckYourAnswersAnalyticsEvent:
    def test_submitting_a_complete_application_records_the_access_request(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})

        client.post(_check_url(app))

        assert client.session["google_analytics_events"] == [
            {
                "name": "course_access_requested",
                "params": {
                    "course_slug": course.slug,
                    "course_id": str(course.id),
                    "access_type": "application_gated",
                    "request_kind": "application",
                },
            }
        ]

    def test_a_blocked_submission_does_not_record_an_event(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        client.post(_check_url(app))

        assert "google_analytics_events" not in client.session


# Tests for deferred login — user intent survives authentication.
#
# Covers:
# - Deferred-login flows via `acquisition_login_required`: anonymous access to
#   `initiate_course_access` / `apply` redirects to signup (or login, once
#   signups are closed) with `?next=` set, and after login the free/gated
#   course flows land the learner correctly.
# - The signup arm of the same funnel: intent survives account creation and
#   email verification, not only sign-in.


# ---------------------------------------------------------------------------
# Deferred-login flows: free course via acquisition_login_required
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_access_to_initiate_redirects_to_signup_with_next(
    mock_site_context, course_with_topic
):
    """Anonymous GET of initiate_course_access → 302 to signup with ?next= set."""
    course = course_with_topic(access_type="free")

    client = Client()
    access_url = reverse(
        "learner_interface:initiate_course_access",
        kwargs={"course_slug": course.slug},
    )
    response = client.get(access_url, follow=False)

    assert response.status_code == 302
    signup_url = reverse("account_signup")
    assert response["Location"].startswith(signup_url)
    assert _next_param(response["Location"]) == access_url


@pytest.mark.django_db
def test_anonymous_access_to_initiate_with_signups_closed_goes_to_login(
    mock_site_context, course_with_topic
):
    """Signups closed on the site falls initiate_course_access back to login."""
    SiteSignupPolicyFactory(allow_signups=False)
    course = course_with_topic(access_type="free")

    client = Client()
    access_url = reverse(
        "learner_interface:initiate_course_access",
        kwargs={"course_slug": course.slug},
    )
    response = client.get(access_url, follow=False)

    assert response.status_code == 302
    login_url = reverse("account_login")
    assert response["Location"].startswith(login_url)
    assert _next_param(response["Location"]) == access_url


@pytest.mark.django_db
def test_deferred_login_free_course_enrolls_and_redirects(
    mock_site_context, logged_in_client, course_with_topic
):
    """After login, the ?next= chain lands the learner inside the course.

    Simulates the full deferred-login flow using force_login (representing
    what happens immediately after a successful login with `next` set).
    """
    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)

    access_url = reverse(
        "learner_interface:initiate_course_access",
        kwargs={"course_slug": course.slug},
    )
    response = client.get(access_url, follow=False)

    # The view registers the user and redirects to course_home which then
    # redirects into the first item — we only need to verify the first hop.
    assert response.status_code == 302
    assert LearnerCourseRegistration.objects.filter(
        learner__user=user, course=course
    ).exists()


@pytest.mark.django_db
def test_anonymous_access_to_apply_redirects_to_applicant_details(
    mock_site_context, course_with_topic
):
    """Anonymous GET of apply on a form-less gated course → the details step."""
    course = course_with_topic(access_type="application_gated")
    client = Client()
    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    response = client.get(apply_url, follow=False)

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "course_applications:applicant_details", kwargs={"course_slug": course.slug}
    )


@pytest.mark.django_db
def test_deferred_login_gated_course_lands_on_apply_page(
    mock_site_context, logged_in_client, course_with_topic
):
    """After login, the ?next= chain lands an authenticated user on the apply page.

    The apply view's GET shows the confirmation page — it must NOT auto-POST.
    """
    course = course_with_topic(access_type="application_gated")
    user = UserFactory()
    client = logged_in_client(user)

    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    response = client.get(apply_url, follow=False)

    # The apply GET shows the confirmation page (200), not an auto-submitted POST.
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Deferred-login flow: apply via acquisition_login_required
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_apply_get_creates_no_application(mock_site_context, client):
    """Opening the confirmation page after the details step submits nothing."""
    course = CourseFactory(access_config={"access_type": "application_gated"})
    _post_details(client, course)

    response = client.get(_apply_url(course))

    assert response.status_code == 200
    assert not CourseApplication.objects.filter(course=course).exists()


@pytest.mark.django_db
def test_signed_in_apply_repeat_submissions_stay_idempotent(mock_site_context, client):
    """A second POST to apply after signing in does not duplicate the application."""
    course = CourseFactory()
    user = UserFactory()
    client.force_login(user)

    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    client.post(apply_url)
    client.post(apply_url)

    assert CourseApplication.objects.filter(user=user, course=course).count() == 1


# ---------------------------------------------------------------------------
# Deferred-login flow: initiate_course_access on a coming-soon course
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_deferred_login_initiate_access_coming_soon_creates_no_registration(
    mock_site_context, client
):
    """A coming-soon course is not enrollable, deferred login or not.

    The anonymous GET redirects to login with next set to the access URL.
    Following that next after signing in lands on the course detail page
    without registering the learner, matching initiate_course_access's own
    coming-soon fallback.
    """
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
    user = UserFactory()

    access_url = reverse(
        "learner_interface:initiate_course_access",
        kwargs={"course_slug": course.slug},
    )
    response = client.get(access_url, follow=False)
    next_url = _next_param(response["Location"])

    client.force_login(user)
    followed = client.get(next_url)

    assert followed.status_code == 302
    assert followed["Location"] == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    assert not LearnerCourseRegistration.objects.filter(
        learner__user=user, course=course
    ).exists()


# ---------------------------------------------------------------------------
# Deferred-login flow: application_status ownership after sign-in
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_signed_in_owner_sees_status_page(mock_site_context, client):
    """The application owner reaches their status page."""
    owner = UserFactory()
    app = CourseApplicationFactory(user=owner)
    client.force_login(owner)

    response = client.get(reverse("course_applications:status", kwargs={"pk": app.pk}))

    assert response.status_code == 200


@pytest.mark.django_db
def test_signed_in_non_owner_gets_404_on_status_page(mock_site_context, client):
    """A signed-in user who does not own the application gets 404."""
    app = CourseApplicationFactory(user=UserFactory())
    client.force_login(UserFactory())

    response = client.get(reverse("course_applications:status", kwargs={"pk": app.pk}))

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Hidden courses: login redirect, never a 404 (no enumeration signal)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_access_to_hidden_course_apply_is_404(mock_site_context):
    """The visibility check runs for an anonymous visitor too."""
    course = CourseFactory(visibility=CourseVisibility.HIDDEN)
    client = Client()

    url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
    response = client.get(url, follow=False)

    assert response.status_code == 404


@pytest.mark.django_db
def test_anonymous_access_to_hidden_course_initiate_redirects_to_signup_not_404(
    mock_site_context,
):
    """acquisition_login_required runs before any visibility check, so an
    anonymous visitor to a hidden course's access URL gets a signup redirect
    rather than the 404 that confirms a registered learner would eventually
    see."""
    course = CourseFactory(visibility=CourseVisibility.HIDDEN)
    client = Client()

    url = reverse(
        "learner_interface:initiate_course_access", kwargs={"course_slug": course.slug}
    )
    response = client.get(url, follow=False)

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('account_signup')}?next={url}"


@pytest.mark.django_db
def test_anonymous_access_to_status_for_hidden_course_application_redirects_to_login(
    mock_site_context,
):
    """A session that holds no such application is sent to log in, the same as
    for a visible course, so the redirect says nothing about the course."""
    course = CourseFactory(visibility=CourseVisibility.HIDDEN)
    owner = UserFactory()
    app = CourseApplicationFactory(user=owner, course=course)
    client = Client()

    url = reverse("course_applications:status", kwargs={"pk": app.pk})
    response = client.get(url, follow=False)

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('account_login')}?next={url}"


# ---------------------------------------------------------------------------
# Anonymous apply on a form-less course
# ---------------------------------------------------------------------------


def _apply_url(course) -> str:
    return reverse("course_applications:apply", kwargs={"course_slug": course.slug})


def _details_url(course) -> str:
    return reverse(
        "course_applications:applicant_details", kwargs={"course_slug": course.slug}
    )


def _details_data(**overrides: str) -> dict[str, str]:
    data = {
        "email": "  Ada@Example.com ",
        "first_name": "Ada",
        "last_name": "Lovelace",
    }
    data.update(overrides)
    return data


def _post_details(client, course, **overrides: str):
    return client.post(_details_url(course), _details_data(**overrides))


@pytest.fixture
def gated_course(mock_site_context):
    return CourseFactory(access_config={"access_type": "application_gated"})


@pytest.mark.django_db
def test_anonymous_apply_on_coming_soon_course_redirects_to_course_detail(
    mock_site_context, client
):
    course = CourseFactory(
        visibility=CourseVisibility.COMING_SOON,
        access_config={"access_type": "application_gated"},
    )

    response = client.get(_apply_url(course))

    assert response["Location"] == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )


def _coming_soon_gated_course():
    return CourseFactory(
        visibility=CourseVisibility.COMING_SOON,
        access_config={"access_type": "application_gated"},
    )


@pytest.mark.django_db
def test_anonymous_apply_on_coming_soon_course_with_an_application_reaches_status(
    mock_site_context, client
):
    """An applicant on a course later flipped to coming-soon still reaches their
    status page, where the only way to resend the claim email lives."""
    course = _coming_soon_gated_course()
    course.visibility = CourseVisibility.PUBLISHED
    course.save(update_fields=["visibility"])
    _post_details(client, course)
    client.post(_apply_url(course))
    application = CourseApplication.objects.get(course=course)
    course.visibility = CourseVisibility.COMING_SOON
    course.save(update_fields=["visibility"])

    response = client.get(_apply_url(course))

    assert response["Location"] == reverse(
        "course_applications:status", kwargs={"pk": application.pk}
    )


@pytest.mark.django_db
@override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True)
def test_anonymous_apply_honours_the_visibility_preview_override(
    mock_site_context, client
):
    course = _coming_soon_gated_course()

    response = client.get(_apply_url(course))

    assert response["Location"] == _details_url(course)


@pytest.mark.django_db
@override_settings(OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE=True)
def test_details_step_honours_the_visibility_preview_override(
    mock_site_context, client
):
    course = _coming_soon_gated_course()

    response = client.get(_details_url(course))

    assert response.status_code == 200


@pytest.mark.django_db
def test_details_step_on_coming_soon_course_with_an_application_reaches_status(
    mock_site_context, client
):
    course = _coming_soon_gated_course()
    course.visibility = CourseVisibility.PUBLISHED
    course.save(update_fields=["visibility"])
    _post_details(client, course)
    client.post(_apply_url(course))
    application = CourseApplication.objects.get(course=course)
    course.visibility = CourseVisibility.COMING_SOON
    course.save(update_fields=["visibility"])

    response = client.get(_details_url(course))

    assert response["Location"] == reverse(
        "course_applications:status", kwargs={"pk": application.pk}
    )


@pytest.mark.django_db
def test_details_step_get_renders_the_three_fields(client, gated_course):
    response = client.get(_details_url(gated_course))

    content = response.content.decode()
    assert response.status_code == 200
    assert 'name="email"' in content
    assert 'name="first_name"' in content
    assert 'name="last_name"' in content


@pytest.mark.django_db
def test_details_step_on_coming_soon_course_redirects_to_course_detail(
    mock_site_context, client
):
    course = CourseFactory(
        visibility=CourseVisibility.COMING_SOON,
        access_config={"access_type": "application_gated"},
    )

    response = client.get(_details_url(course))

    assert response["Location"] == reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )


@pytest.mark.django_db
def test_details_step_on_hidden_course_is_404(mock_site_context, client):
    course = CourseFactory(visibility=CourseVisibility.HIDDEN)

    assert client.get(_details_url(course)).status_code == 404


@pytest.mark.django_db
def test_details_step_signed_in_redirects_to_apply(client, gated_course):
    client.force_login(UserFactory())

    response = client.get(_details_url(gated_course))

    assert response["Location"] == _apply_url(gated_course)


@pytest.mark.django_db
def test_details_step_invalid_post_is_422(client, gated_course):
    response = _post_details(client, gated_course, email="not-an-email")

    assert response.status_code == 422


@pytest.mark.django_db
def test_details_step_valid_post_creates_applicant_with_normalised_email(
    client, gated_course
):
    response = _post_details(client, gated_course)

    applicant = AnonymousApplicant.objects.get(course=gated_course)
    assert response["Location"] == _apply_url(gated_course)
    assert applicant.email == "ada@example.com"


@pytest.mark.django_db
def test_details_step_valid_post_creates_no_user(client, gated_course):
    users_before = User._base_manager.count()

    _post_details(client, gated_course)

    assert User._base_manager.count() == users_before


@pytest.mark.django_db
def test_apply_after_details_links_previous_to_details_step(client, gated_course):
    _post_details(client, gated_course)

    response = client.get(_apply_url(gated_course))

    assert response.status_code == 200
    assert f'href="{_details_url(gated_course)}"' in response.content.decode()


@pytest.mark.django_db
def test_anonymous_apply_post_creates_application_without_user(client, gated_course):
    _post_details(client, gated_course)

    client.post(_apply_url(gated_course))

    application = CourseApplication.objects.get(course=gated_course)
    assert application.user is None
    assert application.anonymous_applicant is not None


@pytest.mark.django_db
def test_anonymous_apply_post_redirects_to_status_page(client, gated_course):
    _post_details(client, gated_course)

    response = client.post(_apply_url(gated_course))

    application = CourseApplication.objects.get(course=gated_course)
    assert response["Location"] == reverse(
        "course_applications:status", kwargs={"pk": application.pk}
    )


@pytest.mark.django_db
def test_anonymous_apply_post_queues_application_submitted_event(client, gated_course):
    _post_details(client, gated_course)

    with patch(
        "freedom_ls.course_applications.views.record_application_submitted"
    ) as record:
        client.post(_apply_url(gated_course))

    record.assert_called_once()


@pytest.mark.django_db
def test_status_page_renders_for_the_applying_session(client, gated_course):
    _post_details(client, gated_course)
    client.post(_apply_url(gated_course))
    application = CourseApplication.objects.get(course=gated_course)

    response = client.get(
        reverse("course_applications:status", kwargs={"pk": application.pk})
    )

    assert response.status_code == 200
    assert "Before anyone reviews it" in response.content.decode()


@pytest.mark.django_db
def test_status_page_sends_a_fresh_client_to_log_in(client, gated_course):
    application = CourseApplicationFactory(course=gated_course, anonymous=True)
    url = reverse("course_applications:status", kwargs={"pk": application.pk})

    response = Client().get(url)

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('account_login')}?next={url}"


@pytest.mark.django_db
def test_status_page_is_404_for_a_signed_in_non_owner(client, gated_course):
    application = CourseApplicationFactory(course=gated_course, anonymous=True)
    client.force_login(UserFactory())

    response = client.get(
        reverse("course_applications:status", kwargs={"pk": application.pk})
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_details_step_after_submission_redirects_to_status_page(client, gated_course):
    _post_details(client, gated_course)
    client.post(_apply_url(gated_course))
    application = CourseApplication.objects.get(course=gated_course)

    response = client.get(_details_url(gated_course))

    assert response["Location"] == reverse(
        "course_applications:status", kwargs={"pk": application.pk}
    )


@pytest.mark.django_db
def test_reposting_details_updates_the_same_applicant(client, gated_course):
    _post_details(client, gated_course)

    _post_details(client, gated_course, first_name="Augusta")

    applicant = AnonymousApplicant.objects.get(course=gated_course)
    assert applicant.first_name == "Augusta"


def _enumeration_emails() -> dict[str, str]:
    return {
        "new": "brand-new@example.com",
        "same_site": str(UserFactory().email),
        "other_site": str(UserFactory(site=SiteFactory()).email),
    }


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["new", "same_site", "other_site"])
def test_details_post_answers_the_same_whether_or_not_the_address_has_an_account(
    client, gated_course, kind
):
    response = _post_details(client, gated_course, email=_enumeration_emails()[kind])

    assert response.status_code == 302
    assert response["Location"] == _apply_url(gated_course)


@pytest.mark.django_db
def test_details_post_reads_no_user_table(client, gated_course):
    with CaptureQueriesContext(connection) as queries:
        _post_details(client, gated_course)

    sql = " ".join(query["sql"] for query in queries.captured_queries)
    assert (
        any(table in sql for table in ("accounts_user", "account_emailaddress"))
        is False
    )


@pytest.mark.django_db
def test_details_post_succeeds_with_csrf_enforced(gated_course):
    client = Client(enforce_csrf_checks=True)
    client.get(_details_url(gated_course))
    token = client.cookies["csrftoken"].value

    response = client.post(
        _details_url(gated_course), _details_data(csrfmiddlewaretoken=token)
    )

    assert response.status_code == 302


@pytest.mark.django_db
def test_details_step_links_both_consent_checkboxes_to_the_legal_documents(
    client, gated_course, site, legal_repo_mock
):
    SiteSignupPolicyFactory(site=site, require_terms_acceptance=True)

    content = client.get(_details_url(gated_course)).content.decode()

    assert "I accept the" in content
    assert reverse("accounts:legal_doc", kwargs={"doc_type": "terms"}) in content
    assert reverse("accounts:legal_doc", kwargs={"doc_type": "privacy"}) in content
    assert 'name="accept_terms"' in content
    assert 'name="accept_privacy"' in content


@pytest.mark.django_db
def test_details_step_post_without_the_consent_is_422(
    client, gated_course, site, legal_repo_mock
):
    SiteSignupPolicyFactory(site=site, require_terms_acceptance=True)

    response = _post_details(client, gated_course)

    assert response.status_code == 422


DETAILS_RATE_LIMITS = {"application_details": "5/m/ip,5/h/key"}


def _post_details_from_distinct_clients(course, count: int, **overrides: str):
    """Post the details step `count` times, each from a fresh browser and IP."""
    return [
        Client().post(
            _details_url(course),
            _details_data(**overrides),
            REMOTE_ADDR=f"10.0.0.{index + 1}",
        )
        for index in range(count)
    ]


def _post_details_from_one_ip(course, count: int):
    """Post the details step `count` times from one IP, each a fresh browser
    applying under its own address."""
    return [
        Client().post(
            _details_url(course),
            _details_data(email=f"applicant{index}@example.com"),
            REMOTE_ADDR="10.9.9.9",
        )
        for index in range(count)
    ]


@pytest.mark.django_db
def test_details_step_sixth_post_from_one_ip_is_rate_limited(gated_course):
    with override_settings(ACCOUNT_RATE_LIMITS=DETAILS_RATE_LIMITS):
        cache.clear()
        _post_details_from_one_ip(gated_course, 5)

        response = Client().post(
            _details_url(gated_course),
            _details_data(email="other@example.com"),
            REMOTE_ADDR="10.9.9.9",
        )

    assert response.status_code == 429


@pytest.mark.django_db
def test_details_step_sixth_post_for_one_address_from_a_new_ip_is_rate_limited(
    gated_course,
):
    with override_settings(ACCOUNT_RATE_LIMITS=DETAILS_RATE_LIMITS):
        cache.clear()
        _post_details_from_distinct_clients(gated_course, 5)

        response = Client().post(
            _details_url(gated_course), _details_data(), REMOTE_ADDR="10.1.1.1"
        )

    assert response.status_code == 429


@pytest.mark.django_db
def test_details_step_post_for_a_different_address_from_a_new_ip_is_not_limited(
    gated_course,
):
    with override_settings(ACCOUNT_RATE_LIMITS=DETAILS_RATE_LIMITS):
        cache.clear()
        _post_details_from_distinct_clients(gated_course, 5)

        response = Client().post(
            _details_url(gated_course),
            _details_data(email="grace@example.com"),
            REMOTE_ADDR="10.1.1.1",
        )

    assert response.status_code != 429


@pytest.mark.django_db
def test_details_step_invalid_posts_do_not_spend_the_address_limit(gated_course):
    with override_settings(ACCOUNT_RATE_LIMITS=DETAILS_RATE_LIMITS):
        cache.clear()
        _post_details_from_distinct_clients(gated_course, 5, first_name="")

        response = Client().post(
            _details_url(gated_course), _details_data(), REMOTE_ADDR="10.1.1.1"
        )

    assert response.status_code == 302


@pytest.mark.django_db
def test_details_step_honeypot_trips_spend_the_address_limit(gated_course):
    with override_settings(ACCOUNT_RATE_LIMITS=DETAILS_RATE_LIMITS):
        cache.clear()
        _post_details_from_distinct_clients(gated_course, 5, fax_number="bot")

        response = Client().post(
            _details_url(gated_course), _details_data(), REMOTE_ADDR="10.1.1.1"
        )

    assert response.status_code == 429


@pytest.mark.django_db
def test_details_step_name_edits_do_not_spend_the_address_limit(client, gated_course):
    with override_settings(ACCOUNT_RATE_LIMITS=DETAILS_RATE_LIMITS):
        cache.clear()
        _post_details(client, gated_course)
        for name in ("Grace", "Ada", "Grace", "Ada", "Grace"):
            _post_details(client, gated_course, first_name=name)

        response = _post_details(client, gated_course, first_name="Mary")

    assert response.status_code == 302


@pytest.mark.django_db
def test_details_step_name_edit_on_an_exhausted_address_is_not_refused(
    client, gated_course
):
    """Anyone can post an address and spend its bucket; the applicant who
    already holds that address is still allowed to correct their name."""
    with override_settings(ACCOUNT_RATE_LIMITS=DETAILS_RATE_LIMITS):
        cache.clear()
        _post_details(client, gated_course)
        _post_details_from_distinct_clients(gated_course, 5)

        response = _post_details(client, gated_course, first_name="Mary")

    assert response.status_code == 302
    assert (
        AnonymousApplicant.objects.get(
            pk=client.session[ANONYMOUS_APPLICANTS_SESSION_KEY][str(gated_course.pk)]
        ).first_name
        == "Mary"
    )


def _repost_details_with_a_new_address(client):
    """Post details on a form course, then repost with another address; returns
    the earlier claim link's url and the applicant."""
    course, _form = gated_course_with_form()
    _post_details(client, course)
    applicant = AnonymousApplicant.objects.get(course=course)
    earlier_url = _claim_url(applicant)
    mail.outbox.clear()
    _post_details(client, course, email="new@example.com")
    applicant.refresh_from_db()
    return earlier_url, applicant


@pytest.mark.django_db
def test_reposting_details_with_a_new_address_bumps_the_claim_link_version(
    mock_site_context, client
):
    _earlier_url, applicant = _repost_details_with_a_new_address(client)

    assert applicant.claim_link_version == 1


@pytest.mark.django_db
def test_reposting_details_with_a_new_address_sends_one_email_to_it(
    mock_site_context, client
):
    _repost_details_with_a_new_address(client)

    assert [message.to for message in mail.outbox] == [["new@example.com"]]


@pytest.mark.django_db
def test_reposting_details_with_a_new_address_invalidates_the_earlier_link(
    mock_site_context, client
):
    earlier_url, _applicant = _repost_details_with_a_new_address(client)

    response = client.get(earlier_url)

    assert response.context["claim_state"] == "invalid"


@pytest.mark.django_db
def test_reposting_details_with_only_a_new_name_keeps_the_claim_link_version(
    mock_site_context, client
):
    course, _form = gated_course_with_form()
    _post_details(client, course)

    _post_details(client, course, first_name="Grace")

    assert AnonymousApplicant.objects.get(course=course).claim_link_version == 0


@pytest.mark.django_db
def test_reposting_details_with_only_a_new_name_sends_nothing(
    mock_site_context, client
):
    course, _form = gated_course_with_form()
    _post_details(client, course)
    mail.outbox.clear()

    _post_details(client, course, first_name="Grace")

    assert mail.outbox == []


@pytest.mark.django_db
def test_details_step_changing_the_address_spends_the_new_addresss_limit(
    client, gated_course
):
    with override_settings(ACCOUNT_RATE_LIMITS=DETAILS_RATE_LIMITS):
        cache.clear()
        _post_details(client, gated_course)
        _post_details_from_distinct_clients(gated_course, 4, email="new@example.com")
        _post_details(client, gated_course, email="new@example.com")

        response = Client().post(
            _details_url(gated_course),
            _details_data(email="new@example.com"),
            REMOTE_ADDR="10.1.1.1",
        )

    assert response.status_code == 429


@pytest.mark.django_db
def test_details_step_limited_address_is_refused_before_anything_is_written(
    gated_course,
):
    with override_settings(ACCOUNT_RATE_LIMITS=DETAILS_RATE_LIMITS):
        cache.clear()
        _post_details_from_distinct_clients(gated_course, 5)
        Client().post(
            _details_url(gated_course), _details_data(), REMOTE_ADDR="10.1.1.1"
        )

    assert AnonymousApplicant.objects.count() == 5


@pytest.mark.django_db
def test_two_overlapping_first_posts_from_one_browser_make_one_applicant(
    gated_course,
):
    cache.clear()
    Client().post(_details_url(gated_course), _details_data(), REMOTE_ADDR="10.2.2.2")

    Client().post(_details_url(gated_course), _details_data(), REMOTE_ADDR="10.2.2.2")

    assert AnonymousApplicant.objects.count() == 1


@pytest.mark.django_db
def test_the_second_of_two_overlapping_first_posts_is_sent_back_to_the_step(
    gated_course,
):
    cache.clear()
    Client().post(_details_url(gated_course), _details_data(), REMOTE_ADDR="10.2.2.2")

    response = Client().post(
        _details_url(gated_course), _details_data(), REMOTE_ADDR="10.2.2.2"
    )

    assert response["Location"] == _details_url(gated_course)


@pytest.mark.django_db
def test_a_long_valid_address_still_makes_an_applicant(gated_course):
    """The in-flight key used to carry the address verbatim, and a long one
    pushed it past what the cache table could store."""
    cache.clear()
    long_email = "a@" + ".".join(["b" * 60] * 3) + ".com"

    Client().post(
        _details_url(gated_course),
        _details_data(email=long_email),
        REMOTE_ADDR="10.2.2.2",
    )

    assert AnonymousApplicant.objects.filter(email=long_email).exists()


@pytest.mark.django_db
def test_the_in_flight_key_carries_neither_the_address_nor_the_ip(gated_course, rf):
    """The production cache is a database table whose rows outlive expiry."""
    request = rf.post(_details_url(gated_course), REMOTE_ADDR="10.2.2.2")
    request.session = SessionStore()

    key = _details_in_flight_key(request, gated_course, "ada@example.com")

    assert ("ada@example.com" in key, "10.2.2.2" in key, len(key) < 250) == (
        False,
        False,
        True,
    )


@pytest.mark.django_db
def test_the_same_address_from_two_networks_makes_two_applicants(gated_course):
    cache.clear()
    Client().post(_details_url(gated_course), _details_data(), REMOTE_ADDR="10.2.2.2")

    Client().post(_details_url(gated_course), _details_data(), REMOTE_ADDR="10.3.3.3")

    assert AnonymousApplicant.objects.count() == 2


# ---------------------------------------------------------------------------
# Only application-gated courses take anonymous applications
# ---------------------------------------------------------------------------


@pytest.fixture
def free_course(mock_site_context):
    return CourseFactory(access_config={"access_type": "free"})


@pytest.mark.django_db
def test_anonymous_apply_on_a_free_course_goes_to_the_auth_page(client, free_course):
    response = client.get(_apply_url(free_course))

    location = response["Location"]
    assert (location.split("?")[0], _next_param(location)) == (
        reverse("account_signup"),
        _apply_url(free_course),
    )


@pytest.mark.django_db
def test_anonymous_apply_post_on_a_free_course_creates_nothing(client, free_course):
    client.post(_apply_url(free_course))

    assert CourseApplication.objects.count() == 0


@pytest.mark.django_db
def test_anonymous_details_step_on_a_free_course_goes_to_the_auth_page(
    client, free_course
):
    response = client.get(_details_url(free_course))

    location = response["Location"]
    assert (location.split("?")[0], _next_param(location)) == (
        reverse("account_signup"),
        _details_url(free_course),
    )


@pytest.mark.django_db
def test_anonymous_details_post_on_a_free_course_creates_no_applicant(
    client, free_course
):
    _post_details(client, free_course)

    assert AnonymousApplicant.objects.count() == 0


@pytest.mark.django_db
def test_anonymous_details_step_on_a_gated_course_renders(client, gated_course):
    response = client.get(_details_url(gated_course))

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Anonymous apply on a course with a form
# ---------------------------------------------------------------------------


def _anonymous_form_applicant(client):
    """Post the details step on a form course and return the course, form and
    the user-less application it started."""
    course, form = gated_course_with_form()
    _post_details(client, course)
    return course, form, CourseApplication.objects.get(course=course)


@pytest.mark.django_db
def test_details_post_on_a_form_course_creates_a_user_less_sitting(
    mock_site_context, client
):
    _course, _form, application = _anonymous_form_applicant(client)

    assert application.user is None
    assert application.form_progress.user is None


@pytest.mark.django_db
def test_details_post_on_a_form_course_redirects_to_page_one(mock_site_context, client):
    course, _form = gated_course_with_form()

    response = _post_details(client, course)

    application = CourseApplication.objects.get(course=course)
    assert response["Location"] == _page_url(application, 1)


@pytest.mark.django_db
def test_details_post_on_a_form_course_allows_the_session_to_use_the_sitting(
    mock_site_context, client
):
    _course, _form, application = _anonymous_form_applicant(client)

    allowed = client.session[ANONYMOUS_FORM_PROGRESS_SESSION_KEY]

    assert allowed == [str(application.form_progress.pk)]


@pytest.mark.django_db
def test_page_one_previous_link_goes_back_to_the_details_step(
    mock_site_context, client
):
    course, _form, application = _anonymous_form_applicant(client)

    body = client.get(_page_url(application, 1)).content.decode()

    assert f'href="{_details_url(course)}"' in body


@pytest.mark.django_db
def test_page_two_previous_link_goes_to_page_one(mock_site_context, client):
    _course, _form, application = _anonymous_form_applicant(client)

    body = client.get(_page_url(application, 2)).content.decode()

    assert f'href="{_page_url(application, 1)}"' in body


def _submit_anonymous_application(client, form, application):
    name = _questions_on(form, 1)[0]
    client.post(_page_url(application, 1), {f"question_{name.id}": "Ada"})
    client.post(_page_url(application, 2), {})
    return client.post(_check_url(application))


def _attach_file(client, form, application):
    file_question = _questions_on(form, 2)[0]
    client.post(
        reverse(
            "form_engine:question_file_upload",
            kwargs={
                "progress_pk": application.form_progress.pk,
                "question_pk": file_question.pk,
            },
        ),
        {"file": SimpleUploadedFile("id-scan.png", png_bytes())},
    )
    return application.form_progress.answers.get(question=file_question).answer_file


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("route", "extra"),
    [("form_page", {"page_number": 1}), ("check_answers", {})],
)
def test_a_submitted_anonymous_application_hides_its_answers_from_the_session(
    mock_site_context, client, route, extra
):
    _course, form, application = _anonymous_form_applicant(client)
    _submit_anonymous_application(client, form, application)

    response = client.get(
        reverse(f"course_applications:{route}", kwargs={"pk": application.pk, **extra})
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_submitted_anonymous_application_hides_its_files_from_the_session(
    mock_site_context, client
):
    _course, form, application = _anonymous_form_applicant(client)
    answer_file = _attach_file(client, form, application)
    _submit_anonymous_application(client, form, application)

    response = client.get(
        reverse(
            "form_engine:own_question_answer_file", kwargs={"file_pk": answer_file.pk}
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_submitted_anonymous_application_still_shows_its_status_to_the_session(
    mock_site_context, client
):
    _course, form, application = _anonymous_form_applicant(client)
    _submit_anonymous_application(client, form, application)

    response = client.get(
        reverse("course_applications:status", kwargs={"pk": application.pk})
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_a_course_that_gains_a_form_after_the_details_step_sends_the_visitor_into_it(
    mock_site_context, client
):
    course = CourseFactory(access_config={"access_type": "application_gated"})
    _post_details(client, course)
    _with_form, form = gated_course_with_form()
    course.application_form = form
    course.save(update_fields=["application_form"])

    response = client.post(_apply_url(course))

    application = CourseApplication.objects.get(course=course)
    assert response["Location"] == _page_url(application, 1)


@pytest.mark.django_db
def test_a_course_that_gains_a_form_after_the_details_step_emails_the_claim_link(
    mock_site_context, client
):
    course = CourseFactory(access_config={"access_type": "application_gated"})
    _post_details(client, course)
    _with_form, form = gated_course_with_form()
    course.application_form = form
    course.save(update_fields=["application_form"])

    client.post(_apply_url(course))

    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_a_sitting_started_from_the_apply_step_is_allowed_to_the_session(
    mock_site_context, client
):
    course = CourseFactory(access_config={"access_type": "application_gated"})
    _post_details(client, course)
    _with_form, form = gated_course_with_form()
    course.application_form = form
    course.save(update_fields=["application_form"])
    client.post(_apply_url(course))
    application = CourseApplication.objects.get(course=course)

    response = client.get(_page_url(application, 1))

    assert response.status_code == 200


@pytest.mark.django_db
def test_submitting_an_anonymous_application_stamps_the_sitting(
    mock_site_context, client
):
    _course, form, application = _anonymous_form_applicant(client)

    _submit_anonymous_application(client, form, application)

    application.form_progress.refresh_from_db()
    assert application.form_progress.completed_time is not None


@pytest.mark.django_db
def test_submitting_an_anonymous_application_redirects_to_the_status_page(
    mock_site_context, client
):
    _course, form, application = _anonymous_form_applicant(client)

    response = _submit_anonymous_application(client, form, application)

    assert response["Location"] == reverse(
        "course_applications:status", kwargs={"pk": application.pk}
    )


@pytest.mark.django_db
def test_submitting_an_anonymous_application_creates_no_course_attempt(
    mock_site_context, client
):
    _course, form, application = _anonymous_form_applicant(client)

    _submit_anonymous_application(client, form, application)

    assert CourseFormAttempt.objects.count() == 0


@pytest.mark.django_db
def test_submitting_an_anonymous_application_changes_no_course_progress(
    mock_site_context, client
):
    _course, form, application = _anonymous_form_applicant(client)
    before = CourseProgress.objects.count()

    _submit_anonymous_application(client, form, application)

    assert CourseProgress.objects.count() == before


@pytest.mark.django_db
@pytest.mark.parametrize("target", ["page", "check", "status"])
def test_a_fresh_client_is_sent_to_log_in_on_an_anonymous_applications_urls(
    mock_site_context, client, target
):
    _course, _form, application = _anonymous_form_applicant(client)
    urls = {
        "page": _page_url(application, 1),
        "check": _check_url(application),
        "status": reverse("course_applications:status", kwargs={"pk": application.pk}),
    }

    response = Client().get(urls[target])

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('account_login')}?next={urls[target]}"


@pytest.mark.django_db
def test_a_second_details_post_resumes_without_a_second_application(
    mock_site_context, client
):
    course, _form, application = _anonymous_form_applicant(client)

    response = _post_details(client, course)

    assert response["Location"] == _page_url(application, 1)
    assert CourseApplication.objects.filter(course=course).count() == 1


@pytest.mark.django_db(transaction=True)
def test_overlapping_starts_of_one_application_make_one_sitting(mock_site_context):
    """Two requests start the same application at once: the second waits on
    the first's row lock, then finds the sitting the first made. Without the
    lock each makes a sitting and the loser's is reachable by nothing.

    transaction=True, because a second connection has to see the first's
    commit, and each thread opens its own connection."""
    site = mock_site_context
    course, _form = gated_course_with_form()
    application = CourseApplicationFactory(
        anonymous=True,
        course=course,
        state=CourseApplication.State.DRAFT,
        submitted_at=None,
    )
    applicant = application.anonymous_applicant
    first_holds_the_lock = threading.Event()
    original_create = FormProgress.objects.create
    failures: list[BaseException] = []

    def slow_create(**kwargs):
        first_holds_the_lock.set()
        time.sleep(0.5)
        return original_create(**kwargs)

    def start() -> None:
        try:
            with site_context(site):
                _start_application(course, anonymous_applicant=applicant)
        except BaseException as exc:
            failures.append(exc)
        finally:
            connection.close()

    with patch.object(FormProgress.objects, "create", side_effect=slow_create):
        first = threading.Thread(target=start)
        first.start()
        assert first_holds_the_lock.wait(timeout=5)
        second = threading.Thread(target=start)
        second.start()
        first.join(timeout=10)
        second.join(timeout=10)

    assert failures == []
    assert FormProgress.objects.count() == 1


# ---------------------------------------------------------------------------
# The claim page
# ---------------------------------------------------------------------------


def _claim_url(applicant) -> str:
    return reverse(
        "course_applications:claim", kwargs={"token": claim_token(applicant)}
    )


def _stamp_consent(applicant) -> None:
    applicant.terms_version = "1.2"
    applicant.terms_git_hash = "a" * 40
    applicant.privacy_version = "2.0"
    applicant.privacy_git_hash = "b" * 40
    applicant.consent_ip_address = "203.0.113.9"
    applicant.save()


def _submitted_form_less_application(*, consent: bool = True):
    application = CourseApplicationFactory(anonymous=True)
    if consent:
        _stamp_consent(application.anonymous_applicant)
    return application


def _submitted_form_application():
    course, form = gated_course_with_form()
    application = CourseApplicationFactory(anonymous=True, course=course)
    application.form_progress = FormProgressFactory(
        user=None, form=form, completed_time=timezone.now()
    )
    application.save(update_fields=["form_progress"])
    return application


def _claim(client, application):
    return client.post(_claim_url(application.anonymous_applicant))


@pytest.fixture
def claimable(mock_site_context):
    return _submitted_form_less_application()


@pytest.mark.django_db
def test_claim_get_renders_the_confirm_page(client, claimable):
    response = client.get(_claim_url(claimable.anonymous_applicant))

    assert response.context["claim_state"] == "confirm"


@pytest.mark.django_db
def test_claim_get_names_the_address_being_verified(client, claimable):
    response = client.get(_claim_url(claimable.anonymous_applicant))

    assert claimable.anonymous_applicant.email in response.content.decode()


@pytest.mark.django_db
def test_claim_get_for_a_new_address_says_a_password_comes_next(client, claimable):
    response = client.get(_claim_url(claimable.anonymous_applicant))

    assert "choose a password for your new account" in response.content.decode()


@pytest.mark.django_db
def test_claim_get_for_an_existing_account_says_it_signs_in(
    client, claimable_for_existing_user
):
    application, _ = claimable_for_existing_user

    response = client.get(_claim_url(application.anonymous_applicant))

    body = response.content.decode()
    assert ("signed in to your account" in body, "choose a password" in body) == (
        True,
        False,
    )


@pytest.mark.django_db
def test_claim_get_is_never_cached(client, claimable):
    response = client.get(_claim_url(claimable.anonymous_applicant))

    assert response["Cache-Control"] == "no-store"


@pytest.mark.django_db
@override_settings(POSTHOG_API_KEY="phc_test")  # pragma: allowlist secret
def test_claim_get_loads_no_analytics_snippet(client, claimable):
    response = client.get(_claim_url(claimable.anonymous_applicant))

    assert "posthog.init(" not in response.content.decode()


@pytest.mark.django_db
def test_claim_get_while_signed_in_as_somebody_else_says_so(client, claimable):
    bystander = UserFactory(email="bob@example.com")
    client.force_login(bystander)

    response = client.get(_claim_url(claimable.anonymous_applicant))

    assert "signed in as bob@example.com" in response.content.decode()


@pytest.mark.django_db
def test_claim_get_while_signed_in_as_the_owner_says_nothing_about_signing_out(
    client, claimable_for_existing_user
):
    application, user = claimable_for_existing_user
    client.force_login(user)

    response = client.get(_claim_url(application.anonymous_applicant))

    assert "sign you out" not in response.content.decode()


@pytest.mark.django_db
def test_claim_post_while_signed_in_as_somebody_else_signs_the_claimant_in(
    client, claimable
):
    bystander = UserFactory(email="bob@example.com")
    client.force_login(bystander)

    _claim(client, claimable)

    claimant = User.objects.get(email=claimable.anonymous_applicant.email)
    assert client.session["_auth_user_id"] == str(claimant.pk)


@pytest.mark.django_db
def test_claim_get_creates_no_user(client, claimable):
    users_before = User._base_manager.count()

    client.get(_claim_url(claimable.anonymous_applicant))

    assert User._base_manager.count() == users_before


@pytest.mark.django_db
def test_claim_get_leaves_claimed_at_empty(client, claimable):
    client.get(_claim_url(claimable.anonymous_applicant))

    claimable.anonymous_applicant.refresh_from_db()
    assert claimable.anonymous_applicant.claimed_at is None


@pytest.mark.django_db
def test_claim_post_creates_a_user_with_an_unusable_password(client, claimable):
    _claim(client, claimable)

    user = User.objects.get(email=claimable.anonymous_applicant.email)
    assert user.has_usable_password() is False


@pytest.mark.django_db
def test_claim_post_copies_the_names_and_site_onto_the_user(
    client, claimable, mock_site_context
):
    _claim(client, claimable)

    user = User.objects.get(email=claimable.anonymous_applicant.email)
    assert (user.first_name, user.last_name) == ("Anna", "Applicant")
    assert user.site_id == claimable.site_id


@pytest.mark.django_db
def test_claim_post_creates_one_verified_primary_email_address(client, claimable):
    _claim(client, claimable)

    addresses = EmailAddress.objects.filter(email=claimable.anonymous_applicant.email)
    assert [(a.verified, a.primary) for a in addresses] == [(True, True)]


@pytest.mark.django_db
def test_claim_post_writes_one_consent_per_accepted_document(client, claimable):
    _claim(client, claimable)

    user = User.objects.get(email=claimable.anonymous_applicant.email)
    consents = LegalConsent.objects.filter(user=user).order_by("document_type")
    assert [
        (c.document_type, c.document_version, c.git_hash, c.ip_address)
        for c in consents
    ] == [
        ("privacy", "2.0", "b" * 40, "203.0.113.9"),
        ("terms", "1.2", "a" * 40, "203.0.113.9"),
    ]


@pytest.mark.django_db
def test_claim_post_records_the_application_details_step_as_consent_method(
    client, claimable
):
    _claim(client, claimable)

    user = User.objects.get(email=claimable.anonymous_applicant.email)
    methods = set(
        LegalConsent.objects.filter(user=user).values_list("consent_method", flat=True)
    )
    assert methods == {"application_details_step"}


@pytest.mark.django_db
def test_claim_post_without_consent_evidence_writes_no_consent(
    client, mock_site_context
):
    application = _submitted_form_less_application(consent=False)

    _claim(client, application)

    assert LegalConsent.objects.count() == 0


@pytest.mark.django_db
def test_claim_post_attaches_the_user_to_the_application(client, claimable):
    _claim(client, claimable)

    claimable.refresh_from_db()
    user = User.objects.get(email=claimable.anonymous_applicant.email)
    assert claimable.user == user


@pytest.mark.django_db
def test_claim_post_attaches_the_user_to_the_sitting(client, mock_site_context):
    application = _submitted_form_application()

    _claim(client, application)

    application.form_progress.refresh_from_db()
    user = User.objects.get(email=application.anonymous_applicant.email)
    assert application.form_progress.user == user


@pytest.mark.django_db
def test_claim_post_attaches_the_user_to_the_applicant(client, claimable):
    _claim(client, claimable)

    applicant = AnonymousApplicant.objects.get(pk=claimable.anonymous_applicant.pk)
    assert applicant.user == User.objects.get(email=applicant.email)


@pytest.mark.django_db
def test_claim_post_stamps_claimed_at(client, claimable):
    _claim(client, claimable)

    applicant = AnonymousApplicant.objects.get(pk=claimable.anonymous_applicant.pk)
    assert applicant.claimed_at is not None


@pytest.mark.django_db
def test_claim_post_redirects_to_set_password_with_the_status_page_as_next(
    client, claimable
):
    response = _claim(client, claimable)

    status_url = reverse("course_applications:status", kwargs={"pk": claimable.pk})
    assert response["Location"] == (
        f"{reverse('account_set_password')}?{urlencode({'next': status_url})}"
    )


@pytest.mark.django_db
def test_claim_post_changes_the_session_key(client, claimable):
    client.get(_claim_url(claimable.anonymous_applicant))
    session = client.session
    session["warmup"] = "1"
    session.save()
    key_before = client.session.session_key

    _claim(client, claimable)

    assert client.session.session_key != key_before


@pytest.mark.django_db
def test_claim_post_removes_the_applicant_from_the_session_map(
    client, mock_site_context
):
    course = CourseFactory(access_config={"access_type": "application_gated"})
    _post_details(client, course)
    client.post(_apply_url(course))
    application = CourseApplication.objects.get(course=course)

    _claim(client, application)

    assert client.session.get(ANONYMOUS_APPLICANTS_SESSION_KEY) == {}


@pytest.mark.django_db
def test_claim_post_fires_the_user_signed_up_webhook_once(client, claimable):
    with patch("freedom_ls.webhooks.events.fire_webhook_event") as fire:
        _claim(client, claimable)

    assert fire.call_count == 1
    assert fire.call_args.args[0] == "user.signed_up"


@pytest.mark.django_db
def test_claim_post_queues_one_sign_up_analytics_event(client, claimable):
    _claim(client, claimable)

    events = client.session["google_analytics_events"]
    assert [event["name"] for event in events] == ["sign_up"]


@pytest.mark.django_db
def test_claim_post_while_signed_in_as_somebody_else_keeps_the_sign_up_event(
    client, claimable
):
    """Signing the bystander out empties their session; the event must land in
    the session the claimant keeps."""
    client.force_login(UserFactory(email="bob@example.com"))

    _claim(client, claimable)

    events = client.session["google_analytics_events"]
    assert [event["name"] for event in events] == ["sign_up"]


@pytest.mark.django_db
def test_claim_post_while_signed_in_as_somebody_else_on_a_used_link_leaves_them_in(
    client, claimable
):
    """A spent link never reaches the confirm page, so nothing promised a sign-out."""
    _claim(Client(), claimable)
    bystander = UserFactory(email="bob@example.com")
    client.force_login(bystander)

    response = _claim(client, claimable)

    assert (response.context["claim_state"], client.session["_auth_user_id"]) == (
        "invalid",
        str(bystander.pk),
    )


@pytest.mark.django_db
def test_claim_post_writes_one_signup_attribution(client, claimable):
    _claim(client, claimable)

    user = User.objects.get(email=claimable.anonymous_applicant.email)
    # Reverse accessor of the one-to-one: course_applications does not depend on
    # referral_tracking, so the model is reached through the user.
    assert user.signup_attribution is not None


@pytest.mark.django_db
def test_claim_of_a_form_less_application_succeeds(client, claimable):
    response = _claim(client, claimable)

    assert response.status_code == 302


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("route", "extra"),
    [("status", {}), ("form_page", {"page_number": 1}), ("check_answers", {})],
)
def test_pre_claim_anonymous_client_is_sent_to_log_in_after_the_claim(
    client, mock_site_context, route, extra
):
    """Once claimed, the application belongs to an account; the browser that
    applied is asked to sign in to it."""
    application = _submitted_form_application()
    session = client.session
    session[ANONYMOUS_APPLICANTS_SESSION_KEY] = {
        str(application.course_id): str(application.anonymous_applicant.pk)
    }
    session.save()
    _claim(Client(), application)

    url = reverse(
        f"course_applications:{route}", kwargs={"pk": application.pk, **extra}
    )
    response = client.get(url)

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('account_login')}?next={url}"


@pytest.mark.django_db
def test_signed_in_claimant_reaches_the_status_page(client, claimable):
    _claim(client, claimable)

    response = client.get(
        reverse("course_applications:status", kwargs={"pk": claimable.pk})
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_second_claim_post_renders_the_invalid_page(client, claimable):
    _claim(client, claimable)

    response = _claim(Client(), claimable)

    assert response.context["claim_state"] == "invalid"


@pytest.mark.django_db
def test_claim_get_after_a_claim_renders_the_invalid_page(client, claimable):
    _claim(client, claimable)

    response = Client().get(_claim_url(claimable.anonymous_applicant))

    assert response.context["claim_state"] == "invalid"


@pytest.mark.django_db
def test_invalid_claim_page_shows_a_centred_icon_with_the_explanation_under_it(
    client, claimable
):
    """The used-link page used to be a bare heading and button, with no icon or text."""
    _claim(client, claimable)

    response = Client().get(_claim_url(claimable.anonymous_applicant))

    content = response.content.decode()
    assert 'data-icon="locked"' in content
    assert "size-12" in content
    assert "text-center" in content
    assert "This link is invalid or has already been used" in content
    assert "Browse courses" in content
    assert 'data-testid="claim-invalid-explanation"' in content


def _draft_application():
    """A form application whose sitting has not been completed yet."""
    application = _submitted_form_application()
    _stamp_consent(application.anonymous_applicant)
    application.form_progress.completed_time = None
    application.form_progress.save(update_fields=["completed_time"])
    application.state = CourseApplication.State.DRAFT
    application.submitted_at = None
    application.save(update_fields=["state", "submitted_at"])
    return application


@pytest.fixture
def claimable_draft(mock_site_context):
    return _draft_application()


@pytest.mark.django_db
def test_claim_of_a_draft_application_renders_the_confirm_page(client, claimable_draft):
    response = client.get(_claim_url(claimable_draft.anonymous_applicant))

    assert (response.context["claim_state"], response.context["is_submitted"]) == (
        "confirm",
        False,
    )


@pytest.mark.django_db
def test_claim_get_of_a_rejected_application_does_not_say_to_finish_it(
    client: Client, claimable: CourseApplication
) -> None:
    """The confirm page heading used to tell the person to finish an
    application that had already been decided."""
    CourseApplication.objects.filter(pk=claimable.pk).update(
        state=CourseApplication.State.REJECTED,
        submitted_at=timezone.now(),
        decided_at=timezone.now(),
        rejection_message="Not this time.",
    )

    body = client.get(_claim_url(claimable.anonymous_applicant)).content.decode()

    assert ("Finish your application" in body, "Confirm" in body) == (False, True)


@pytest.mark.django_db
def test_claim_get_of_a_draft_says_the_application_continues(client, claimable_draft):
    response = client.get(_claim_url(claimable_draft.anonymous_applicant))

    body = response.content.decode()
    assert (
        "Continue your application for" in body,
        "taken back to your application" in body,
        "Finish your application for" in body,
    ) == (True, True, False)


@pytest.mark.django_db
def test_claim_get_of_a_draft_lists_the_password_step_before_returning_to_the_application(
    client, claimable_draft
):
    response = client.get(_claim_url(claimable_draft.anonymous_applicant))

    body = " ".join(response.content.decode().split())
    assert (
        "You'll then choose a password for your new account and be taken back to your application."
        in body
    )


@pytest.mark.django_db
def test_claim_get_of_a_draft_over_a_held_submission_does_not_promise_the_application(
    client, claimable_draft
):
    _account_holding(claimable_draft, draft=False)

    response = client.get(_claim_url(claimable_draft.anonymous_applicant))

    assert "taken back to your application" not in response.content.decode()


@pytest.mark.django_db
def test_claim_post_of_a_draft_creates_the_user(client, claimable_draft):
    _claim(client, claimable_draft)

    assert User.objects.filter(email=claimable_draft.anonymous_applicant.email).exists()


@pytest.mark.django_db
def test_claim_post_of_a_draft_writes_the_consent(client, claimable_draft):
    _claim(client, claimable_draft)

    user = User.objects.get(email=claimable_draft.anonymous_applicant.email)
    assert LegalConsent.objects.filter(user=user).count() == 2


@pytest.mark.django_db
def test_claim_post_of_a_draft_fires_the_user_signed_up_webhook_once(
    client, claimable_draft
):
    with patch("freedom_ls.webhooks.events.fire_webhook_event") as fire:
        _claim(client, claimable_draft)

    assert (fire.call_count, fire.call_args.args[0]) == (1, "user.signed_up")


@pytest.mark.django_db
def test_claim_post_of_a_draft_changes_the_session_key(client, claimable_draft):
    client.get(_claim_url(claimable_draft.anonymous_applicant))
    session = client.session
    session["warmup"] = "1"
    session.save()
    key_before = client.session.session_key

    _claim(client, claimable_draft)

    assert client.session.session_key != key_before


@pytest.mark.django_db
def test_claim_post_of_a_draft_attaches_the_user_to_the_application_and_sitting(
    client, claimable_draft
):
    _claim(client, claimable_draft)

    claimable_draft.refresh_from_db()
    claimable_draft.form_progress.refresh_from_db()
    user = User.objects.get(email=claimable_draft.anonymous_applicant.email)
    assert (claimable_draft.user, claimable_draft.form_progress.user) == (user, user)


@pytest.mark.django_db
def test_claim_post_of_a_draft_redirects_to_set_password_with_the_status_page_as_next(
    client, claimable_draft
):
    response = _claim(client, claimable_draft)

    status_url = reverse(
        "course_applications:status", kwargs={"pk": claimable_draft.pk}
    )
    assert response["Location"] == (
        f"{reverse('account_set_password')}?{urlencode({'next': status_url})}"
    )


@pytest.mark.django_db
def test_status_page_after_a_draft_claim_continues_on_the_first_form_page(
    client: Client, claimable_draft: CourseApplication
) -> None:
    _claim(client, claimable_draft)

    response = client.get(
        reverse("course_applications:status", kwargs={"pk": claimable_draft.pk})
    )

    first_page = reverse(
        "course_applications:form_page",
        kwargs={"pk": claimable_draft.pk, "page_number": 1},
    )
    assert f'href="{first_page}"' in response.content.decode()


@pytest.mark.django_db
def test_claim_post_of_a_draft_drops_the_applicant_from_the_claiming_session(
    client, claimable_draft
):
    session = client.session
    session[ANONYMOUS_APPLICANTS_SESSION_KEY] = {
        str(claimable_draft.course_id): str(claimable_draft.anonymous_applicant.pk)
    }
    session.save()

    _claim(client, claimable_draft)

    request = RequestFactory().get("/")
    request.session = client.session
    assert anonymous_applicant_for_course(request, claimable_draft.course) is None


@pytest.mark.django_db
def test_claim_post_of_a_draft_for_an_existing_account_lands_on_the_status_page(
    client: Client, mock_site_context: Site
) -> None:
    user = UserFactory(email="ada@example.com")
    EmailAddressFactory(user=user)
    application = _draft_application()
    applicant = application.anonymous_applicant
    applicant.email = "ada@example.com"
    applicant.save(update_fields=["email"])
    status_url = reverse("course_applications:status", kwargs={"pk": application.pk})

    response = _claim(client, application)
    followed = client.get(response["Location"])

    first_page = reverse(
        "course_applications:form_page",
        kwargs={"pk": application.pk, "page_number": 1},
    )
    assert (
        response["Location"],
        client.session["_auth_user_id"],
        f'href="{first_page}"' in followed.content.decode(),
    ) == (status_url, str(user.pk), True)


@pytest.mark.django_db
def test_claim_with_an_expired_token_of_a_draft_uses_the_draft_wording(
    client, claimable_draft
):
    url = _claim_url(claimable_draft.anonymous_applicant)
    days = allauth_account_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS

    with time_machine.travel(timezone.now() + timedelta(days=days, hours=1)):
        response = client.get(url)

    assert "Links to continue an application stop working" in response.content.decode()


@pytest.mark.django_db
def test_claim_with_an_expired_token_renders_the_expired_page(client, claimable):
    url = _claim_url(claimable.anonymous_applicant)
    days = allauth_account_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS

    with time_machine.travel(timezone.now() + timedelta(days=days, hours=1)):
        response = client.get(url)

    assert response.context["claim_state"] == "expired"


@pytest.mark.django_db
def test_unclaimed_applicant_leaves_no_user_or_side_effects(client, mock_site_context):
    course = CourseFactory(access_config={"access_type": "application_gated"})
    with patch("freedom_ls.webhooks.events.fire_webhook_event") as fire:
        _post_details(client, course)
        client.post(_apply_url(course))

    assert (
        User._base_manager.count(),
        LegalConsent.objects.count(),
        fire.call_count,
        "google_analytics_events" in client.session
        and any(
            e["name"] == "sign_up" for e in client.session["google_analytics_events"]
        ),
    ) == (0, 0, 0, False)


# ---------------------------------------------------------------------------
# Claiming with an existing account
# ---------------------------------------------------------------------------


@pytest.fixture
def claimable_for_existing_user(mock_site_context):
    """A submitted application whose address belongs to a same-site account."""
    user = UserFactory(email="ada@example.com", first_name="Original")
    EmailAddressFactory(user=user)
    application = _submitted_form_less_application()
    applicant = application.anonymous_applicant
    applicant.email = "ADA@example.com"
    applicant.first_name = "Different"
    applicant.save(update_fields=["email", "first_name"])
    return application, user


@pytest.mark.django_db
def test_claim_post_for_an_existing_account_attaches_the_application(
    client, claimable_for_existing_user
):
    application, user = claimable_for_existing_user

    _claim(client, application)

    application.refresh_from_db()
    assert application.user == user


@pytest.mark.django_db
def test_claim_post_for_an_existing_account_attaches_the_applicant(
    client, claimable_for_existing_user
):
    application, user = claimable_for_existing_user

    _claim(client, application)

    applicant = AnonymousApplicant.objects.get(pk=application.anonymous_applicant.pk)
    assert (applicant.user, applicant.claimed_at is not None) == (user, True)


@pytest.mark.django_db
def test_claim_post_for_an_existing_account_attaches_the_sitting(
    client, mock_site_context
):
    user = UserFactory(email="ada@example.com")
    application = _submitted_form_application()
    applicant = application.anonymous_applicant
    applicant.email = "Ada@Example.com"
    applicant.save(update_fields=["email"])

    _claim(client, application)

    application.form_progress.refresh_from_db()
    assert application.form_progress.user == user


@pytest.mark.django_db
def test_claim_post_for_an_existing_account_adds_no_second_address_row(
    client, claimable_for_existing_user
):
    application, user = claimable_for_existing_user

    _claim(client, application)

    assert EmailAddress.objects.filter(user=user).count() == 1


@pytest.fixture
def claimable_for_passwordless_user(mock_site_context):
    """A submitted application whose address belongs to a verified account that
    never finished choosing a password."""
    user = UserFactory(email="ada@example.com")
    user.set_unusable_password()
    user.save(update_fields=["password"])
    EmailAddressFactory(user=user)
    application = _submitted_form_less_application()
    applicant = application.anonymous_applicant
    applicant.email = "ada@example.com"
    applicant.save(update_fields=["email"])
    return application


def _account_holding(application, *, draft: bool):
    """The account of the application's address, holding its own application
    for the same course: an unfinished one, or a submitted one."""
    user = UserFactory(email=application.anonymous_applicant.email)
    EmailAddressFactory(user=user)
    CourseApplicationFactory(
        user=user,
        course=application.course,
        form_progress=(
            FormProgressFactory(user=user, completed_time=None) if draft else None
        ),
    )


@pytest.mark.django_db
def test_claim_get_of_a_draft_over_a_held_submission_says_the_draft_is_discarded(
    client, claimable_draft
):
    _account_holding(claimable_draft, draft=False)

    response = client.get(_claim_url(claimable_draft.anonymous_applicant))

    assert (
        response.context["held_application"],
        "This unfinished application will be discarded." in response.content.decode(),
    ) == ("submitted", True)


@pytest.mark.django_db
def test_claim_get_of_a_submission_over_a_held_submission_says_it_is_discarded(
    client, claimable
):
    _account_holding(claimable, draft=False)

    response = client.get(_claim_url(claimable.anonymous_applicant))

    body = response.content.decode()
    assert (
        response.context["held_application"],
        "This application will be discarded." in body,
        "unfinished application will be discarded" in body,
    ) == ("submitted", True, False)


@pytest.mark.django_db
def test_claim_get_over_a_held_draft_says_it_is_replaced(client, claimable_draft):
    _account_holding(claimable_draft, draft=True)

    response = client.get(_claim_url(claimable_draft.anonymous_applicant))

    assert (
        response.context["held_application"],
        "replaces the unfinished application" in response.content.decode(),
    ) == ("draft", True)


@pytest.mark.django_db
def test_claim_get_with_nothing_held_says_nothing_is_discarded(client, claimable_draft):
    response = client.get(_claim_url(claimable_draft.anonymous_applicant))

    body = response.content.decode()
    assert (
        response.context["held_application"],
        "will be discarded" in body,
        "replaces the unfinished application" in body,
    ) == ("", False, False)


@pytest.mark.django_db
@pytest.mark.parametrize("closed", [{"rejected": True}, {"withdrawn": True}])
def test_claim_get_over_only_a_held_closed_application_holds_nothing(
    client: Client, claimable_draft: CourseApplication, closed: dict[str, bool]
) -> None:
    assert claimable_draft.anonymous_applicant is not None
    user = UserFactory(email=claimable_draft.anonymous_applicant.email)
    EmailAddressFactory(user=user)
    CourseApplicationFactory(user=user, course=claimable_draft.course, **closed)

    response = client.get(_claim_url(claimable_draft.anonymous_applicant))

    assert response.context["held_application"] == ""


@pytest.mark.django_db
def test_claim_post_of_a_rejected_application_leaves_the_account_holding_both(
    client: Client, mock_site_context: Site
) -> None:
    incoming = CourseApplicationFactory(anonymous=True, rejected=True)
    _stamp_consent(incoming.anonymous_applicant)
    user = UserFactory(email=incoming.anonymous_applicant.email)
    EmailAddressFactory(user=user)
    held = CourseApplicationFactory(user=user, course=incoming.course)

    response = _claim(client, incoming)

    incoming.refresh_from_db()
    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(user.pk)
    assert set(CourseApplication.objects.filter(user=user)) == {held, incoming}


@pytest.mark.django_db
@pytest.mark.parametrize("draft", [True, False])
def test_claim_get_of_a_rejected_application_says_nothing_is_replaced_or_discarded(
    client: Client, mock_site_context: Site, draft: bool
) -> None:
    incoming = CourseApplicationFactory(anonymous=True, rejected=True)
    _account_holding(incoming, draft=draft)

    response = client.get(_claim_url(incoming.anonymous_applicant))

    body = response.content.decode()
    assert (
        response.context["held_application"],
        "will be discarded" in body,
        "replaces the unfinished application" in body,
    ) == ("", False, False)


@pytest.mark.django_db
def test_claim_get_for_a_passwordless_account_says_a_password_comes_next(
    client: Client, claimable_for_passwordless_user: CourseApplication
) -> None:
    response = client.get(
        _claim_url(claimable_for_passwordless_user.anonymous_applicant)
    )

    assert "choose a password" in response.content.decode()


@pytest.mark.django_db
def test_claim_post_for_a_passwordless_account_redirects_to_set_password(
    client, claimable_for_passwordless_user
):
    response = _claim(client, claimable_for_passwordless_user)

    assert response["Location"].startswith(reverse("account_set_password"))


@pytest.mark.django_db
def test_claim_post_for_an_existing_account_writes_no_consent(
    client, claimable_for_existing_user
):
    application, _ = claimable_for_existing_user

    _claim(client, application)

    assert LegalConsent.objects.count() == 0


@pytest.mark.django_db
def test_claim_post_for_an_existing_account_leaves_the_profile_untouched(
    client, claimable_for_existing_user
):
    application, user = claimable_for_existing_user
    password_before = user.password

    _claim(client, application)

    user.refresh_from_db()
    assert (user.first_name, user.password) == ("Original", password_before)


@pytest.mark.django_db
def test_claim_post_for_an_existing_account_changes_the_session_key(
    client, claimable_for_existing_user
):
    application, _ = claimable_for_existing_user
    client.get(_claim_url(application.anonymous_applicant))
    session = client.session
    session["warmup"] = "1"
    session.save()
    key_before = client.session.session_key

    _claim(client, application)

    assert client.session.session_key != key_before


@pytest.mark.django_db
def test_claim_post_for_an_existing_account_signs_the_account_in(
    client, claimable_for_existing_user
):
    application, user = claimable_for_existing_user

    _claim(client, application)

    assert client.session["_auth_user_id"] == str(user.pk)


@pytest.mark.django_db
def test_claim_post_for_an_existing_account_redirects_to_the_status_page(
    client, claimable_for_existing_user
):
    application, _ = claimable_for_existing_user

    response = _claim(client, application)

    assert response.url == reverse(
        "course_applications:status", kwargs={"pk": application.pk}
    )


@pytest.mark.django_db
def test_claim_post_for_an_existing_account_fires_no_webhook(
    client, claimable_for_existing_user
):
    application, _ = claimable_for_existing_user

    with patch("freedom_ls.webhooks.events.fire_webhook_event") as fire:
        _claim(client, application)

    assert fire.call_count == 0


@pytest.mark.django_db
def test_claim_post_for_an_existing_account_queues_no_sign_up_event(
    client, claimable_for_existing_user
):
    application, _ = claimable_for_existing_user

    _claim(client, application)

    assert "google_analytics_events" not in client.session


@pytest.mark.django_db
def test_claim_post_for_an_existing_account_writes_no_attribution(
    client, claimable_for_existing_user
):
    application, user = claimable_for_existing_user

    _claim(client, application)

    # Reverse accessor of the one-to-one: course_applications does not depend on
    # referral_tracking, so the model is reached through the user.
    assert hasattr(user, "signup_attribution") is False


@pytest.mark.django_db
def test_claim_post_over_an_earlier_submission_lands_on_that_one(
    client, claimable_for_existing_user
):
    """An account holds one application per course: the one it already
    submitted stays, the claimed one goes, and the claimant is shown the one
    that stays."""
    application, user = claimable_for_existing_user
    earlier = CourseApplicationFactory(user=user, course=application.course)

    response = _claim(client, application)

    assert response["Location"] == reverse(
        "course_applications:status", kwargs={"pk": earlier.pk}
    )
    assert list(
        CourseApplication.objects.filter(course=application.course).values_list(
            "pk", flat=True
        )
    ) == [earlier.pk]


@pytest.mark.django_db
def test_claim_post_for_an_inactive_account_attaches_without_signing_in(
    client, mock_site_context
):
    user = UserFactory(email="ada@example.com", is_active=False)
    application = _submitted_form_less_application()
    applicant = application.anonymous_applicant
    applicant.email = "ada@example.com"
    applicant.save(update_fields=["email"])

    _claim(client, application)

    application.refresh_from_db()
    assert (application.user, "_auth_user_id" in client.session) == (user, False)


@pytest.mark.django_db
def test_claim_post_for_an_inactive_account_signs_a_bystander_out(
    client, mock_site_context
):
    UserFactory(email="ada@example.com", is_active=False)
    application = _submitted_form_less_application()
    applicant = application.anonymous_applicant
    applicant.email = "ada@example.com"
    applicant.save(update_fields=["email"])
    client.force_login(UserFactory(email="bob@example.com"))

    response = _claim(client, application)

    assert (response.url, "_auth_user_id" in client.session) == (
        reverse("account_login"),
        False,
    )


@pytest.mark.django_db
def test_claim_post_for_an_inactive_account_redirects_to_login(
    client, mock_site_context
):
    UserFactory(email="ada@example.com", is_active=False)
    application = _submitted_form_less_application()
    applicant = application.anonymous_applicant
    applicant.email = "ada@example.com"
    applicant.save(update_fields=["email"])

    response = _claim(client, application)

    assert response.url == reverse("account_login")


@pytest.fixture
def claimable_for_other_site_user(mock_site_context):
    """A submitted application whose address belongs to an account on another site."""
    UserFactory(site=SiteFactory(), email="ada@example.com")
    application = _submitted_form_less_application()
    applicant = application.anonymous_applicant
    applicant.email = "ada@example.com"
    applicant.save(update_fields=["email"])
    return application


@pytest.mark.django_db
def test_claim_post_for_an_other_site_account_renders_the_invalid_page(
    client, claimable_for_other_site_user
):
    response = _claim(client, claimable_for_other_site_user)

    assert response.context["claim_state"] == "invalid"


@pytest.mark.django_db
def test_claim_post_for_an_other_site_account_attaches_nothing(
    client, claimable_for_other_site_user
):
    _claim(client, claimable_for_other_site_user)

    claimable_for_other_site_user.refresh_from_db()
    applicant = AnonymousApplicant.objects.get(
        pk=claimable_for_other_site_user.anonymous_applicant.pk
    )
    assert (
        claimable_for_other_site_user.user,
        applicant.user,
        applicant.claimed_at,
    ) == (None, None, None)


@pytest.mark.django_db
def test_claim_post_for_an_other_site_account_creates_no_user(
    client, claimable_for_other_site_user
):
    users_before = User._base_manager.count()

    _claim(client, claimable_for_other_site_user)

    assert User._base_manager.count() == users_before


@pytest.mark.django_db
def test_claim_post_for_an_other_site_account_leaves_the_client_anonymous(
    client, claimable_for_other_site_user
):
    _claim(client, claimable_for_other_site_user)

    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("route", "extra"),
    [("status", {}), ("form_page", {"page_number": 1}), ("check_answers", {})],
)
def test_session_from_one_site_resolves_nothing_on_another_sites_host(
    client, mock_site_context, route, extra
):
    """Another host's session reaches nothing: it gets the same login redirect
    as a session that holds no application at all."""
    application = _submitted_form_application()
    session = client.session
    session[ANONYMOUS_APPLICANTS_SESSION_KEY] = {
        str(application.course_id): str(application.anonymous_applicant.pk)
    }
    session.save()
    other_site = SiteFactory()

    with site_context(other_site):
        response = client.get(
            reverse(
                f"course_applications:{route}",
                kwargs={"pk": application.pk, **extra},
            )
        )

    assert response.status_code == 302
    assert response["Location"].startswith(f"{reverse('account_login')}?next=")


# ---------------------------------------------------------------------------
# Claim email on the status and expired pages
# ---------------------------------------------------------------------------


def _expired_claim_post(client, application):
    url = _claim_url(application.anonymous_applicant)
    days = allauth_account_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS
    with time_machine.travel(timezone.now() + timedelta(days=days, hours=1)):
        return client.post(url)


@pytest.mark.django_db
def test_a_resent_claim_email_greets_nobody_by_the_signed_in_users_name(
    client, claimable
):
    bystander = UserFactory(first_name="Alice")
    client.force_login(bystander)

    _expired_claim_post(client, claimable)

    assert "Alice" not in mail.outbox[0].body


@pytest.mark.django_db
def test_status_page_of_an_unverified_application_shows_the_emailed_link_sentence(
    client, gated_course
):
    _post_details(client, gated_course)
    response = client.post(_apply_url(gated_course), follow=True)

    assert "emailed a link to ada@example.com" in _page_text(response)


def _page_text(response) -> str:
    """The page as a reader sees it: no tags, and runs of whitespace as one space."""
    return " ".join(strip_tags(response.content.decode()).split())


def _unverified_status_url(client, course) -> str:
    _post_details(client, course)
    client.post(_apply_url(course))
    application = CourseApplication.objects.get(course=course)
    return reverse("course_applications:status", kwargs={"pk": application.pk})


@pytest.mark.django_db
def test_status_page_offers_to_send_the_email_again(client, gated_course):
    url = _unverified_status_url(client, gated_course)

    notice = client.get(url).content.decode()

    assert 'data-testid="claim-link-notice"' in notice
    assert ">Send again</span>" in notice


@pytest.mark.django_db
def test_status_page_says_when_no_email_went_out(client, gated_course):
    with override_settings(ACCOUNT_RATE_LIMITS={"application_claim_email": "0/h/key"}):
        cache.clear()
        url = _unverified_status_url(client, gated_course)

    body = _page_text(client.get(url))

    assert (
        "We couldn't email ada@example.com just now" in body,
        "emailed a link" in body,
    ) == (
        True,
        False,
    )


@pytest.mark.django_db
def test_resend_post_sends_the_email_again(client, gated_course):
    url = _unverified_status_url(client, gated_course)

    client.post(url)

    assert len(mail.outbox) == 2


@pytest.mark.django_db
def test_resend_post_confirms_with_a_message(client, gated_course):
    url = _unverified_status_url(client, gated_course)

    response = client.post(url)

    assert [str(m) for m in get_messages(response.wsgi_request)] == [
        "We've emailed a link to ada@example.com."
    ]


@pytest.mark.django_db
def test_resend_post_over_the_limit_says_so(client, gated_course):
    with override_settings(ACCOUNT_RATE_LIMITS={"application_claim_email": "1/h/key"}):
        cache.clear()
        url = _unverified_status_url(client, gated_course)

        response = client.post(url)

    assert [str(m) for m in get_messages(response.wsgi_request)] == [
        "We couldn't email ada@example.com just now. Try again in a little while."
    ]


@pytest.mark.django_db
def test_resend_post_returns_to_the_status_page(client, gated_course):
    url = _unverified_status_url(client, gated_course)

    response = client.post(url)

    assert response["Location"] == url


@pytest.mark.django_db
def test_resend_post_from_another_session_sends_nothing(client, gated_course):
    url = _unverified_status_url(client, gated_course)
    sent_before = len(mail.outbox)

    response = Client().post(url)

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('account_login')}?next={url}"
    assert len(mail.outbox) == sent_before


@pytest.mark.django_db
def test_resend_post_on_a_verified_application_is_404(client, mock_site_context):
    user = UserFactory()
    application = CourseApplicationFactory(user=user)
    client.force_login(user)

    response = client.post(
        reverse("course_applications:status", kwargs={"pk": application.pk})
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_expired_token_post_sends_one_email_to_the_stored_address(client, claimable):
    mail.outbox.clear()

    _expired_claim_post(client, claimable)

    assert [message.to for message in mail.outbox] == [
        [claimable.anonymous_applicant.email]
    ]


@pytest.mark.django_db
def test_expired_token_post_after_an_address_change_sends_a_link_that_confirms(
    client, claimable
):
    applicant = claimable.anonymous_applicant
    update_applicant_email(applicant, "new@example.com")
    mail.outbox.clear()

    _expired_claim_post(client, claimable)

    emailed_link = re.search(r"https?://\S+/claim/[^\s\"<]+", mail.outbox[0].body)
    assert emailed_link is not None
    assert client.get(emailed_link.group(0)).context["claim_state"] == "confirm"


@pytest.mark.django_db
def test_expired_token_post_renders_the_resent_page(client, claimable):
    response = _expired_claim_post(client, claimable)

    assert response.context["claim_state"] == "resent"


@pytest.mark.django_db
def test_expired_token_post_over_the_limit_sends_nothing(client, claimable):
    with override_settings(ACCOUNT_RATE_LIMITS={"application_claim_email": "1/h/key"}):
        cache.clear()
        _expired_claim_post(client, claimable)
        mail.outbox.clear()
        _expired_claim_post(client, claimable)

    assert mail.outbox == []


@pytest.mark.django_db
def test_expired_token_post_over_the_limit_says_nothing_was_sent(client, claimable):
    with override_settings(ACCOUNT_RATE_LIMITS={"application_claim_email": "1/h/key"}):
        cache.clear()
        _expired_claim_post(client, claimable)
        response = _expired_claim_post(client, claimable)

    assert (response.context["claim_state"], response.context["resend_failed"]) == (
        "expired",
        True,
    )


@pytest.mark.django_db
def test_expired_token_post_over_the_limit_still_offers_the_button(client, claimable):
    with override_settings(ACCOUNT_RATE_LIMITS={"application_claim_email": "1/h/key"}):
        cache.clear()
        _expired_claim_post(client, claimable)
        response = _expired_claim_post(client, claimable)

    assert "Send a new link" in response.content.decode()


# ---------------------------------------------------------------------------
# claim link notice and resending from a draft
# ---------------------------------------------------------------------------


def _refuse_every_send(*args: object, **kwargs: object) -> None:
    raise smtplib.SMTPRecipientsRefused({})


def _anonymous_draft(client):
    """Take a fresh session through the details step of a form-bearing course."""
    course, _form = gated_course_with_form()
    _post_details(client, course)
    return CourseApplication.objects.get(course=course)


@pytest.mark.django_db
def test_form_page_of_an_unverified_draft_shows_the_notice_as_sent(
    client, mock_site_context
):
    application = _anonymous_draft(client)

    response = client.get(_page_url(application, 1))

    assert (
        'data-testid="claim-link-notice" data-sent="true"' in response.content.decode()
    )


@pytest.mark.django_db
def test_form_page_notice_shows_not_sent_when_the_send_was_refused(
    client, mock_site_context
):
    with patch.object(AccountAdapter, "send_mail", _refuse_every_send):
        application = _anonymous_draft(client)

    response = client.get(_page_url(application, 1))

    assert (
        'data-testid="claim-link-notice" data-sent="false"' in response.content.decode()
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "state",
    [CourseApplication.State.WITHDRAWN, CourseApplication.State.REJECTED],
)
def test_read_only_form_page_never_says_submitted_for_an_unsubmitted_state(
    client: Client, mock_site_context: Site, state: CourseApplication.State
) -> None:
    """The read-only notice used to say "submitted" for a withdrawn or rejected application."""
    application = _anonymous_draft(client)
    user = UserFactory()
    client.force_login(user)
    now = timezone.now()
    CourseApplication.objects.filter(pk=application.pk).update(
        user=user,
        anonymous_applicant=None,
        state=state,
        withdrawn_at=now if state == CourseApplication.State.WITHDRAWN else None,
        decided_at=now if state == CourseApplication.State.REJECTED else None,
        submitted_at=now if state == CourseApplication.State.REJECTED else None,
        rejection_message="Not a fit."
        if state == CourseApplication.State.REJECTED
        else "",
    )

    body = client.get(_page_url(application, 1)).content.decode()
    notice = lxml.html.fromstring(body).xpath(
        "string(//*[@data-testid='read-only-notice'])"
    )

    assert notice.strip()
    assert "submitted" not in notice


@pytest.mark.django_db
def test_read_only_form_page_of_an_approved_application_says_a_decision_was_made(
    client: Client, mock_site_context: Site
) -> None:
    application = _anonymous_draft(client)
    user = UserFactory()
    client.force_login(user)
    now = timezone.now()
    CourseApplication.objects.filter(pk=application.pk).update(
        user=user,
        anonymous_applicant=None,
        state=CourseApplication.State.APPROVED,
        decided_at=now,
        submitted_at=now,
    )

    body = client.get(_page_url(application, 1)).content.decode()
    notice = lxml.html.fromstring(body).xpath(
        "string(//*[@data-testid='read-only-notice'])"
    )

    assert "A decision has been made" in notice


@pytest.mark.django_db
def test_form_page_notice_names_the_applicants_address(client, mock_site_context):
    application = _anonymous_draft(client)

    body = client.get(_page_url(application, 1)).content.decode()

    assert ">ada@example.com</strong>" in body


@pytest.mark.django_db
def test_check_your_answers_of_an_unverified_draft_shows_the_notice(
    client, mock_site_context
):
    application = _anonymous_draft(client)

    body = client.get(_check_url(application)).content.decode()

    assert 'data-testid="claim-link-notice"' in body


@pytest.mark.django_db
def test_form_page_of_a_signed_in_applicant_has_no_notice(client, mock_site_context):
    course, _form = gated_course_with_form()
    application = _applied(client, course)

    body = client.get(_page_url(application, 1)).content.decode()

    assert "claim-link-notice" not in body


@pytest.mark.django_db
def test_check_your_answers_of_a_signed_in_applicant_has_no_notice(
    client, mock_site_context
):
    course, _form = gated_course_with_form()
    application = _applied(client, course)

    body = client.get(_check_url(application)).content.decode()

    assert "claim-link-notice" not in body


@pytest.mark.django_db
def test_notice_form_posts_to_the_status_url(client, mock_site_context):
    application = _anonymous_draft(client)
    status_url = reverse("course_applications:status", kwargs={"pk": application.pk})

    body = client.get(_page_url(application, 1)).content.decode()

    assert f'hx-post="{status_url}"' in body


@pytest.mark.django_db
def test_notice_change_form_posts_to_the_change_email_url(client, mock_site_context):
    application = _anonymous_draft(client)
    change_url = reverse(
        "course_applications:change_applicant_email", kwargs={"pk": application.pk}
    )

    body = client.get(_page_url(application, 1)).content.decode()

    assert f'hx-post="{change_url}"' in body


@pytest.mark.django_db
def test_notice_change_form_starts_with_the_current_address(client, mock_site_context):
    application = _anonymous_draft(client)

    body = client.get(_check_url(application)).content.decode()

    assert 'value="ada@example.com"' in body


def _htmx_change_email(client, application, *, next_url: str = "", **data: str):
    return client.post(
        reverse(
            "course_applications:change_applicant_email", kwargs={"pk": application.pk}
        ),
        {"email": "new@example.com", "next": next_url, **data},
        HTTP_HX_REQUEST="true",
    )


@pytest.mark.django_db
def test_htmx_change_on_a_draft_returns_the_notice_naming_the_new_address(
    client, mock_site_context
):
    application = _anonymous_draft(client)

    response = _htmx_change_email(client, application)

    body = response.content.decode()
    assert response.status_code == 200
    assert 'data-testid="claim-link-notice" data-sent="true"' in body
    assert ">new@example.com</strong>" in body
    assert "<html" not in body


@pytest.mark.django_db
def test_htmx_change_on_a_draft_sends_one_link_to_the_new_address(
    client, mock_site_context
):
    application = _anonymous_draft(client)
    mail.outbox.clear()

    _htmx_change_email(client, application)

    assert [message.to for message in mail.outbox] == [["new@example.com"]]


@pytest.mark.django_db
def test_htmx_change_with_an_invalid_address_is_422_with_the_form_open(
    client, mock_site_context
):
    application = _anonymous_draft(client)

    response = _htmx_change_email(client, application, email="not-an-address")

    body = response.content.decode()
    assert response.status_code == 422
    assert 'data-editing="true"' in body
    assert 'aria-invalid="true"' in body


@pytest.mark.django_db
def test_htmx_change_keeps_the_resend_on_the_page_it_came_from(
    client, mock_site_context
):
    application = _anonymous_draft(client)
    page_url = f"{_page_url(application, 1)}?return=check"

    body = _htmx_change_email(client, application, next_url=page_url).content.decode()

    assert f'<input type="hidden" name="next" value="{escape(page_url)}">' in body


@pytest.mark.django_db
def test_htmx_change_drops_a_next_url_on_another_host(client, mock_site_context):
    application = _anonymous_draft(client)

    body = _htmx_change_email(
        client, application, next_url="https://evil.example.com/"
    ).content.decode()

    assert "evil.example.com" not in body


@pytest.mark.django_db
def test_resend_post_from_a_draft_sends_one_more_email(client, mock_site_context):
    application = _anonymous_draft(client)
    mail.outbox.clear()

    client.post(reverse("course_applications:status", kwargs={"pk": application.pk}))

    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_resend_post_from_a_draft_confirms_with_a_message(client, mock_site_context):
    application = _anonymous_draft(client)

    response = client.post(
        reverse("course_applications:status", kwargs={"pk": application.pk})
    )

    assert [str(m) for m in get_messages(response.wsgi_request)] == [
        "We've emailed a link to ada@example.com."
    ]


@pytest.mark.django_db
def test_resend_post_from_a_draft_redirects_to_the_status_url(
    client, mock_site_context
):
    application = _anonymous_draft(client)
    status_url = reverse("course_applications:status", kwargs={"pk": application.pk})

    response = client.post(status_url)

    assert response["Location"] == status_url


def _htmx_resend(client, application, *, next_url: str = ""):
    return client.post(
        reverse("course_applications:status", kwargs={"pk": application.pk}),
        {"next": next_url},
        HTTP_HX_REQUEST="true",
    )


@pytest.mark.django_db
def test_htmx_resend_returns_the_notice_saying_a_new_link_went(
    client, mock_site_context
):
    application = _anonymous_draft(client)
    mail.outbox.clear()

    response = _htmx_resend(client, application)

    body = response.content.decode()
    assert response.status_code == 200
    assert 'data-resend="sent"' in body
    assert "We've sent a new link to" in body
    assert "<html" not in body
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_htmx_resend_says_when_the_email_could_not_be_sent(client, mock_site_context):
    application = _anonymous_draft(client)

    with patch.object(AccountAdapter, "send_mail", _refuse_every_send):
        body = _htmx_resend(client, application).content.decode()

    assert 'data-resend="failed"' in body


@pytest.mark.django_db
def test_htmx_resend_raises_no_toast(client, mock_site_context):
    application = _anonymous_draft(client)

    body = _htmx_resend(client, application).content.decode()

    assert "toast-region" not in body


@pytest.mark.django_db
def test_htmx_resend_keeps_the_next_resend_on_the_page_it_came_from(
    client, mock_site_context
):
    application = _anonymous_draft(client)
    page_url = _page_url(application, 1)

    body = _htmx_resend(client, application, next_url=page_url).content.decode()

    assert f'<input type="hidden" name="next" value="{escape(page_url)}">' in body


@pytest.mark.django_db
def test_notice_form_carries_the_page_it_was_sent_from(client, mock_site_context):
    application = _anonymous_draft(client)
    page_url = f"{_page_url(application, 1)}?return=check"

    body = client.get(page_url).content.decode()

    assert f'<input type="hidden" name="next" value="{escape(page_url)}">' in body


@pytest.mark.django_db
def test_resend_post_from_a_draft_returns_to_the_page_it_was_sent_from(
    client, mock_site_context
):
    application = _anonymous_draft(client)
    page_url = f"{_page_url(application, 1)}?return=check"

    response = client.post(
        reverse("course_applications:status", kwargs={"pk": application.pk}),
        {"next": page_url},
    )

    assert response["Location"] == page_url


@pytest.mark.django_db
def test_resend_post_with_an_offsite_next_returns_to_the_status_url(
    client, mock_site_context
):
    application = _anonymous_draft(client)
    status_url = reverse("course_applications:status", kwargs={"pk": application.pk})

    response = client.post(status_url, {"next": "https://elsewhere.example/"})

    assert response["Location"] == status_url


@pytest.mark.django_db
def test_status_url_of_a_draft_redirects_on_to_page_one(client, mock_site_context):
    application = _anonymous_draft(client)

    response = client.get(
        reverse("course_applications:status", kwargs={"pk": application.pk})
    )

    assert response["Location"] == _page_url(application, 1)


@pytest.mark.django_db
def test_resend_post_from_a_draft_with_a_refused_send_adds_the_error_toast(
    client, mock_site_context
):
    application = _anonymous_draft(client)

    with patch.object(AccountAdapter, "send_mail", _refuse_every_send):
        response = client.post(
            reverse("course_applications:status", kwargs={"pk": application.pk})
        )

    assert [str(m) for m in get_messages(response.wsgi_request)] == [
        "We couldn't email ada@example.com just now. Try again in a little while."
    ]


def _change_email_url(application) -> str:
    return reverse(
        "course_applications:change_applicant_email", kwargs={"pk": application.pk}
    )


def _submitted_unverified(client, course):
    """Take a session through details and submit; returns the application."""
    _post_details(client, course)
    client.post(_apply_url(course))
    mail.outbox.clear()
    return CourseApplication.objects.get(course=course)


def _change_email(client, application, **data: str):
    return client.post(
        _change_email_url(application), {"email": "new@example.com", **data}
    )


@pytest.mark.django_db
def test_changing_the_address_bumps_the_claim_link_version(client, gated_course):
    application = _submitted_unverified(client, gated_course)

    _change_email(client, application)

    application.anonymous_applicant.refresh_from_db()
    assert application.anonymous_applicant.claim_link_version == 1


@pytest.mark.django_db
def test_changing_the_address_sends_one_email_to_the_new_address_only(
    client, gated_course
):
    application = _submitted_unverified(client, gated_course)

    _change_email(client, application)

    assert [message.to for message in mail.outbox] == [["new@example.com"]]


@pytest.mark.django_db
def test_changing_the_address_invalidates_the_earlier_link(client, gated_course):
    application = _submitted_unverified(client, gated_course)
    earlier_url = _claim_url(application.anonymous_applicant)

    _change_email(client, application)

    assert client.get(earlier_url).context["claim_state"] == "invalid"


@pytest.mark.django_db
def test_changing_the_address_redirects_to_the_status_page(client, gated_course):
    application = _submitted_unverified(client, gated_course)

    response = _change_email(client, application)

    assert response["Location"] == reverse(
        "course_applications:status", kwargs={"pk": application.pk}
    )


@pytest.mark.django_db
def test_changing_the_address_names_the_new_address_in_the_toast(client, gated_course):
    application = _submitted_unverified(client, gated_course)

    response = _change_email(client, application)

    assert [str(m) for m in get_messages(response.wsgi_request)] == [
        "We've emailed a link to new@example.com."
    ]


@pytest.mark.django_db
def test_posting_the_same_address_sends_nothing(client, gated_course):
    application = _submitted_unverified(client, gated_course)

    _change_email(client, application, email="ada@example.com")

    assert mail.outbox == []


@pytest.mark.django_db
def test_posting_the_same_address_keeps_the_claim_link_version(client, gated_course):
    application = _submitted_unverified(client, gated_course)

    response = _change_email(client, application, email="ada@example.com")

    application.anonymous_applicant.refresh_from_db()
    assert (
        response.status_code,
        application.anonymous_applicant.claim_link_version,
    ) == (
        302,
        0,
    )


@pytest.mark.django_db
def test_posting_an_invalid_address_is_422_with_the_field_error(client, gated_course):
    application = _submitted_unverified(client, gated_course)

    response = _change_email(client, application, email="not-an-address")

    assert response.status_code == 422
    assert "email" in response.context["email_form"].errors
    assert "course_applications/application_status.html" in [
        t.name for t in response.templates
    ]


@pytest.mark.django_db
def test_posting_an_invalid_address_sends_nothing(client, gated_course):
    application = _submitted_unverified(client, gated_course)

    _change_email(client, application, email="not-an-address")

    assert mail.outbox == []


@pytest.mark.django_db
def test_posting_a_filled_honeypot_is_422_with_the_non_field_error(
    client, gated_course
):
    application = _submitted_unverified(client, gated_course)

    response = _change_email(client, application, fax_number="bot")

    assert response.status_code == 422
    assert len(response.context["email_form"].non_field_errors()) == 1


@pytest.mark.django_db
def test_change_email_honeypot_trips_spend_the_address_limit(gated_course):
    with override_settings(ACCOUNT_RATE_LIMITS=DETAILS_RATE_LIMITS):
        cache.clear()
        client = Client()
        application = _submitted_unverified(client, gated_course)
        for index in range(4):
            Client().post(
                _details_url(gated_course),
                _details_data(email="new@example.com", fax_number="bot"),
                REMOTE_ADDR=f"10.0.0.{index + 1}",
            )
        _change_email(client, application, fax_number="bot")

        response = Client().post(
            _details_url(gated_course),
            _details_data(email="new@example.com"),
            REMOTE_ADDR="10.1.1.1",
        )

    assert response.status_code == 429


@pytest.mark.django_db
@pytest.mark.parametrize("has_account", [True, False])
def test_change_answers_the_same_whether_or_not_the_address_has_an_account(
    client, gated_course, has_account
):
    application = _submitted_unverified(client, gated_course)
    address = str(UserFactory().email) if has_account else "free@example.com"

    response = _change_email(client, application, email=address)

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "course_applications:status", kwargs={"pk": application.pk}
    )
    assert [str(m) for m in get_messages(response.wsgi_request)] == [
        f"We've emailed a link to {address}."
    ]


@pytest.mark.django_db
def test_change_post_reads_no_user_table(client, gated_course):
    application = _submitted_unverified(client, gated_course)

    with CaptureQueriesContext(connection) as queries:
        _change_email(client, application)

    sql = " ".join(query["sql"] for query in queries.captured_queries)
    assert (
        any(table in sql for table in ("accounts_user", "account_emailaddress"))
        is False
    )


@pytest.mark.django_db
def test_change_email_on_a_draft_moves_it_to_the_new_address(client, mock_site_context):
    application = _anonymous_draft(client)

    _change_email(client, application)

    application.anonymous_applicant.refresh_from_db()
    assert application.anonymous_applicant.email == "new@example.com"


@pytest.mark.django_db
def test_change_email_on_a_verified_application_is_404(client, mock_site_context):
    user = UserFactory()
    application = CourseApplicationFactory(user=user)
    client.force_login(user)

    response = _change_email(client, application)

    assert response.status_code == 404


@pytest.mark.django_db
def test_change_email_on_an_application_with_no_applicant_is_404(
    client, mock_site_context
):
    user = UserFactory()
    application = CourseApplicationFactory(user=user)
    CourseApplication.objects.filter(pk=application.pk).update(
        user=None, anonymous_applicant=None
    )
    client.force_login(user)

    response = _change_email(client, application)

    assert response.status_code == 404


@pytest.mark.django_db
def test_change_email_from_a_fresh_client_is_sent_to_log_in_at_the_status_page(
    client, gated_course
):
    application = _submitted_unverified(client, gated_course)
    status_url = reverse("course_applications:status", kwargs={"pk": application.pk})

    response = _change_email(Client(), application)

    assert response["Location"] == f"{reverse('account_login')}?next={status_url}"


@pytest.mark.django_db
def test_change_email_get_is_405(client, gated_course):
    application = _submitted_unverified(client, gated_course)

    response = client.get(_change_email_url(application))

    assert response.status_code == 405


@pytest.mark.django_db
def test_change_email_over_the_per_ip_limit_is_429_and_writes_nothing(gated_course):
    client = Client()
    with override_settings(ACCOUNT_RATE_LIMITS=DETAILS_RATE_LIMITS):
        cache.clear()
        application = _submitted_unverified(client, gated_course)
        _post_details_from_one_ip(gated_course, 5)

        response = client.post(
            _change_email_url(application),
            {"email": "new@example.com"},
            REMOTE_ADDR="10.9.9.9",
        )

    application.anonymous_applicant.refresh_from_db()
    assert (response.status_code, application.anonymous_applicant.email) == (
        429,
        "ada@example.com",
    )


@pytest.mark.django_db
def test_htmx_change_over_the_limit_is_429_with_the_notice_and_a_toast(
    mock_site_context,
):
    client = Client()
    with override_settings(ACCOUNT_RATE_LIMITS=DETAILS_RATE_LIMITS):
        cache.clear()
        application = _anonymous_draft(client)
        _post_details_from_one_ip(application.course, 5)

        response = client.post(
            _change_email_url(application),
            {"email": "new@example.com"},
            REMOTE_ADDR="10.9.9.9",
            HTTP_HX_REQUEST="true",
        )

    body = response.content.decode()
    assert response.status_code == 429
    assert 'data-testid="claim-link-notice"' in body
    assert "too many emails" in body


@pytest.mark.django_db
def test_status_page_of_an_unverified_application_offers_the_change_form(
    client, gated_course
):
    application = _submitted_unverified(client, gated_course)

    body = client.get(
        reverse("course_applications:status", kwargs={"pk": application.pk})
    ).content.decode()

    assert 'data-testid="change-email-form"' in body
    assert f'action="{_change_email_url(application)}"' in body


@pytest.mark.django_db
def test_status_page_of_a_verified_application_has_no_change_form(
    client, mock_site_context
):
    user = UserFactory()
    application = CourseApplicationFactory(user=user)
    client.force_login(user)

    body = client.get(
        reverse("course_applications:status", kwargs={"pk": application.pk})
    ).content.decode()

    assert 'data-testid="change-email-form"' not in body


@pytest.mark.django_db
def test_resend_form_on_the_change_email_422_page_posts_to_the_status_url(
    client, gated_course
):
    """The 422 page renders at the change-email URL, so a resend form with no
    action would post the change form again and never send anything."""
    application = _submitted_unverified(client, gated_course)

    body = _change_email(client, application, email="not-an-email").content.decode()

    status_url = reverse("course_applications:status", kwargs={"pk": application.pk})
    assert f'<form method="post" action="{status_url}"' in body


@pytest.mark.django_db
def test_posting_the_same_address_says_it_is_already_the_address(client, gated_course):
    application = _submitted_unverified(client, gated_course)

    response = _change_email(client, application, email="ada@example.com")

    assert [str(m) for m in get_messages(response.wsgi_request)] == [
        "ada@example.com is already the address on this application. "
        "Didn't get the email? Send it again."
    ]


def _let_the_claim_link_expire(application) -> None:
    applicant = application.anonymous_applicant
    applicant.claim_email_sent_at = (
        timezone.now() - claim_link_max_age() - timedelta(seconds=1)
    )
    applicant.save(update_fields=["claim_email_sent_at"])


@pytest.mark.django_db
def test_status_page_says_when_the_emailed_link_has_expired(client, gated_course):
    url = _unverified_status_url(client, gated_course)
    _let_the_claim_link_expire(CourseApplication.objects.get(course=gated_course))

    body = _page_text(client.get(url))

    assert (
        "The link we emailed to ada@example.com has expired" in body,
        "We've emailed a link" in body,
    ) == (True, False)


@pytest.mark.django_db
def test_form_page_notice_says_when_the_emailed_link_has_expired(
    client, mock_site_context
):
    application = _anonymous_draft(client)
    _let_the_claim_link_expire(application)

    body = client.get(_page_url(application, 1)).content.decode()

    assert (
        'data-sent="true" data-live="false"' in body,
        "has expired" in body,
    ) == (True, True)


@pytest.mark.django_db
def test_reposting_a_new_address_another_post_already_stored_sends_nothing(
    mock_site_context, client
):
    """Two tabs post the same new address: the second finds it stored, so the
    helper reports no change and no second email goes out."""
    course, _form = gated_course_with_form()
    _post_details(client, course)
    mail.outbox.clear()

    with patch(
        "freedom_ls.course_applications.views.update_applicant_email",
        return_value=False,
    ):
        _post_details(client, course, email="new@example.com")

    assert mail.outbox == []


@pytest.mark.django_db
class TestApplyConversion:
    """Starting an application records one referral conversion for the new row."""

    def test_starting_an_application_writes_one_course_application_conversion(
        self, client, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory()
        client.force_login(user)

        client.post(_apply_url(course))

        conversion = Conversion._base_manager.get(user=user)
        app = CourseApplication.objects.get(user=user, course=course)
        assert conversion.kind == ConversionKind.COURSE_APPLICATION
        assert conversion.target == app
        assert conversion.occurred_at == app.created_at
        assert conversion.target_label == course.title

    def test_visit_with_an_existing_application_writes_no_conversion(
        self, client, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory()
        CourseApplicationFactory(user=user, course=course)
        client.force_login(user)

        client.post(_apply_url(course))

        assert not Conversion._base_manager.exists()

    def test_anonymous_start_writes_no_conversion(self, client, gated_course):
        _post_details(client, gated_course)

        client.post(_apply_url(gated_course))

        assert not Conversion._base_manager.exists()

    def test_tracked_landing_on_a_form_course_freezes_its_code(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        user = UserFactory()
        client.force_login(user)

        client.get(_apply_url(course), {"ref": "A"})

        conversion = Conversion._base_manager.get(user=user)
        assert (conversion.first_referral_code, conversion.last_referral_code) == (
            "A",
            "A",
        )

    def test_first_and_last_codes_come_from_the_earliest_and_latest_touches(
        self, client, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory()
        AttributionTouchFactory(
            user=user,
            referral_code="A",
            occurred_at=timezone.now() - timedelta(days=21),
            recorded_via=TouchSource.SIGNUP_FLUSH,
        )
        AttributionTouchFactory(
            user=user,
            referral_code="B",
            occurred_at=timezone.now() - timedelta(days=1),
            recorded_via=TouchSource.SIGNUP_FLUSH,
        )
        client.force_login(user)

        client.post(_apply_url(course))

        conversion = Conversion._base_manager.get(user=user)
        assert (conversion.first_referral_code, conversion.last_referral_code) == (
            "A",
            "B",
        )

    def test_failed_conversion_write_leaves_the_application_and_the_redirect(
        self, client, mock_site_context, mocker
    ):
        user = UserFactory()
        course = CourseFactory()
        client.force_login(user)
        mocker.patch.object(
            Conversion._base_manager,
            "get_or_create",
            side_effect=DatabaseError("boom"),
        )
        mocker.patch("freedom_ls.referral_tracking.best_effort.sentry_sdk")

        response = client.post(_apply_url(course))

        app = CourseApplication.objects.get(user=user, course=course)
        assert response["Location"] == reverse(
            "course_applications:status", kwargs={"pk": app.pk}
        )


# ---------------------------------------------------------------------------
# A quiz application form follows its served paper
# ---------------------------------------------------------------------------


class QuizApplication(NamedTuple):
    """An application whose quiz sitting is served page 3, page 1, then page 2."""

    application: CourseApplication
    course: Course
    sitting: FormProgress
    pick: FormQuestion
    extra: FormQuestion
    second: FormQuestion
    third: FormQuestion
    first_option: QuestionOption
    second_option: QuestionOption


def _quiz_application_form() -> tuple[
    Course,
    Form,
    tuple[FormQuestion, FormQuestion, FormQuestion, FormQuestion],
    tuple[QuestionOption, QuestionOption],
]:
    """A quiz application form of three pages, every question required but `extra`.

    Page 1 holds `pick` (a multiple choice) and `extra`; pages 2 and 3 hold one
    short text question each.
    """
    form: Form = FormFactory(strategy=FormStrategy.QUIZ)
    page_one = FormPageFactory(form=form, order=0, title="First authored")
    pick: FormQuestion = FormQuestionFactory(
        form_page=page_one, type="multiple_choice", order=0, required=True
    )
    first_option: QuestionOption = QuestionOptionFactory(
        question=pick, text="Alpha", order=0
    )
    second_option: QuestionOption = QuestionOptionFactory(
        question=pick, text="Omega", order=1
    )
    extra: FormQuestion = FormQuestionFactory(
        form_page=page_one, type="short_text", order=1, required=False
    )
    page_two = FormPageFactory(form=form, order=1, title="Second authored")
    second: FormQuestion = FormQuestionFactory(
        form_page=page_two, type="short_text", order=0, required=True
    )
    page_three = FormPageFactory(form=form, order=2, title="Third authored")
    third: FormQuestion = FormQuestionFactory(
        form_page=page_three, type="short_text", order=0, required=True
    )
    course: Course = CourseFactory(access_config={"access_type": "application_gated"})
    course.application_form = form
    course.save(update_fields=["application_form"])
    return course, form, (pick, extra, second, third), (first_option, second_option)


def _served_quiz_application(
    client: Client, *, with_paper: bool = True
) -> QuizApplication:
    """A signed-in applicant's quiz sitting, served page 3, page 1, then page 2.

    On page 1 the optional question comes before the multiple choice and its
    options are served Omega before Alpha.
    """
    course, form, (pick, extra, second, third), (first_option, second_option) = (
        _quiz_application_form()
    )
    app = _applied(client, course)
    sitting = app.form_progress
    if with_paper:
        page_one, page_two, page_three = form.pages.all()
        FormProgress.objects.filter(pk=sitting.pk).update(
            served_paper=served_paper_of(
                [
                    (page_three, [third]),
                    (page_one, [extra, pick]),
                    (page_two, [second]),
                ],
                {pick: [second_option, first_option]},
            )
        )
    else:
        # Starting the application already served a paper; clear it.
        FormProgress.objects.filter(pk=sitting.pk).update(served_paper=None)
    sitting.refresh_from_db()
    return QuizApplication(
        app, course, sitting, pick, extra, second, third, first_option, second_option
    )


@pytest.fixture
def quiz_application(client: Client, mock_site_context: object) -> QuizApplication:
    return _served_quiz_application(client)


@pytest.fixture
def paperless_quiz_application(
    client: Client, mock_site_context: object
) -> QuizApplication:
    return _served_quiz_application(client, with_paper=False)


def _paper_of(sitting: FormProgress) -> object:
    sitting.refresh_from_db()
    return sitting.served_paper


@pytest.mark.django_db
def test_the_resume_url_writes_the_served_paper_of_an_open_quiz_sitting(
    client, paperless_quiz_application
):
    app = paperless_quiz_application.application

    client.get(reverse("course_applications:status", kwargs={"pk": app.pk}))

    assert _paper_of(paperless_quiz_application.sitting) is not None


@pytest.mark.django_db
def test_a_page_get_writes_the_served_paper_of_an_open_quiz_sitting(
    client, paperless_quiz_application
):
    app = paperless_quiz_application.application

    client.get(_page_url(app, 1))

    assert _paper_of(paperless_quiz_application.sitting) is not None


@pytest.mark.django_db
def test_a_page_post_writes_the_served_paper_of_an_open_quiz_sitting(
    client, paperless_quiz_application
):
    app = paperless_quiz_application.application

    client.post(_page_url(app, 1), {})

    assert _paper_of(paperless_quiz_application.sitting) is not None


@pytest.mark.django_db
def test_check_your_answers_writes_the_served_paper_of_an_open_quiz_sitting(
    client, paperless_quiz_application
):
    app = paperless_quiz_application.application

    client.get(_check_url(app))

    assert _paper_of(paperless_quiz_application.sitting) is not None


@pytest.mark.django_db
def test_an_application_form_that_is_not_a_quiz_gets_no_served_paper(
    client, mock_site_context
):
    course, _form = gated_course_with_form()
    app = _applied(client, course)

    client.get(_page_url(app, 1))

    assert _paper_of(app.form_progress) is None


@pytest.mark.django_db
def test_a_visitor_who_does_not_own_the_application_writes_no_served_paper(
    client, paperless_quiz_application
):
    app = paperless_quiz_application.application
    client.force_login(UserFactory())

    response = client.get(_page_url(app, 1))

    assert response.status_code == 404
    assert _paper_of(paperless_quiz_application.sitting) is None


@pytest.mark.django_db
def test_resuming_a_quiz_application_continues_on_the_first_served_page(
    client: Client, quiz_application: QuizApplication
) -> None:
    app = quiz_application.application

    response = client.get(reverse("course_applications:status", kwargs={"pk": app.pk}))

    assert f'href="{_page_url(app, 3)}"' in response.content.decode()


@pytest.mark.django_db
def test_posting_a_quiz_application_page_goes_to_the_next_served_page(
    client, quiz_application
):
    app = quiz_application.application

    response = client.post(
        _page_url(app, 3), {f"question_{quiz_application.third.id}": "answer"}
    )

    assert response["Location"] == _page_url(app, 1)


@pytest.mark.django_db
def test_a_quiz_application_page_shows_its_options_in_served_order(
    client, quiz_application
):
    body = client.get(_page_url(quiz_application.application, 1)).content.decode()

    assert body.index("Omega") < body.index("Alpha")


@pytest.mark.django_db
def test_check_your_answers_lists_a_quiz_application_in_served_order(
    client, quiz_application
):
    app = quiz_application.application

    response = client.get(_check_url(app))

    assert [s["title"] for s in response.context["sections"]] == [
        "Third authored",
        "First authored",
        "Second authored",
    ]
    assert [s["number"] for s in response.context["sections"]] == [1, 2, 3]
    assert [s["edit_url"] for s in response.context["sections"]] == [
        _edit_url(app, 3),
        _edit_url(app, 1),
        _edit_url(app, 2),
    ]


@pytest.mark.django_db
def test_check_your_answers_lists_a_served_page_questions_in_served_order(
    client, quiz_application
):
    response = client.get(_check_url(quiz_application.application))

    rows = response.context["sections"][1]["rows"]
    assert [row["question"] for row in rows] == [
        quiz_application.extra,
        quiz_application.pick,
    ]


@pytest.mark.django_db
def test_an_edit_that_leaves_a_required_question_unanswered_goes_to_the_next_served_page(
    client, quiz_application
):
    app = quiz_application.application

    response = client.post(
        _edit_url(app, 3), {f"question_{quiz_application.third.id}": "answer"}
    )

    assert response["Location"] == _edit_url(app, 1)


@pytest.fixture
def answered_quiz_application(
    client: Client, quiz_application: QuizApplication
) -> QuizApplication:
    """The served quiz application with every required question answered."""
    app = quiz_application.application
    client.post(_page_url(app, 3), {f"question_{quiz_application.third.id}": "c"})
    client.post(_page_url(app, 2), {f"question_{quiz_application.second.id}": "b"})
    client.post(
        _page_url(app, 1),
        {f"question_{quiz_application.pick.id}": str(quiz_application.first_option.id)},
    )
    return quiz_application


@pytest.mark.django_db
def test_submitting_a_served_quiz_application_completes_the_sitting(
    client, answered_quiz_application
):
    client.post(_check_url(answered_quiz_application.application))

    answered_quiz_application.sitting.refresh_from_db()
    assert answered_quiz_application.sitting.completed_time is not None


def _anonymous_quiz_application(client: Client) -> CourseApplication:
    """An anonymous applicant's quiz sitting, served page 3, page 1, then page 2."""
    course, form, (pick, extra, second, third), (_first, _second_option) = (
        _quiz_application_form()
    )
    _post_details(client, course)
    app: CourseApplication = CourseApplication.objects.get(course=course)
    page_one, page_two, page_three = form.pages.all()
    FormProgress.objects.filter(pk=app.form_progress_id).update(
        served_paper=served_paper_of(
            [(page_three, [third]), (page_one, [extra, pick]), (page_two, [second])]
        )
    )
    return app


@pytest.mark.django_db
def test_an_anonymous_applicant_sees_the_details_back_link_on_the_first_served_page(
    client, mock_site_context
):
    app = _anonymous_quiz_application(client)

    response = client.get(_page_url(app, 3))

    assert response.context["previous_page_url"] == reverse(
        "course_applications:applicant_details",
        kwargs={"course_slug": app.course.slug},
    )


@pytest.mark.django_db
def test_an_anonymous_applicant_sees_the_previous_served_page_link_on_the_others(
    client, mock_site_context
):
    app = _anonymous_quiz_application(client)

    response = client.get(_page_url(app, 1))

    assert response.context["previous_page_url"] == _page_url(app, 3)


# ---------------------------------------------------------------------------
# Status page per state and withdraw
# ---------------------------------------------------------------------------


def _status_url(app: CourseApplication) -> str:
    return reverse("course_applications:status", kwargs={"pk": app.pk})


def _withdraw_url(app: CourseApplication) -> str:
    return reverse("course_applications:withdraw", kwargs={"pk": app.pk})


def _claimed_draft(user: User) -> CourseApplication:
    return cast(
        CourseApplication,
        CourseApplicationFactory(
            user=user, form_progress=FormProgressFactory(user=user)
        ),
    )


def _messages_of(response: _MonkeyPatchedWSGIResponse) -> list[str]:
    return [str(m) for m in get_messages(response.wsgi_request)]


# What a closed row of a submitted application holds, so the state check
# constraints stay satisfied when a test closes an application in place.
_CLOSED_FIELDS = {
    "withdrawn": {"withdrawn_at": timezone.now},
    "rejected": {
        "submitted_at": timezone.now,
        "decided_at": timezone.now,
        "rejection_message": lambda: "Not this time.",
    },
}


def _close_in_place(app: CourseApplication, state: str) -> None:
    fields = {name: make() for name, make in _CLOSED_FIELDS[state].items()}
    CourseApplication.objects.filter(pk=app.pk).update(state=state, **fields)


@pytest.mark.django_db
class TestWithdrawApplicationView:
    def test_owner_withdraw_redirects_to_status_and_stores_withdrawn(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        app = CourseApplicationFactory(user=user)
        client.force_login(user)

        response = client.post(_withdraw_url(app))

        app.refresh_from_db()
        assert response["Location"] == _status_url(app)
        assert app.state == CourseApplication.State.WITHDRAWN

    def test_owner_withdraw_says_it_was_withdrawn(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        app = CourseApplicationFactory(user=user)
        client.force_login(user)

        response = client.post(_withdraw_url(app))

        assert _messages_of(response) == ["Application withdrawn."]

    @pytest.mark.parametrize(
        "trait",
        [{"withdrawn": True}, {"approved": True}, {"rejected": True}],
        ids=["withdrawn", "approved", "rejected"],
    )
    def test_withdraw_of_a_closed_or_decided_application_is_refused(
        self, client: Client, mock_site_context: Site, trait: dict[str, bool]
    ) -> None:
        user = UserFactory()
        app = CourseApplicationFactory(user=user, **trait)
        before = CourseApplication.objects.get(pk=app.pk)
        client.force_login(user)

        response = client.post(_withdraw_url(app))

        after = CourseApplication.objects.get(pk=app.pk)
        assert response["Location"] == _status_url(app)
        assert _messages_of(response) == [
            "This application can no longer be withdrawn."
        ]
        assert (after.state, after.updated_at) == (before.state, before.updated_at)

    def test_withdraw_of_another_accounts_application_is_404(
        self, client: Client, mock_site_context: Site
    ) -> None:
        app = CourseApplicationFactory(user=UserFactory())
        client.force_login(UserFactory())

        response = client.post(_withdraw_url(app))

        assert response.status_code == 404

    def test_withdraw_of_an_unclaimed_application_in_its_own_session_is_404(
        self, client: Client, mock_site_context: Site
    ) -> None:
        app = _anonymous_draft(client)

        response = client.post(_withdraw_url(app))

        assert response.status_code == 404

    def test_withdraw_of_an_unclaimed_application_changes_nothing(
        self, client: Client, mock_site_context: Site
    ) -> None:
        app = _anonymous_draft(client)

        client.post(_withdraw_url(app))

        app.refresh_from_db()
        assert app.state == CourseApplication.State.DRAFT

    def test_withdraw_by_a_signed_out_visitor_redirects_to_login_for_the_status_page(
        self, client: Client, mock_site_context: Site
    ) -> None:
        app = CourseApplicationFactory(user=UserFactory())

        response = client.post(_withdraw_url(app))

        assert response["Location"] == (
            f"{reverse('account_login')}?next={_status_url(app)}"
        )

    def test_withdraw_by_get_is_405(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        app = CourseApplicationFactory(user=user)
        client.force_login(user)

        response = client.get(_withdraw_url(app))

        assert response.status_code == 405


@pytest.mark.django_db
class TestApplicationStatusStates:
    def test_a_claimed_draft_renders_its_status_page(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        app = _claimed_draft(user)
        client.force_login(user)

        response = client.get(_status_url(app))

        assert response.status_code == 200
        assert "Not submitted" in response.content.decode()

    def test_a_claimed_draft_links_to_its_resume_url(
        self, client: Client, mock_site_context: Site
    ) -> None:
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        body = client.get(_status_url(app)).content.decode()

        assert f'href="{_page_url(app, 1)}"' in body
        assert "Continue application" in body

    def test_a_claimed_draft_offers_withdraw(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        app = _claimed_draft(user)
        client.force_login(user)

        body = client.get(_status_url(app)).content.decode()

        assert f'action="{_withdraw_url(app)}"' in body

    def test_an_unclaimed_draft_is_sent_to_its_form(
        self, client: Client, mock_site_context: Site
    ) -> None:
        app = _anonymous_draft(client)

        response = client.get(_status_url(app))

        assert response["Location"] == _page_url(app, 1)

    def test_a_submitted_application_shows_state_date_and_withdraw(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        app = CourseApplicationFactory(user=user)
        client.force_login(user)

        body = client.get(_status_url(app)).content.decode()

        assert "Waiting for review" in body
        assert "Submitted" in body
        assert f'action="{_withdraw_url(app)}"' in body

    def test_a_withdrawn_application_says_so_and_offers_no_withdraw(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        app = CourseApplicationFactory(user=user, withdrawn=True)
        client.force_login(user)

        body = client.get(_status_url(app)).content.decode()

        assert "You withdrew your application" in body
        assert _withdraw_url(app) not in body

    def test_a_withdrawn_draft_renders_instead_of_resuming_its_form(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        app = CourseApplicationFactory(
            user=user,
            form_progress=FormProgressFactory(user=user),
            withdrawn=True,
        )
        client.force_login(user)

        response = client.get(_status_url(app))

        assert response.status_code == 200
        assert "You withdrew your application" in response.content.decode()

    def test_the_page_title_holds_the_state_label(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        app = CourseApplicationFactory(user=user, withdrawn=True)
        client.force_login(user)

        body = client.get(_status_url(app)).content.decode()

        assert re.search(r"<title>[^<]*Withdrawn · Application", body)

    def test_an_unclaimed_submitted_application_offers_no_withdraw(
        self, client: Client, mock_site_context: Site
    ) -> None:
        app = _anonymous_draft(client)
        CourseApplication.objects.filter(pk=app.pk).update(
            state=CourseApplication.State.SUBMITTED, submitted_at=timezone.now()
        )

        body = client.get(_status_url(app)).content.decode()

        assert "Check your email" in body
        assert _withdraw_url(app) not in body


@pytest.mark.django_db
class TestClosedApplicationAcceptsNoWrites:
    @pytest.mark.parametrize("state", ["withdrawn", "rejected"])
    def test_a_form_page_post_redirects_to_status_and_changes_no_answer(
        self, client: Client, mock_site_context: Site, state: str
    ) -> None:
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})
        _close_in_place(app, state)

        response = client.post(_page_url(app, 1), {f"question_{name.id}": "Grace"})

        answer = app.form_progress.answers.get(question=name)
        assert response["Location"] == _status_url(app)
        assert answer.text_answer == "Ada"

    def test_a_form_page_post_changes_no_answer_when_withdrawn_mid_request(
        self, client: Client, mock_site_context: Site
    ) -> None:
        """The view has already read the draft when another tab withdraws it."""
        from freedom_ls.course_applications import views

        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})
        serve = views.ensure_served_paper

        def serve_then_withdraw(form_progress: FormProgress) -> None:
            serve(form_progress)
            _close_in_place(app, "withdrawn")

        with patch.object(views, "ensure_served_paper", serve_then_withdraw):
            response = client.post(_page_url(app, 1), {f"question_{name.id}": "Grace"})

        answer = app.form_progress.answers.get(question=name)
        assert response["Location"] == _status_url(app)
        assert answer.text_answer == "Ada"

    @pytest.mark.parametrize("state", ["withdrawn", "rejected"])
    def test_a_check_your_answers_post_redirects_to_status_and_keeps_the_state(
        self, client: Client, mock_site_context: Site, state: str
    ) -> None:
        course, _form = gated_course_with_form()
        app = _applied(client, course)
        _close_in_place(app, state)

        response = client.post(_check_url(app))

        app.refresh_from_db()
        assert response["Location"] == _status_url(app)
        assert app.state == state


@pytest.mark.django_db
class TestDecidedApplicationStatusPage:
    def test_an_approved_application_shows_the_decision_and_no_withdraw(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        app = CourseApplicationFactory(user=user, approved=True)
        client.force_login(user)

        body = client.get(_status_url(app)).content.decode()

        assert "Your application was approved" in body
        assert "was approved on" in body
        assert _withdraw_url(app) not in body

    def test_a_rejected_application_shows_the_message_and_offers_apply_again(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        app = CourseApplicationFactory(user=user, rejected=True)
        client.force_login(user)

        body = client.get(_status_url(app)).content.decode()

        assert "Your application was declined" in body
        assert "Message from the reviewer" not in body
        assert "not approved" not in body.lower()
        assert "Not this time." in body
        assert "You can apply again." in body
        assert (
            reverse(
                "course_applications:apply", kwargs={"course_slug": app.course.slug}
            )
            in body
        )
        assert _withdraw_url(app) not in body

    def test_a_rejection_message_is_escaped_and_keeps_its_line_breaks(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        app = CourseApplicationFactory(
            user=user, rejected=True, rejection_message="<script>x</script>\nSecond"
        )
        client.force_login(user)

        body = client.get(_status_url(app)).content.decode()

        assert "<script>x</script>" not in body
        assert "&lt;script&gt;x&lt;/script&gt;<br>Second" in body

    def test_an_unclaimed_rejected_application_shows_message_beside_claim_notice(
        self, client: Client, mock_site_context: Site
    ) -> None:
        app = _anonymous_draft(client)
        CourseApplication.objects.filter(pk=app.pk).update(
            state=CourseApplication.State.REJECTED,
            submitted_at=timezone.now(),
            decided_at=timezone.now(),
            rejection_message="Not this time.",
        )

        body = client.get(_status_url(app)).content.decode()

        assert "Check your email" in body
        assert "Not this time." in body
        assert "Apply again" not in body

    def test_an_unclaimed_rejected_application_claim_notice_does_not_say_it_awaits_review(
        self, client: Client, mock_site_context: Site
    ) -> None:
        """The claim notice above a decision used to say "Before anyone reviews
        it", contradicting the decision shown right below it."""
        app = _anonymous_draft(client)
        CourseApplication.objects.filter(pk=app.pk).update(
            state=CourseApplication.State.REJECTED,
            submitted_at=timezone.now(),
            decided_at=timezone.now(),
            rejection_message="Not this time.",
        )

        body = client.get(_status_url(app)).content.decode()

        assert ("Check your email" in body, "Before anyone reviews it" in body) == (
            True,
            False,
        )

    def test_the_status_page_reads_what_reject_application_stored(
        self, client: Client, mock_site_context: Site
    ) -> None:
        user = UserFactory()
        app = CourseApplicationFactory(user=user)
        reject_application(app, actor=UserFactory(), message="  Come back in spring.  ")
        client.force_login(user)

        body = client.get(_status_url(app)).content.decode()

        assert "Come back in spring." in body


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["question_file_upload", "question_file_remove"])
def test_a_withdrawn_draft_refuses_file_changes(
    client: Client, mock_site_context: Site, route: str
) -> None:
    course, form = gated_course_with_form()
    app = _applied(client, course)
    answer_file = _attach_file(client, form, app)
    withdraw_application(app)

    response = client.post(
        reverse(
            f"form_engine:{route}",
            kwargs={
                "progress_pk": app.form_progress.pk,
                "question_pk": answer_file.answer.question_id,
            },
        ),
        {"file": SimpleUploadedFile("other.png", png_bytes())},
        HTTP_HX_REQUEST="true",
    )

    answer_file.refresh_from_db()
    assert (response.status_code, answer_file.original_filename) == (
        409,
        "id-scan.png",
    )
