"""Resetting the QA applicant has to take their form sittings with it.

CourseApplication.form_progress is RESTRICT, so the application goes first and
the sitting after -- and it is the sitting's cascade, through the
QuestionAnswerFile post_delete receiver, that sweeps the stored ID scan out of
the bucket. Deleting the application alone leaves the scan behind, and each
re-run of the reset then accumulates PII instead of clearing it.
"""

from __future__ import annotations

import pytest

from django.conf import settings

if "freedom_ls.qa_helpers" not in settings.INSTALLED_APPS:  # pragma: no cover
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.form_engine.factories import QuestionAnswerFileFactory
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.qa_helpers.management.commands.qa_create_application_review_accounts import (
    _purge_course_data,
)


@pytest.mark.django_db
def test_the_purge_takes_the_sitting_and_its_stored_file(mock_site_context):
    answer_file = QuestionAnswerFileFactory()
    sitting = answer_file.answer.form_progress
    user = sitting.user
    CourseApplicationFactory(user=user, form_progress=sitting)
    storage, name = answer_file.file.storage, answer_file.file.name
    assert storage.exists(name)

    counts = _purge_course_data(user)

    assert counts["CourseApplication"] == 1
    assert counts["FormProgress"] == 1
    assert not FormProgress._base_manager.filter(user=user).exists()
    assert not storage.exists(name)
