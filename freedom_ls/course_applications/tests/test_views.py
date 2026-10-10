"""Tests for course_applications views."""

from __future__ import annotations

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import (
    EmailAddressFactory,
    SiteSignupPolicyFactory,
    UserFactory,
)
from freedom_ls.accounts.tests._auth_page_helpers import _next_param
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.tests.app_guards import app_not_installed
from freedom_ls.tests.images import png_bytes

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.claims import UNCLAIMED_APPLICATIONS_SESSION_KEY
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.form_engine.anonymous_sittings import ANONYMOUS_SITTINGS_SESSION_KEY
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
)
from freedom_ls.form_engine.models import FormProgress, FormStrategy
from freedom_ls.form_engine.queries import page_questions
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.learner_progress.models import CourseFormAttempt

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
class TestApplyViewPost:
    """POST /apply/<slug>/ — creates application and redirects to status."""

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

    def test_status_page_contains_pending_review_message(
        self, client, mock_site_context
    ):
        """Status page contains the pending-review confirmation message."""
        user = UserFactory()
        app = CourseApplicationFactory(user=user)
        client.force_login(user)

        url = reverse("course_applications:status", kwargs={"pk": app.pk})
        response = client.get(url)

        content = response.content.decode()
        # The page must mention that the application has been received
        assert "received" in content.lower() or "pending" in content.lower()

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
        """Unauthenticated access to status page redirects to login with next set to the status URL."""
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


def _about_you_url(app):
    return reverse("course_applications:about_you", kwargs={"pk": app.pk})


def _check_url(app):
    return reverse("course_applications:check_answers", kwargs={"pk": app.pk})


def _questions_on(form, page_number):
    page = list(form.pages.all())[page_number - 1]
    return page_questions(page)


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
    def test_an_unfinished_application_is_sent_back_to_its_form(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        response = client.get(
            reverse("course_applications:status", kwargs={"pk": app.pk})
        )

        assert response["Location"] == _page_url(app, 1)

    def test_a_submitted_application_renders_its_status(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        app = _applied(client, course)
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

    def test_the_status_page_resumes_on_the_check_page(self, client, mock_site_context):
        course = _gated_course_with_a_page_less_form()
        app = _applied(client, course)

        response = client.get(
            reverse("course_applications:status", kwargs={"pk": app.pk})
        )

        assert response["Location"] == _check_url(app)

    def test_the_check_page_renders_and_submits(self, client, mock_site_context):
        course = _gated_course_with_a_page_less_form()
        app = _applied(client, course)

        assert client.get(_check_url(app)).status_code == 200
        client.post(_check_url(app))

        app.refresh_from_db()
        assert app.form_progress.completed_time is not None


@pytest.mark.django_db
class TestApplicationFormPage:
    def test_the_owner_sees_page_one(self, client, mock_site_context):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        response = client.get(_page_url(app, 1))

        assert response.status_code == 200

    def test_a_form_page_is_never_cached(self, client, mock_site_context):
        """A back-nav must re-read the answers, or it shows work that has since
        changed."""
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        response = client.get(_page_url(app, 1))

        assert "no-store" in response["Cache-Control"]

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

        accessible = [link.is_accessible for link in response.context["page_links"]]
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

        assert "Your background" in body
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
            "and is pending review."
        ]

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
        app.form_progress.complete()

        body = client.get(_page_url(app, 1)).content.decode()

        assert "can no longer be changed" in body

    def test_a_submitted_application_disables_its_inputs(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        app = _applied(client, course)
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

        assert not response.context["submitted"]

    def test_a_submitted_application_cannot_be_submitted_again(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})
        client.post(_check_url(app))

        response = client.get(_check_url(app))

        assert response.context["submitted"]

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


# ---------------------------------------------------------------------------
# Rejected (invalid) typed answers
# ---------------------------------------------------------------------------


def _course_with_single_question(question_type: str, *, required: bool = False):
    """An application-gated course whose one-page form carries a single
    question of `question_type`, isolated from the rest of the fixture form
    so a rejected answer's effect on paging and completion is unambiguous.
    """
    form = FormFactory(strategy=FormStrategy.UNSCORED)
    page = FormPageFactory(form=form, order=0, title="Your background")
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
def test_anonymous_access_to_apply_on_closed_site_redirects_to_login_with_next(
    mock_site_context, course_with_topic, settings
):
    """Anonymous GET of apply on a site closed for signups goes to login?next=<apply-url>."""
    settings.ALLOW_SIGN_UPS = False
    course = course_with_topic(access_type="application_gated")
    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    response = Client().get(apply_url, follow=False)

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("account_login"))
    assert _next_param(response["Location"]) == apply_url


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
def test_deferred_login_apply_round_trip_creates_no_application(
    mock_site_context, client, settings
):
    """An anonymous apply GET creates nothing; only the POST does.

    On a closed site the anonymous POST redirects to login with next set to
    the apply URL itself. Following that next after signing in lands on the GET
    confirmation page, not an auto-created application.
    """
    settings.ALLOW_SIGN_UPS = False
    course = CourseFactory()
    user = UserFactory()

    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    response = client.post(apply_url)
    next_url = _next_param(response["Location"])

    client.force_login(user)
    followed = client.get(next_url)

    assert followed.status_code == 200
    assert not CourseApplication.objects.filter(course=course).exists()


