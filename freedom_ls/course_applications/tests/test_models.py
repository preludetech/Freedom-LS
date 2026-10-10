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

from freedom_ls.course_applications.factories import CourseApplicationFactory
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
class TestUnclaimedApplication:
    def test_unclaimed_rows_are_not_deduplicated_by_the_unique_constraint(
        self, mock_site_context
    ):
        course = CourseFactory()
        CourseApplicationFactory(unclaimed=True, course=course)
        CourseApplicationFactory(unclaimed=True, course=course)

        assert CourseApplication.objects.filter(course=course).count() == 2

    def test_is_claimed_is_false_without_a_user(self, mock_site_context):
        assert CourseApplicationFactory(unclaimed=True).is_claimed is False

    def test_is_claimed_is_true_with_a_user(self, mock_site_context):
        assert CourseApplicationFactory().is_claimed is True

    def test_str_prints_the_email_of_an_unclaimed_row(self, mock_site_context):
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")

        assert "pat@example.com" in str(app)

    def test_a_no_form_unclaimed_row_is_submitted(self, mock_site_context):
        assert CourseApplicationFactory(unclaimed=True).is_submitted is True


@pytest.mark.parametrize(
    ("first_name", "last_name", "expected"),
    [("Ada", "Lovelace", "Ada Lovelace"), ("Ada", "", "Ada"), ("", "", "")],
)
def test_full_name_joins_the_names_it_has(first_name, last_name, expected):
    application = CourseApplication(first_name=first_name, last_name=last_name)

    assert application.full_name == expected
