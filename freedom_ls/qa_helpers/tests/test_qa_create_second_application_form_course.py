"""The seeded application sittings are finished the way a real submission is."""

from __future__ import annotations

import pytest

from django.conf import settings

if "freedom_ls.qa_helpers" not in settings.INSTALLED_APPS:  # pragma: no cover
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.qa_helpers.management.commands.qa_create_second_application_form_course import (
    QUESTIONS,
    _get_or_create_application,
    _get_or_create_course,
    _get_or_create_form,
)

pytestmark = pytest.mark.dev_tooling


@pytest.mark.django_db
def test_the_completed_sitting_records_the_questions_it_was_asked(mock_site_context):
    site = mock_site_context
    user = UserFactory()
    form, questions = _get_or_create_form(site)
    course = _get_or_create_course(site, form)

    application = _get_or_create_application(site, user, course, form, questions)
    rerun = _get_or_create_application(site, user, course, form, questions)

    sitting = application.form_progress
    assert sitting is not None
    assert application.is_submitted
    assert sitting.furthest_page_reached == 1
    assert sitting.asked
    assert sitting.answers.count() == len(QUESTIONS)
    assert rerun.pk == application.pk
    assert rerun.form_progress is not None
    assert rerun.form_progress.asked == sitting.asked