@pytest.mark.django_db
def test_anonymous_apply_post_creates_an_unclaimed_application(
    mock_site_context, client
):
    course = CourseFactory()
    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )

    client.get(apply_url)
    assert not CourseApplication.objects.exists()
    client.post(apply_url, {"first_name": "Pat", "email": "pat@example.com"})

    assert CourseApplication.objects.filter(
        course=course, user__isnull=True, email="pat@example.com"
    ).exists()


@pytest.mark.django_db
def test_deferred_login_apply_repeat_submissions_stay_idempotent(
    mock_site_context, client
):
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
def test_deferred_login_application_status_owner_sees_status_page(
    mock_site_context, client
):
    """After the login round trip, the application owner reaches their status page."""
    owner = UserFactory()
    app = CourseApplicationFactory(user=owner)

    status_url = reverse("course_applications:status", kwargs={"pk": app.pk})
    response = client.get(status_url, follow=False)
    next_url = _next_param(response["Location"])

    client.force_login(owner)
    followed = client.get(next_url)

    assert followed.status_code == 200


@pytest.mark.django_db
def test_deferred_login_application_status_non_owner_gets_404(
    mock_site_context, client
):
    """After the login round trip, a non-owner still gets 404 on someone else's status page."""
    owner = UserFactory()
    other_user = UserFactory()
    app = CourseApplicationFactory(user=owner)

    status_url = reverse("course_applications:status", kwargs={"pk": app.pk})
    response = client.get(status_url, follow=False)
    next_url = _next_param(response["Location"])

    client.force_login(other_user)
    followed = client.get(next_url)

    assert followed.status_code == 404


# ---------------------------------------------------------------------------
# Hidden courses: login redirect, never a 404 (no enumeration signal)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_access_to_hidden_course_apply_is_404_on_open_site(
    mock_site_context,
):
    """On a site open for signups, apply serves anonymous visitors itself, so a
    hidden course answers 404 like any unknown slug."""
    course = CourseFactory(visibility=CourseVisibility.HIDDEN)

    url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
    response = Client().get(url, follow=False)

    assert response.status_code == 404


@pytest.mark.django_db
def test_anonymous_access_to_hidden_course_apply_redirects_to_login_on_closed_site(
    mock_site_context, settings
):
    """With signups closed the login redirect comes before any course lookup,
    so it reveals nothing about which slugs exist."""
    settings.ALLOW_SIGN_UPS = False
    course = CourseFactory(visibility=CourseVisibility.HIDDEN)

    url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
    response = Client().get(url, follow=False)

    assert response["Location"] == f"{reverse('account_login')}?next={url}"


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
    """The same holds for an application status page belonging to a hidden course."""
    course = CourseFactory(visibility=CourseVisibility.HIDDEN)
    owner = UserFactory()
    app = CourseApplicationFactory(user=owner, course=course)
    client = Client()

    url = reverse("course_applications:status", kwargs={"pk": app.pk})
    response = client.get(url, follow=False)

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('account_login')}?next={url}"


# ---------------------------------------------------------------------------
# anonymous apply
# ---------------------------------------------------------------------------


def _apply_url(course):
    return reverse("course_applications:apply", kwargs={"course_slug": course.slug})


