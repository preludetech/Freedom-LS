"""Erasing an anonymous applicant takes the application, sitting and files too."""

from __future__ import annotations

from typing import cast

import pytest

from freedom_ls.course_applications.erasure import erase_anonymous_applicant
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import AnonymousApplicant, CourseApplication
from freedom_ls.course_applications.tests.helpers import (
    unverified_application_with_file,
)
from freedom_ls.form_engine.models import FormProgress, QuestionAnswerFile

pytestmark = pytest.mark.django_db


def test_erasing_an_applicant_whose_application_has_no_sitting(mock_site_context):
    application = cast(CourseApplication, CourseApplicationFactory(anonymous=True))
    applicant = AnonymousApplicant.objects.get(pk=application.anonymous_applicant_id)

    erase_anonymous_applicant(applicant)

    assert not AnonymousApplicant.objects.filter(pk=applicant.pk).exists()
    assert not CourseApplication.objects.filter(pk=application.pk).exists()


def test_erasing_an_applicant_removes_the_sitting(mock_site_context):
    unverified = unverified_application_with_file()

    erase_anonymous_applicant(unverified.applicant)

    assert not FormProgress.objects.filter(pk=unverified.sitting.pk).exists()


def test_erasing_an_applicant_removes_the_answer_file_row_and_stored_object(
    mock_site_context,
):
    unverified = unverified_application_with_file()
    answer_file = QuestionAnswerFile.objects.get(
        answer__form_progress=unverified.sitting
    )
    storage, name = answer_file.file.storage, answer_file.file.name

    erase_anonymous_applicant(unverified.applicant)

    assert not QuestionAnswerFile.objects.filter(pk=answer_file.pk).exists()
    assert not storage.exists(name)
