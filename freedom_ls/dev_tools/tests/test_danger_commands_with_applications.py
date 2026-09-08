"""The bulk-delete commands against a course application's RESTRICTed sitting."""

from __future__ import annotations

import pytest

from django.core.management import call_command

from freedom_ls.form_engine.factories import FormProgressFactory
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import CourseApplication

pytestmark = pytest.mark.django_db


@pytest.fixture
def application_with_a_sitting(mock_site_context) -> CourseApplication:
    """An applicant part-way through a form, as the danger commands find them."""
    application: CourseApplication = CourseApplicationFactory.create(
        form_progress=FormProgressFactory()
    )
    return application


def test_clear_all_course_progress_takes_the_application_with_the_sitting(
    application_with_a_sitting,
):
    """The application RESTRICTs its sitting, so it has to go first or the
    whole command fails.
    """
    call_command("danger_clear_all_course_progress", "--yes")

    assert FormProgress.objects.count() == 0
    assert CourseApplication.objects.count() == 0


def test_content_delete_takes_the_application_with_the_sitting(
    application_with_a_sitting,
):
    call_command("danger_content_delete", "--yes")

    assert FormProgress.objects.count() == 0
    assert CourseApplication.objects.count() == 0
