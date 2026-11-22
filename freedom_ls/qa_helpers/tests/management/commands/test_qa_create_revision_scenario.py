"""The revision seeder builds every revision state and builds it only once."""

from __future__ import annotations

from datetime import timedelta

import pytest

from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

if "freedom_ls.qa_helpers" not in settings.INSTALLED_APPS:  # pragma: no cover
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import ContentCollectionItem, Course, CoursePart
from freedom_ls.form_engine.models import FormQuestion
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.queries import course_progress_for
from freedom_ls.revision.models import RevisionReview, RevisionSchedule
from freedom_ls.revision.queries import (
    bank_questions,
    last_reviewed_at,
    ready_count,
    weak_sections,
)

pytestmark = [pytest.mark.dev_tooling, pytest.mark.django_db(transaction=True)]


def _seed(site) -> None:
    call_command("qa_create_revision_scenario", "--site-name", site.name)


def _main_record(site):
    user = User.objects.get(email="qa-revision@example.com")
    course = Course.objects.get(slug="qa-revision-course")
    record = course_progress_for(user, course)
    assert record is not None
    return user, record


def test_a_second_run_creates_no_further_rows(mock_site_context):
    _seed(mock_site_context)
    counts = (
        FormQuestion.objects.count(),
        ContentCollectionItem.objects.count(),
        RevisionSchedule.objects.count(),
        RevisionReview.objects.count(),
        CourseProgress.objects.count(),
        User.objects.count(),
    )

    _seed(mock_site_context)

    assert counts == (
        FormQuestion.objects.count(),
        ContentCollectionItem.objects.count(),
        RevisionSchedule.objects.count(),
        RevisionReview.objects.count(),
        CourseProgress.objects.count(),
        User.objects.count(),
    )


def test_bank_excludes_the_unfinished_part_and_the_dropped_question(mock_site_context):
    _seed(mock_site_context)
    _, record = _main_record(mock_site_context)

    texts = set(bank_questions(record).values_list("question", flat=True))

    assert not any(text.startswith("Advanced question") for text in texts)
    assert "Foundations question 5: which option is correct?" not in texts
    assert "Foundations question 1: which option is correct?" in texts


def test_practice_part_is_weak(mock_site_context):
    _seed(mock_site_context)
    user, record = _main_record(mock_site_context)
    practice = CoursePart.objects.get(slug="qa-revision-practice")

    assert weak_sections(user, record) == {practice.pk}


def test_ready_count_stops_at_the_limit(mock_site_context):
    _seed(mock_site_context)
    user, record = _main_record(mock_site_context)

    assert ready_count(user, record, timezone.now(), limit=41) == 41


def test_returning_learner_last_reviewed_twenty_days_ago(mock_site_context):
    _seed(mock_site_context)
    back = User.objects.get(email="qa-revision-back@example.com")
    course = Course.objects.get(slug="qa-revision-course")

    reviewed = last_reviewed_at(back, course)

    assert reviewed is not None
    assert timezone.now() - reviewed > timedelta(days=19)


def test_new_learner_has_an_empty_bank(mock_site_context):
    _seed(mock_site_context)
    user = User.objects.get(email="qa-revision-new@example.com")
    course = Course.objects.get(slug="qa-revision-course")
    record = course_progress_for(user, course)
    assert record is not None

    assert bank_questions(record).count() == 0