@pytest.mark.django_db
class TestAnonymousApply:
    def test_anonymous_apply_on_closed_signup_site_redirects_to_login_with_next(
        self, client, mock_site_context, settings
    ):
        settings.ALLOW_SIGN_UPS = False
        course = CourseFactory()
        url = _apply_url(course)

        response = client.get(url)

        assert response.status_code == 302
        assert response["Location"] == f"{reverse('account_login')}?next={url}"

    def test_anonymous_apply_to_hidden_course_is_404(self, client, mock_site_context):
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)

        response = client.get(_apply_url(course))

        assert response.status_code == 404

    def test_anonymous_apply_to_coming_soon_course_redirects_to_detail(
        self, client, mock_site_context
    ):
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

        response = client.get(_apply_url(course))

        assert response["Location"] == reverse(
            "learner_interface:course_detail", kwargs={"course_slug": course.slug}
        )

    def test_anonymous_no_form_get_shows_about_you_with_a_submit_button(
        self, client, mock_site_context
    ):
        course = CourseFactory()

        response = client.get(_apply_url(course))

        body = response.content.decode()
        assert response.status_code == 200
        assert "<h1>About you</h1>" in body
        assert 'name="email"' in body
        assert "Submit application" in body

    def test_anonymous_no_form_get_creates_nothing(self, client, mock_site_context):
        course = CourseFactory()

        client.get(_apply_url(course))

        assert not CourseApplication.objects.exists()

    def test_about_you_post_for_no_form_course_submits_and_hands_off(
        self, client, mock_site_context
    ):
        course = CourseFactory()

        with patch(
            "freedom_ls.course_applications.views.record_application_submitted"
        ) as record:
            response = client.post(
                _apply_url(course), {**ABOUT_YOU_DETAILS, "email": "Ada@Example.com"}
            )

        app = CourseApplication.objects.get(course=course)
        location = response["Location"]
        assert (app.user, app.first_name, app.last_name, app.email) == (
            None,
            "Ada",
            "Lovelace",
            "ada@example.com",
        )
        assert (app.form_progress, FormProgress.objects.count()) == (None, 0)
        assert client.session[UNCLAIMED_APPLICATIONS_SESSION_KEY] == [str(app.pk)]
        record.assert_called_once()
        assert location.startswith(reverse("account_signup"))
        assert parse_qs(urlparse(location).query)["email"] == ["ada@example.com"]

    def test_anonymous_submit_redirects_to_signup_with_the_email_prefilled(
        self, client, mock_site_context
    ):
        course = CourseFactory()

        response = client.post(
            _apply_url(course), {"first_name": "Pat", "email": "pat@example.com"}
        )

        location = response["Location"]
        assert location.startswith(reverse("account_signup"))
        assert parse_qs(urlparse(location).query)["email"] == ["pat@example.com"]

    def test_anonymous_submit_carries_next(self, client, mock_site_context):
        course = CourseFactory()

        response = client.post(
            _apply_url(course), {"first_name": "Pat", "email": "pat@example.com"}
        )

        assert parse_qs(urlparse(response["Location"]).query)["next"] == [
            reverse("course_applications:claim")
        ]

    def test_anonymous_submit_on_closed_signup_site_redirects_to_login(
        self, client, mock_site_context, settings
    ):
        settings.ALLOW_SIGN_UPS = False
        course = CourseFactory()

        response = client.post(
            _apply_url(course), {"first_name": "Pat", "email": "pat@example.com"}
        )

        assert response["Location"].startswith(reverse("account_login"))

    def test_anonymous_submit_response_is_identical_for_registered_and_unregistered_email(
        self, client, mock_site_context
    ):
        course = CourseFactory()
        UserFactory(email="known@example.com")

        known = client.post(
            _apply_url(course), {"first_name": "Pat", "email": "known@example.com"}
        )
        unknown = Client().post(
            _apply_url(course), {"first_name": "Pat", "email": "stranger@example.com"}
        )

        assert known.status_code == unknown.status_code
        assert known["Location"].replace("known", "x") == unknown["Location"].replace(
            "stranger", "x"
        )

    def test_anonymous_apply_after_submit_redirects_to_handoff(
        self, client, mock_site_context
    ):
        course = CourseFactory()
        client.post(
            _apply_url(course), {"first_name": "Pat", "email": "pat@example.com"}
        )

        response = client.get(_apply_url(course))

        assert response.status_code == 302
        assert parse_qs(urlparse(response["Location"]).query)["email"] == [
            "pat@example.com"
        ]
        assert CourseApplication.objects.count() == 1

    def test_signed_in_apply_shows_the_account_email_read_only(
        self, client, mock_site_context
    ):
        user = UserFactory(email="me@example.com")
        client.force_login(user)
        course = CourseFactory()

        response = client.get(_apply_url(course))

        html = response.content.decode()
        assert "me@example.com" in html
        assert 'name="email"' not in html

    def test_signed_in_application_is_created_with_account_email(
        self, client, mock_site_context
    ):
        user = UserFactory(email="me@example.com")
        client.force_login(user)
        course = CourseFactory()

        client.post(_apply_url(course))

        assert CourseApplication.objects.get(user=user).email == "me@example.com"

    def test_signed_in_application_copies_account_names(
        self, client, mock_site_context
    ):
        user = UserFactory(first_name="Ada", last_name="Lovelace")
        client.force_login(user)
        course = CourseFactory()

        client.post(_apply_url(course))

        application = CourseApplication.objects.get(user=user)
        assert (application.first_name, application.last_name) == ("Ada", "Lovelace")

    @pytest.mark.parametrize(
        "view_name", ["apply", "about_you", "form_page", "check_answers"]
    )
    def test_every_unclaimed_application_view_sends_no_store_and_same_origin_referrer(
        self, client, mock_site_context, view_name
    ):
        course, form = gated_course_with_form()
        app = _start_anonymous_application(client, course, form)
        urls = {
            "apply": _apply_url(course),
            "about_you": _about_you_url(app),
            "form_page": _page_url(app, 1),
            "check_answers": _check_url(app),
        }

        response = client.get(urls[view_name])

        assert "no-store" in response["Cache-Control"]
        assert response["Referrer-Policy"] == "same-origin"


def _hold(client, *applications):
    session = client.session
    session[UNCLAIMED_APPLICATIONS_SESSION_KEY] = [str(a.pk) for a in applications]
    session.save()


def _claim_url():
    return reverse("course_applications:claim")


def _signed_in_with_verified(client, email="pat@example.com"):
    user = UserFactory()
    EmailAddressFactory(user=user, email=email)
    client.force_login(user)
    return user


