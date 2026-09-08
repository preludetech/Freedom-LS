"""Tests for the CourseApplication model."""

from __future__ import annotations

import pytest

from django.db import IntegrityError
from django.db.models import ProtectedError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.form_engine.factories import FormFactory, FormProgressFactory
from freedom_ls.form_engine.models import FormStrategy
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.factories import CourseApplicationFactory


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
class TestCourseApplicationFormFields:
    """The form the application was made against, and the applicant's sitting."""

    def test_an_application_needs_neither_a_form_nor_a_sitting(self, mock_site_context):
        """A course with no application form still takes applications."""
        app = CourseApplicationFactory()

        assert app.form is None

    def test_deleting_a_sitting_keeps_the_application(self, mock_site_context):
        """The application is the record of the request. Losing the answers must
        not lose the fact that someone applied.
        """
        form = FormFactory(strategy=FormStrategy.UNSCORED)
        form_progress = FormProgressFactory(form=form)
        app = CourseApplicationFactory(form=form, form_progress=form_progress)

        form_progress.delete()

        app.refresh_from_db()
        assert app.form_progress is None

    def test_a_form_with_applications_cannot_be_deleted(self, mock_site_context):
        """Deleting the form would leave applications with no record of what was
        asked of the people who filled it in.
        """
        form = FormFactory(strategy=FormStrategy.UNSCORED)
        CourseApplicationFactory(form=form)

        with pytest.raises(ProtectedError):
            form.delete()
