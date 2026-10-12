"""Tests for the CourseApplication model."""

from __future__ import annotations

import pytest

from django.db import IntegrityError
from django.db.models import ProtectedError, RestrictedError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.form_engine.factories import FormFactory, FormProgressFactory
from freedom_ls.form_engine.models import FormProgress, FormStrategy
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.factories import (
    AnonymousApplicantFactory,
    CourseApplicationFactory,
)
from freedom_ls.course_applications.models import CourseApplication


@pytest.mark.django_db
class TestCourseApplicationUniqueConstraint:
    """Unique constraint per (site, user, course)."""

    def test_second_application_same_site_user_course_raises_integrity_error(
        self, mock_site_context
    ):
        """A second CourseApplication for the same (site, user, course) must raise IntegrityError."""
        user = UserFactory()
        course = CourseFactory()
        CourseApplicationFactory(user=user, course=course)

        with pytest.raises(IntegrityError):
            CourseApplicationFactory(user=user, course=course)

    def test_a_claimed_application_counts_as_the_users_one_for_the_course(
        self, mock_site_context
    ):
        """How the application began makes no difference to the constraint."""
        user = UserFactory()
        course = CourseFactory()
        CourseApplicationFactory(user=user, course=course)

        with pytest.raises(IntegrityError):
            CourseApplicationFactory(anonymous=True, user=user, course=course)

    def test_unverified_applications_never_collide(self, mock_site_context):
        """Two visitors applying to one course have no user to collide on."""
        course = CourseFactory()
        first = CourseApplicationFactory(anonymous=True, course=course)
        second = CourseApplicationFactory(anonymous=True, course=course)

        assert first.pk != second.pk

    def test_different_users_can_apply_to_same_course(self, mock_site_context):
        """Different users may each have one application for the same course."""
        course = CourseFactory()
        user_a = UserFactory()
        user_b = UserFactory()
        app_a = CourseApplicationFactory(user=user_a, course=course)
        app_b = CourseApplicationFactory(user=user_b, course=course)
        assert app_a.pk != app_b.pk

    def test_same_user_can_apply_to_different_courses(self, mock_site_context):
        """The same user may have one application per course (not a global unique)."""
        user = UserFactory()
        course_a = CourseFactory()
        course_b = CourseFactory()
        app_a = CourseApplicationFactory(user=user, course=course_a)
        app_b = CourseApplicationFactory(user=user, course=course_b)
        assert app_a.pk != app_b.pk


@pytest.mark.django_db
class TestCourseApplicationSitting:
    """The applicant's sitting of the form, and what may delete it."""

    def test_an_application_needs_no_sitting(self, mock_site_context):
        """A course with no application form still takes applications."""
        app = CourseApplicationFactory()

        assert app.form_progress is None

    def test_a_sitting_with_an_application_cannot_be_deleted(self, mock_site_context):
        """The sitting is the only record of what this applicant was asked, so
        it cannot go while the application stands.
        """
        form_progress = FormProgressFactory(
            form=FormFactory(strategy=FormStrategy.UNSCORED)
        )
        CourseApplicationFactory(form_progress=form_progress)

        with pytest.raises(RestrictedError):
            form_progress.delete()

    def test_deleting_the_applicant_takes_the_application_and_the_sitting(
        self, mock_site_context
    ):
        """RESTRICT rather than PROTECT, so erasing someone still works: both
        rows cascade off the user in one operation.
        """
        user = UserFactory()
        form_progress = FormProgressFactory(
            user=user, form=FormFactory(strategy=FormStrategy.UNSCORED)
        )
        app = CourseApplicationFactory(user=user, form_progress=form_progress)

        user.delete()

        assert not CourseApplication.objects.filter(pk=app.pk).exists()
        assert not FormProgress.objects.filter(pk=form_progress.pk).exists()

    def test_a_form_behind_an_application_cannot_be_deleted(self, mock_site_context):
        """Deleting the form would leave applications with no record of what was
        asked of the people who filled it in. FormProgress.form carries this.
        """
        form = FormFactory(strategy=FormStrategy.UNSCORED)
        CourseApplicationFactory(form_progress=FormProgressFactory(form=form))

        with pytest.raises(ProtectedError):
            form.delete()


@pytest.mark.django_db
class TestIsSubmitted:
    """Draft versus submitted is the sitting's completed_time."""

    def test_an_application_with_no_sitting_is_submitted(self, mock_site_context):
        assert CourseApplicationFactory().is_submitted is True

    def test_an_open_sitting_is_a_draft(self, mock_site_context):
        user = UserFactory()
        form = FormFactory(strategy=FormStrategy.UNSCORED)
        app = CourseApplicationFactory(
            user=user, form_progress=FormProgressFactory(user=user, form=form)
        )

        assert app.is_submitted is False

    def test_a_completed_sitting_is_submitted(self, mock_site_context):
        user = UserFactory()
        form = FormFactory(strategy=FormStrategy.UNSCORED)
        app = CourseApplicationFactory(
            user=user, form_progress=FormProgressFactory(user=user, form=form)
        )
        app.form_progress.complete()

        assert app.is_submitted is True


@pytest.mark.django_db
class TestAnonymousApplications:
    def test_signed_in_application_is_email_verified(self, mock_site_context):
        assert CourseApplicationFactory().is_email_verified is True

    def test_anonymous_application_is_not_email_verified(self, mock_site_context):
        assert CourseApplicationFactory(anonymous=True).is_email_verified is False

    def test_anonymous_application_reports_the_applicants_email(
        self, mock_site_context
    ):
        application = CourseApplicationFactory(anonymous=True)

        assert application.applicant_email == application.anonymous_applicant.email

    def test_signed_in_application_reports_the_users_email(self, mock_site_context):
        application = CourseApplicationFactory()

        assert application.applicant_email == application.user.email

    def test_anonymous_application_reports_the_applicants_name(self, mock_site_context):
        application = CourseApplicationFactory(anonymous=True)
        applicant = application.anonymous_applicant

        assert (
            application.applicant_name
            == f"{applicant.first_name} {applicant.last_name}"
        )

    def test_signed_in_application_reports_the_users_name(self, mock_site_context):
        application = CourseApplicationFactory()
        user = application.user

        assert (
            application.applicant_name == f"{user.first_name} {user.last_name}".strip()
        )

    def test_two_anonymous_applications_for_one_course_coexist(self, mock_site_context):
        course = CourseFactory()
        CourseApplicationFactory(course=course, anonymous=True)
        CourseApplicationFactory(course=course, anonymous=True)

        assert CourseApplication.objects.filter(course=course).count() == 2

    def test_deleting_an_applicant_removes_its_application(self, mock_site_context):
        application = CourseApplicationFactory(anonymous=True)

        application.anonymous_applicant.delete()

        assert not CourseApplication.objects.filter(pk=application.pk).exists()


@pytest.mark.django_db
def test_an_anonymous_applicants_label_leaves_out_the_address(mock_site_context):
    applicant = AnonymousApplicantFactory(email="secret@example.com")

    assert "secret@example.com" not in str(applicant)


@pytest.mark.django_db
def test_an_unclaimed_applications_label_names_the_applicant_not_none(
    mock_site_context,
):
    """An unclaimed application's label printed `None` where the user belongs."""
    application = CourseApplicationFactory(anonymous=True)

    assert str(application) == (
        f"CourseApplication(anonymous {application.anonymous_applicant_id}, "
        f"{application.course_id})"
    )