@pytest.mark.django_db
class TestClaimLanding:
    def test_one_claimed_submitted_application_lands_on_its_status_page(
        self, client, mock_site_context
    ):
        user = _signed_in_with_verified(client)
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        _hold(client, app)

        response = client.get(_claim_url())

        app.refresh_from_db()
        assert app.user == user
        assert response["Location"] == reverse(
            "course_applications:status", kwargs={"pk": app.pk}
        )

    def test_claiming_says_the_application_is_on_the_dashboard(
        self, client, mock_site_context
    ):
        _signed_in_with_verified(client)
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        _hold(client, app)

        response = client.get(_claim_url())

        assert [str(m) for m in get_messages(response.wsgi_request)] == [
            f"Your application for {app.course.title} is now on your dashboard."
        ]

    def test_several_claimed_applications_land_on_the_dashboard(
        self, client, mock_site_context
    ):
        _signed_in_with_verified(client)
        first = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        second = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        _hold(client, first, second)

        response = client.get(_claim_url())

        assert response["Location"] == reverse("learner_interface:dashboard")

    def test_a_collision_alone_lands_on_the_existing_application(
        self, client, mock_site_context
    ):
        user = _signed_in_with_verified(client)
        course = CourseFactory()
        existing = CourseApplicationFactory(user=user, course=course)
        held = CourseApplicationFactory(
            unclaimed=True, course=course, email="pat@example.com"
        )
        _hold(client, held)

        response = client.get(_claim_url())

        assert response["Location"] == reverse(
            "course_applications:status", kwargs={"pk": existing.pk}
        )

    def test_a_collision_says_the_user_had_already_applied(
        self, client, mock_site_context
    ):
        user = _signed_in_with_verified(client)
        course = CourseFactory()
        CourseApplicationFactory(user=user, course=course)
        held = CourseApplicationFactory(
            unclaimed=True, course=course, email="pat@example.com"
        )
        _hold(client, held)

        response = client.get(_claim_url())

        assert [str(m) for m in get_messages(response.wsgi_request)] == [
            f"You had already applied to {course.title}. This is your application."
        ]

    def test_a_mismatch_shows_the_mismatch_page(self, client, mock_site_context):
        _signed_in_with_verified(client, email="other@example.com")
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        _hold(client, app)

        response = client.get(_claim_url())

        assert response.status_code == 200
        assert "pat@example.com" in response.content.decode()
        assert "Link your application" in response.content.decode()

    def test_a_mismatch_on_an_unverified_own_address_says_to_verify_it(
        self, client, mock_site_context
    ):
        user = UserFactory()
        EmailAddressFactory(user=user, email="pat@example.com", verified=False)
        client.force_login(user)
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        _hold(client, app)

        html = client.get(_claim_url()).content.decode()

        assert "has not been verified on this account yet" in html
        assert "Add and verify" not in html

    def test_a_mismatch_on_a_different_address_says_to_add_it(
        self, client, mock_site_context
    ):
        _signed_in_with_verified(client, email="other@example.com")
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        _hold(client, app)

        html = client.get(_claim_url()).content.decode()

        assert "Add and verify" in html
        assert "has not been verified" not in html

    def test_a_mismatch_leaves_the_application_unclaimed(
        self, client, mock_site_context
    ):
        _signed_in_with_verified(client, email="other@example.com")
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        _hold(client, app)

        client.get(_claim_url())

        app.refresh_from_db()
        assert app.user is None

    def test_nothing_held_says_no_application_was_found(
        self, client, mock_site_context
    ):
        _signed_in_with_verified(client)

        response = client.get(_claim_url())

        assert (
            response["Location"],
            [str(m) for m in get_messages(response.wsgi_request)],
        ) == (
            reverse("learner_interface:dashboard"),
            ["We couldn't find an application in this browser."],
        )

    def test_a_mismatch_mixed_with_a_claim_shows_the_mismatch_page(
        self, client, mock_site_context
    ):
        _signed_in_with_verified(client)
        claimable = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        mismatched = CourseApplicationFactory(unclaimed=True, email="else@example.com")
        _hold(client, claimable, mismatched)

        response = client.get(_claim_url())

        assert response.status_code == 200
        assert "else@example.com" in response.content.decode()

    def test_a_mixed_run_still_claims_the_matching_application(
        self, client, mock_site_context
    ):
        user = _signed_in_with_verified(client)
        claimable = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        mismatched = CourseApplicationFactory(unclaimed=True, email="else@example.com")
        _hold(client, claimable, mismatched)

        client.get(_claim_url())

        claimable.refresh_from_db()
        assert claimable.user == user

    def test_claim_landing_with_a_deleted_mismatched_application_finds_nothing(
        self, client, mock_site_context
    ):
        _signed_in_with_verified(client, email="other@example.com")
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        _hold(client, app)
        client.get(_claim_url())
        app.delete()

        response = client.get(_claim_url())

        assert response["Location"] == reverse("learner_interface:dashboard")

    def test_claim_landing_links_a_mismatched_application_once_the_address_is_verified(
        self, client, mock_site_context
    ):
        user = _signed_in_with_verified(client, email="other@example.com")
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        _hold(client, app)
        client.get(_claim_url())
        EmailAddressFactory(user=user, email="pat@example.com", primary=False)

        response = client.get(_claim_url())

        app.refresh_from_db()
        assert (app.user, response["Location"]) == (
            user,
            reverse("course_applications:status", kwargs={"pk": app.pk}),
        )

    def test_mismatch_page_offers_the_link_my_application_button(
        self, client, mock_site_context
    ):
        _signed_in_with_verified(client, email="other@example.com")
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        _hold(client, app)

        html = client.get(_claim_url()).content.decode()

        assert "Link my application" in html
        assert f'href="{_claim_url()}"' in html

    def test_claim_landing_is_login_required(self, client, mock_site_context):
        response = client.get(_claim_url())

        assert response.status_code == 302
        assert reverse("account_login") in response["Location"]

    def test_claim_landing_is_get_only(self, client, mock_site_context):
        _signed_in_with_verified(client)

        response = client.post(_claim_url())

        assert response.status_code == 405

    def test_claim_landing_revisit_finds_nothing(self, client, mock_site_context):
        _signed_in_with_verified(client)
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        _hold(client, app)
        client.get(_claim_url())

        response = client.get(_claim_url())

        assert response["Location"] == reverse("learner_interface:dashboard")

    def test_claim_landing_sends_no_store_and_same_origin_referrer(
        self, client, mock_site_context
    ):
        _signed_in_with_verified(client)

        response = client.get(_claim_url())

        assert "no-store" in response["Cache-Control"]
        assert response["Referrer-Policy"] == "same-origin"

    def test_claimed_application_appears_on_the_dashboard(
        self, client, mock_site_context
    ):
        _signed_in_with_verified(client)
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")
        _hold(client, app)
        client.get(_claim_url())

        response = client.get(reverse("learner_interface:dashboard"))

        assert app.course.title in response.content.decode()

    def test_handoff_message_is_shown_on_the_signup_page(
        self, client, mock_site_context
    ):
        course = CourseFactory()

        response = client.post(
            _apply_url(course),
            {"first_name": "Pat", "email": "pat@example.com"},
            follow=True,
        )

        assert (
            f"Your application for {course.title} has been sent."
            in response.content.decode()
        )


