"""The seeded bulk application sittings are finished the way a real submission is."""

from __future__ import annotations

from typing import cast

import pytest

from django.conf import settings

if "freedom_ls.qa_helpers" not in settings.INSTALLED_APPS:  # pragma: no cover
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.course_applications.transitions import reject_application
from freedom_ls.form_engine.enums import QuestionType
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
)
from freedom_ls.form_engine.models import FormQuestion
from freedom_ls.qa_helpers.management.commands.qa_create_bulk_applications import (
    _ensure_application,
)

pytestmark = pytest.mark.dev_tooling


@pytest.mark.django_db
def test_the_completed_sitting_records_the_questions_it_was_asked(mock_site_context):
    form = FormFactory()
    page = FormPageFactory(form=form, order=1)
    question = cast(
        FormQuestion,
        FormQuestionFactory(form_page=page, type=QuestionType.SHORT_TEXT, order=1),
    )
    course = CourseFactory(application_form=form)
    user = UserFactory()

    application = _ensure_application(
        mock_site_context, user, course, [(question, "Bulk Applicant 01")]
    )
    rerun = _ensure_application(
        mock_site_context, user, course, [(question, "Bulk Applicant 01")]
    )

    sitting = application.form_progress
    assert sitting is not None
    assert application.is_submitted
    assert sitting.furthest_page == course.application_form.pages.first()
    assert sitting.asked
    assert sitting.answers.count() == 1
    assert rerun.pk == application.pk


@pytest.mark.django_db
def test_a_rerun_after_a_rejection_submits_a_new_application(mock_site_context):
    form = FormFactory()
    page = FormPageFactory(form=form, order=1)
    question = cast(
        FormQuestion,
        FormQuestionFactory(form_page=page, type=QuestionType.SHORT_TEXT, order=1),
    )
    course = CourseFactory(application_form=form)
    user = UserFactory()
    answers = [(question, "Bulk Applicant 01")]
    first = _ensure_application(mock_site_context, user, course, answers)
    reject_application(first, actor=UserFactory(), message="Not this time.")

    rerun = _ensure_application(mock_site_context, user, course, answers)

    assert rerun.pk != first.pk
    assert rerun.state == CourseApplication.State.SUBMITTED
