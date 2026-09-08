"""Tests for course_applications views."""

from __future__ import annotations

import pytest

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.tests.app_guards import app_not_installed
from freedom_ls.tests.images import png_bytes

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.form_engine.queries import page_questions
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_progress.models import CourseFormAttempt

from .conftest import gated_course_with_form

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

    def test_get_unauthenticated_redirects_to_login(self, client, mock_site_context):
        """GET apply without login redirects to login with next set to the apply URL."""
        course = CourseFactory()
        url = reverse("course_applications:apply", kwargs={"course_slug": course.slug})
        response = client.get(url)

        assert response.status_code == 302
        assert response["Location"] == f"{reverse('account_login')}?next={url}"

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

    def test_applying_to_a_course_with_a_form_records_the_form(
        self, client, mock_site_context
    ):
        """Kept on the application itself, so re-pointing the course later does
        not rewrite what an existing applicant was asked.
        """
        course, form = gated_course_with_form()

        app = _applied(client, course)

        assert app.form == form

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


@pytest.mark.django_db
class TestApplicationFormPage:
    def test_the_owner_sees_page_one(self, client, mock_site_context):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        response = client.get(_page_url(app, 1))

        assert response.status_code == 200

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

        body = client.get(_edit_url(app, 1)).content.decode()

        assert "Save and return to your answers" in body
        assert "Back to your answers" in body

    def test_a_page_reached_normally_offers_no_return_button(
        self, client, mock_site_context
    ):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        body = client.get(_page_url(app, 1)).content.decode()

        assert "Save and return to your answers" not in body

    def test_a_refused_page_keeps_the_return_marker(self, client, mock_site_context):
        course, _form = gated_course_with_form()
        app = _applied(client, course)

        response = client.post(_edit_url(app, 1), {})

        assert response.status_code == 422
        assert "Save and return to your answers" in response.content.decode()

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

    def test_submitting_redirects_to_the_status_page(self, client, mock_site_context):
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})

        response = client.post(_check_url(app))

        assert response["Location"] == reverse(
            "course_applications:status", kwargs={"pk": app.pk}
        )

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

        body = client.get(_check_url(app)).content.decode()

        assert "Submit application" in body

    def test_a_submitted_application_cannot_be_submitted_again(
        self, client, mock_site_context
    ):
        course, form = gated_course_with_form()
        app = _applied(client, course)
        name = _questions_on(form, 1)[0]
        client.post(_page_url(app, 1), {f"question_{name.id}": "Ada"})
        client.post(_check_url(app))

        body = client.get(_check_url(app)).content.decode()

        assert "Submit application" not in body

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