# ---------------------------------------------------------------------------
# The anonymous form journey
# ---------------------------------------------------------------------------


def _page_one_post(form, name="Ada"):
    """A valid page-1 POST body for the shared two-page form."""
    required = _questions_on(form, 1)[0]
    return {f"question_{required.id}": name}


ABOUT_YOU_DETAILS = {
    "first_name": "Ada",
    "last_name": "Lovelace",
    "email": "ada@example.com",
}


def _start_anonymous_application(client, course, form):
    """Take an anonymous visitor through About you and a valid page-1 save."""
    client.post(_apply_url(course), ABOUT_YOU_DETAILS)
    app = CourseApplication.objects.get(course=course)
    client.post(_page_url(app, 1), _page_one_post(form))
    return app


def _signed_in_holding_unclaimed_draft(client, form):
    """A signed-in browser whose session holds an unclaimed draft.

    Built directly because logging in claims an unsubmitted draft; what is
    left holding one is a submitted application whose address did not match.
    """
    from freedom_ls.form_engine.factories import FormProgressFactory

    sitting = FormProgressFactory(user=None, form=form)
    app = CourseApplicationFactory(
        unclaimed=True, form_progress=sitting, email="other@example.com"
    )
    client.force_login(UserFactory())
    session = client.session
    session[UNCLAIMED_APPLICATIONS_SESSION_KEY] = [str(app.pk)]
    session[ANONYMOUS_SITTINGS_SESSION_KEY] = [str(sitting.pk)]
    session.save()
    return app


def _complete_anonymous_application(client, course, form):
    """An anonymous applicant with page 1 saved, ready to submit from page 2."""
    app = _start_anonymous_application(client, course, form)
    client.post(_page_url(app, 2), {})
    return app


def _form_course():
    return gated_course_with_form()[0]


COURSE_KINDS = pytest.mark.parametrize(
    "make_course",
    [_form_course, CourseFactory],
    ids=["form_course", "no_form_course"],
)


def _course_with_file_on_page_one(*, required: bool):
    form = FormFactory(strategy=FormStrategy.UNSCORED)
    page = FormPageFactory(form=form, order=0)
    FormQuestionFactory(
        form_page=page, type="short_text", order=0, question="Name", required=True
    )
    FormQuestionFactory(
        form_page=page, type="file_upload", order=1, question="ID", required=required
    )
    course = CourseFactory(access_config={"access_type": "application_gated"})
    course.application_form = form
    course.save(update_fields=["application_form"])
    return course, form


