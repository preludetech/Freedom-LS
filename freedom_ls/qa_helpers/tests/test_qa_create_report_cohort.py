"""The report cohort seeds records whose stored figures match their own rows.

The command writes topic rows already complete, which never makes the
transition the completion receiver watches for. Without an explicit
recalculation the seeded percentage stays at the registration's initial 0, and
the educator matrix renders 0% beside a row of completed cells -- exactly the
incoherence a tester is told to treat as a read-path defect.
"""

from __future__ import annotations

import pytest

from django.conf import settings

if "freedom_ls.qa_helpers" not in settings.INSTALLED_APPS:  # pragma: no cover
    pytest.skip("qa_helpers not installed", allow_module_level=True)

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.learner_management.utils import calculate_course_progress_percentage
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.qa_helpers.management.commands.qa_create_report_cohort import (
    build_report_cohort,
)


@pytest.fixture
def topic_course(mock_site_context):
    """A course of four topics -- enough for the ladder to land off 0 and 100."""
    course = CourseFactory(slug="qa-report-topics")
    for order in range(4):
        ContentCollectionItemFactory(
            collection_object=course, child_object=TopicFactory(), order=order
        )
    return course


def _canonical_percentage(record: CourseProgress) -> int:
    """What the record's own completion rows say its percentage should be."""
    completed_item_ids = set(
        TopicProgress.objects.filter(
            course_progress=record,
            complete_time__isnull=False,
            collection_item__isnull=False,
        ).values_list("collection_item_id", flat=True)
    )
    return calculate_course_progress_percentage(record.course, completed_item_ids)


@pytest.fixture
def seeded_records(site, topic_course):
    build_report_cohort(
        site=site,
        cohort_name="QA Report Cohort",
        num_learners=6,
        course_slugs=(topic_course.slug,),
        inactive_course_slugs=(),
        num_flagged=0,
        no_progress=False,
        email_prefix="qa-report-test",
        educator_email=None,
    )
    return list(CourseProgress.objects.filter(course=topic_course))


@pytest.mark.django_db
def test_every_seeded_percentage_matches_its_own_completed_cells(seeded_records):
    assert seeded_records
    disagreeing = [
        (record.pk, record.progress_percentage, _canonical_percentage(record))
        for record in seeded_records
        if record.progress_percentage != _canonical_percentage(record)
    ]
    assert not disagreeing, f"stored percentage disagrees with cells: {disagreeing}"


@pytest.mark.django_db
def test_some_seeded_learners_are_actually_partway_through(seeded_records):
    """Guards the test above from passing on an all-zero seed."""
    assert any(0 < record.progress_percentage < 100 for record in seeded_records)


@pytest.mark.django_db
def test_a_fully_completed_record_is_stamped_complete(seeded_records):
    finished = [r for r in seeded_records if r.progress_percentage == 100]
    assert finished, "the ladder should take at least one learner all the way"
    assert all(record.completed_time is not None for record in finished)