@pytest.mark.django_db
class TestAnonymousFormJourney:
    def test_anonymous_apply_renders_about_you_without_creating_rows(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()

        response = client.get(_apply_url(course))

        body = response.content.decode()
        assert response.status_code == 200
        assert "<h1>About you</h1>" in body
        assert "kept until an administrator removes it" in body
        assert (CourseApplication.objects.count(), FormProgress.objects.count()) == (
            0,
            0,
        )

    def test_about_you_post_creates_application_and_sitting_and_remembers_them(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()

        response = client.post(
            _apply_url(course), {**ABOUT_YOU_DETAILS, "email": "Ada@Example.com"}
        )

        app = CourseApplication.objects.get(course=course)
        assert (app.user, app.first_name, app.last_name, app.email) == (
            None,
            "Ada",
            "Lovelace",
            "ada@example.com",
        )
        assert (app.form_progress.user, FormProgress.objects.count()) == (None, 1)
        assert client.session[UNCLAIMED_APPLICATIONS_SESSION_KEY] == [str(app.pk)]
        assert client.session[ANONYMOUS_SITTINGS_SESSION_KEY] == [
            str(app.form_progress_id)
        ]
        assert response["Location"] == _page_url(app, 1)

    @COURSE_KINDS
    def test_about_you_post_with_errors_creates_nothing_and_keeps_typed_values(
        self, client, mock_site_context, make_course
    ):
        course = make_course()

        response = client.post(
            _apply_url(course), {"first_name": "Ada", "last_name": "Lovelace"}
        )

        assert response.status_code == 422
        assert "Lovelace" in response.content.decode()
        assert (CourseApplication.objects.count(), FormProgress.objects.count()) == (
            0,
            0,
        )

    @pytest.mark.parametrize(
        ("require_name", "status", "label"),
        [(True, 422, "First name"), (False, 302, "First name (optional)")],
    )
    def test_about_you_first_name_required_follows_signup_policy(
        self, client, mock_site_context, require_name, status, label
    ):
        SiteSignupPolicyFactory(require_name=require_name)
        course, _form = gated_course_with_form()

        response = client.post(
            _apply_url(course), {"first_name": "", "email": "ada@example.com"}
        )
        page = Client().get(_apply_url(course))

        assert response.status_code == status
        assert f">{label}" in page.content.decode()

    def test_about_you_on_a_form_with_no_pages_leads_to_check_answers(
        self, client, mock_site_context
    ):
        course = _gated_course_with_a_page_less_form()

        response = client.post(_apply_url(course), ABOUT_YOU_DETAILS)

        app = CourseApplication.objects.get(course=course)
        assert response["Location"] == _check_url(app)

    @COURSE_KINDS
    def test_start_cap_counts_only_valid_about_you_posts(
        self, settings, mock_site_context, make_course
    ):
        settings.TRUSTED_PROXY_IP_HEADER = None
        settings.COURSE_APPLICATIONS_ANONYMOUS_START_LIMIT = 1
        settings.COURSE_APPLICATIONS_ANONYMOUS_START_WINDOW_SECONDS = 600
        course = make_course()
        refused = Client().post(_apply_url(course), {"first_name": "Ada"})
        accepted = Client().post(_apply_url(course), ABOUT_YOU_DETAILS)

        capped = Client().post(_apply_url(course), ABOUT_YOU_DETAILS)

        assert (refused.status_code, accepted.status_code) == (422, 302)
        assert capped.status_code == 429
        assert CourseApplication.objects.count() == 1

    @COURSE_KINDS
    def test_honeypot_on_about_you_creates_nothing(
        self, client, mock_site_context, make_course
    ):
        course = make_course()

        response = client.post(
            _apply_url(course), {**ABOUT_YOU_DETAILS, "fax_number": "bot"}
        )

        assert response.status_code == 422
        assert "We couldn&#x27;t process this application" in response.content.decode()
        assert not CourseApplication.objects.exists()

    def test_about_you_fields_use_the_question_field_markup(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()

        html = client.post(_apply_url(course), {"first_name": "Ada"}).content.decode()

        assert html.count("<fieldset") >= 3
        assert html.count("<legend") >= 3
        assert 'aria-invalid="true"' in html
        assert 'aria-describedby="id_email_error"' in html
        assert 'id="id_email_error"' in html

    def test_about_you_nav_lists_about_you_first_and_numbers_pages_from_two(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()

        before = client.get(_apply_url(course)).context["page_links"]
        app = _start_anonymous_application(client, course, form)
        after = client.get(_page_url(app, 1)).context["page_links"]

        assert [
            (link.number, link.title, link.is_current, link.is_accessible)
            for link in before
        ] == [
            (1, "About you", True, True),
            (2, "Your background", False, False),
            (3, "Supporting documents", False, False),
        ]
        assert [
            (link.number, link.is_current, link.is_accessible) for link in after[:2]
        ] == [
            (1, False, True),
            (2, True, True),
        ]

    def test_form_page_one_previous_links_to_about_you_for_an_unclaimed_application(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _start_anonymous_application(client, course, form)

        response = client.get(_page_url(app, 1))

        assert response.context["previous_page_url"] == _about_you_url(app)

    def test_anonymous_apply_resumes_the_session_draft(self, client, mock_site_context):
        course, form = gated_course_with_form()
        app = _start_anonymous_application(client, course, form)
        client.get(_page_url(app, 2))

        response = client.get(_apply_url(course))

        assert response["Location"] == _page_url(app, 2)

    def test_anonymous_apply_get_does_not_write_the_session(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()

        client.get(_apply_url(course))

        assert ANONYMOUS_SITTINGS_SESSION_KEY not in client.session

    def test_foreign_application_id_is_404_for_anonymous_request(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _start_anonymous_application(client, course, form)

        response = Client().get(_page_url(app, 1))

        assert response.status_code == 404

    def test_expired_session_is_404(self, client, mock_site_context):
        course, form = gated_course_with_form()
        app = _start_anonymous_application(client, course, form)
        client.cookies.clear()

        response = client.get(_page_url(app, 1))

        assert response.status_code == 404

    def test_session_held_id_from_another_site_is_404(self, client, mock_site_context):
        from freedom_ls.accounts.factories import SiteFactory
        from freedom_ls.form_engine.factories import FormProgressFactory

        sitting = FormProgressFactory(user=None, site=SiteFactory())
        app = CourseApplicationFactory(
            unclaimed=True, form_progress=sitting, site=sitting.site
        )
        _hold(client, app)

        response = client.get(_page_url(app, 1))

        assert response.status_code == 404

    def test_session_held_id_of_a_claimed_application_is_404(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _start_anonymous_application(client, course, form)
        app.user = UserFactory()
        app.save(update_fields=["user"])

        response = client.get(_page_url(app, 1))

        assert response.status_code == 404

    def test_submitted_unclaimed_check_answers_post_redirects_to_handoff(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _complete_anonymous_application(client, course, form)
        client.post(_check_url(app), {})

        response = client.post(_check_url(app))

        assert response["Location"].startswith(reverse("account_signup"))

    def test_submitted_unclaimed_check_answers_links_back_to_the_handoff(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _complete_anonymous_application(client, course, form)
        client.post(_check_url(app), {})

        html = client.get(_check_url(app)).content.decode()

        assert f'href="{_apply_url(course)}"' in html
        assert reverse("course_applications:status", kwargs={"pk": app.pk}) not in html

    def test_signed_in_user_reads_a_session_held_unclaimed_application(
        self, client, mock_site_context
    ):
        _course, form = gated_course_with_form()
        app = _signed_in_holding_unclaimed_draft(client, form)

        response = client.get(_page_url(app, 1))

        assert response.status_code == 200

    def test_signed_in_user_on_a_session_held_draft_sees_the_about_you_card(
        self, client, mock_site_context
    ):
        _course, form = gated_course_with_form()
        app = _signed_in_holding_unclaimed_draft(client, form)

        html = client.get(_check_url(app)).content.decode()

        assert "other@example.com" in html

    def test_check_answers_shows_about_you_card(self, client, mock_site_context):
        course, form = gated_course_with_form()
        app = _start_anonymous_application(client, course, form)

        html = client.get(_check_url(app)).content.decode()

        assert "Ada Lovelace" in html
        assert "ada@example.com" in html
        assert f"{_about_you_url(app)}?return=check" in html

    def test_check_answers_has_no_email_field(self, client, mock_site_context):
        course, form = gated_course_with_form()
        app = _start_anonymous_application(client, course, form)

        html = client.get(_check_url(app)).content.decode()

        assert 'name="email"' not in html

    def test_anonymous_submit_hands_off_without_reading_an_email(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _complete_anonymous_application(client, course, form)

        with patch(
            "freedom_ls.course_applications.views.record_application_submitted"
        ) as record:
            response = client.post(_check_url(app), {})

        app.form_progress.refresh_from_db()
        query = parse_qs(urlparse(response["Location"]).query)
        assert app.form_progress.completed_time is not None
        record.assert_called_once()
        assert (urlparse(response["Location"]).path, query["email"]) == (
            reverse("account_signup"),
            ["ada@example.com"],
        )

    def test_anonymous_submit_runs_the_whole_form_check(
        self, client, mock_site_context
    ):
        course, form = _course_with_file_on_page_one(required=True)
        client.post(_apply_url(course), ABOUT_YOU_DETAILS)
        app = CourseApplication.objects.get(course=course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})

        response = client.post(_check_url(app), {})

        assert response.status_code == 422
        assert "needs an answer" in response.content.decode()

    def test_anonymous_submit_completes_the_sitting(self, client, mock_site_context):
        course, form = gated_course_with_form()
        app = _complete_anonymous_application(client, course, form)

        client.post(_check_url(app), {})

        app.form_progress.refresh_from_db()
        assert app.form_progress.completed_time is not None

    def test_anonymous_submit_records_the_event(self, client, mock_site_context):
        course, form = gated_course_with_form()
        app = _complete_anonymous_application(client, course, form)

        with patch(
            "freedom_ls.course_applications.views.record_application_submitted"
        ) as record:
            client.post(_check_url(app), {})

        record.assert_called_once()

    def test_anonymous_submit_from_check_answers_hands_off(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _complete_anonymous_application(client, course, form)

        response = client.post(_check_url(app), {})

        query = parse_qs(urlparse(response["Location"]).query)
        assert (urlparse(response["Location"]).path, query["email"]) == (
            reverse("account_signup"),
            ["ada@example.com"],
        )

    def test_signed_in_check_answers_shows_about_you_card_without_edit_link(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        html = client.get(_check_url(app)).content.decode()

        assert app.user.email in html
        assert _about_you_url(app) not in html

    def test_unclaimed_form_pages_carry_the_browser_only_notice(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _start_anonymous_application(client, course, form)

        pages = [client.get(_page_url(app, 1)), client.get(_check_url(app))]

        assert all("saved in this browser only" in r.content.decode() for r in pages)

    def test_claimed_form_pages_carry_no_browser_only_notice(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        pages = [client.get(_page_url(app, 1)), client.get(_check_url(app))]

        assert all(
            "saved in this browser only" not in r.content.decode() for r in pages
        )

    def test_submitted_unclaimed_pages_no_longer_ask_to_submit(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _complete_anonymous_application(client, course, form)
        client.post(_check_url(app), {})

        pages = [client.get(_page_url(app, 1)), client.get(_check_url(app))]

        assert all("Submit it to keep it" not in r.content.decode() for r in pages)

    def test_browser_only_notice_names_the_session_lifetime(
        self, client, mock_site_context, settings
    ):
        settings.SESSION_EXPIRE_AT_BROWSER_CLOSE = False
        settings.SESSION_COOKIE_AGE = 8 * 3600
        course, form = gated_course_with_form()
        app = _start_anonymous_application(client, course, form)

        html = client.get(_page_url(app, 1)).content.decode()

        assert "for up to 8\xa0hours" in html

    def test_browser_only_notice_for_a_session_that_ends_with_the_browser(
        self, client, mock_site_context, settings
    ):
        settings.SESSION_EXPIRE_AT_BROWSER_CLOSE = True
        course, form = gated_course_with_form()
        app = _start_anonymous_application(client, course, form)

        html = client.get(_check_url(app)).content.decode()

        assert "until you close your browser" in html
        assert "for up to" not in html


@pytest.mark.django_db
class TestAboutYouRevisit:
    def test_about_you_edit_saves_and_returns_to_page_one(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _start_anonymous_application(client, course, form)

        response = client.post(
            _about_you_url(app), {**ABOUT_YOU_DETAILS, "first_name": "Augusta"}
        )

        app.refresh_from_db()
        assert app.first_name == "Augusta"
        assert response["Location"] == _page_url(app, 1)

    def test_about_you_edit_with_return_marker_goes_to_check_answers(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _start_anonymous_application(client, course, form)

        response = client.post(f"{_about_you_url(app)}?return=check", ABOUT_YOU_DETAILS)

        assert response["Location"] == _check_url(app)

    def test_about_you_is_read_only_once_submitted(self, client, mock_site_context):
        course, form = gated_course_with_form()
        app = _complete_anonymous_application(client, course, form)
        client.post(_check_url(app), {})

        html = client.get(_about_you_url(app)).content.decode()

        assert 'id="id_email"' in html
        assert "disabled" in html
        assert 'type="submit"' not in html

    def test_about_you_redirects_once_claimed(self, client, mock_site_context):
        course, form = gated_course_with_form()
        app = _start_anonymous_application(client, course, form)
        app.user = UserFactory()
        app.save(update_fields=["user"])
        client.force_login(app.user)

        response = client.get(_about_you_url(app))

        assert response.status_code == 302

    def test_about_you_without_the_application_in_session_is_404(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _start_anonymous_application(client, course, form)

        response = Client().get(_about_you_url(app))

        assert response.status_code == 404


@pytest.mark.django_db
class TestClaimLandingResumesDraft:
    def test_claim_landing_with_one_claimed_draft_resumes_it(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _start_anonymous_application(client, course, form)
        client.get(_page_url(app, 2))
        client.force_login(UserFactory())

        response = client.get(_claim_url())

        assert response["Location"] == _page_url(app, 2)


@pytest.mark.django_db
class TestSignedInApplyWithAHeldApplication:
    """Apply never starts a second application while the browser holds one."""

    def test_a_mismatched_submitted_application_sends_apply_to_the_claim_landing(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _complete_anonymous_application(client, course, form)
        client.post(_check_url(app), {})
        _signed_in_with_verified(client, email="other@example.com")

        response = client.get(_apply_url(course))

        assert response["Location"] == _claim_url()
        assert CourseApplication.objects.filter(course=course).count() == 1

    def test_a_held_draft_is_claimed_and_resumed(self, client, mock_site_context):
        from freedom_ls.form_engine.factories import FormProgressFactory

        course, form = gated_course_with_form()
        sitting = FormProgressFactory(user=None, form=form)
        app = CourseApplicationFactory(
            unclaimed=True, email="", course=course, form_progress=sitting
        )
        client.force_login(UserFactory())
        _hold(client, app)

        response = client.get(_apply_url(course), follow=True)

        app.refresh_from_db()
        assert app.user is not None
        assert response.redirect_chain[-1][0] == _page_url(app, 1)
        assert CourseApplication.objects.filter(course=course).count() == 1


# ---------------------------------------------------------------------------
# Per-address caps and the honeypot on the anonymous apply
# ---------------------------------------------------------------------------


def _post_application(course, email: str = "pat@example.com", **extra: str):
    """One anonymous no-form application POST from a browser of its own."""
    return Client().post(
        _apply_url(course), {"first_name": "Pat", "email": email, **extra}
    )


@pytest.mark.django_db
class TestAnonymousStartCap:
    @pytest.fixture(autouse=True)
    def _capped(self, settings, mock_site_context) -> None:
        settings.TRUSTED_PROXY_IP_HEADER = None
        settings.COURSE_APPLICATIONS_ANONYMOUS_START_LIMIT = 1
        settings.COURSE_APPLICATIONS_ANONYMOUS_START_WINDOW_SECONDS = 600

    def test_start_cap_fires_with_429(self):
        course = CourseFactory()
        _post_application(course, "a@example.com")

        response = _post_application(course, "b@example.com")

        assert response.status_code == 429

    def test_start_cap_sets_retry_after(self, settings):
        course = CourseFactory()
        _post_application(course, "a@example.com")

        response = _post_application(course, "b@example.com")

        assert response["Retry-After"] == str(
            settings.COURSE_APPLICATIONS_ANONYMOUS_START_WINDOW_SECONDS
        )

    def test_start_cap_zero_disables(self, settings):
        settings.COURSE_APPLICATIONS_ANONYMOUS_START_LIMIT = 0
        course = CourseFactory()
        _post_application(course, "a@example.com")

        response = _post_application(course, "b@example.com")

        assert response.status_code == 302

    def test_start_cap_key_holds_no_raw_ip(self):
        from django.core.cache import cache

        course = CourseFactory()

        Client().post(
            _apply_url(course),
            {"first_name": "Pat", "email": "a@example.com"},
            REMOTE_ADDR="203.0.113.7",
        )

        assert cache._cache
        assert not [key for key in cache._cache if "203.0.113.7" in key]

    def test_start_cap_broken_cache_fails_open(self, mocker):
        mocker.patch(
            "freedom_ls.accounts.throttling.cache.add",
            side_effect=ConnectionError("no cache"),
        )
        mocker.patch("freedom_ls.accounts.throttling.sentry_sdk")
        course = CourseFactory()
        _post_application(course, "a@example.com")

        response = _post_application(course, "b@example.com")

        assert response.status_code == 302

    def test_start_cap_missing_proxy_header_is_forbidden(self, settings):
        settings.TRUSTED_PROXY_IP_HEADER = "X-Real-IP"
        course = CourseFactory()

        response = _post_application(course)

        assert response.status_code == 403

    def test_start_cap_ignores_signed_in_requests(self, client):
        course = CourseFactory()
        client.force_login(UserFactory())
        _post_application(course, "a@example.com")

        response = client.post(_apply_url(course))

        assert response.status_code != 429

    def test_start_cap_ignores_gets(self):
        course = CourseFactory()
        _post_application(course, "a@example.com")

        response = Client().get(_apply_url(course))

        assert response.status_code == 200

    def test_start_cap_creates_nothing_when_it_fires(self):
        course = CourseFactory()
        _post_application(course, "a@example.com")

        _post_application(course, "b@example.com")

        assert CourseApplication.objects.count() == 1
