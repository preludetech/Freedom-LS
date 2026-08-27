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
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.qa_helpers.management.commands.qa_create_report_cohort import (
    build_report_cohort,
)

#: Six unflagged learners are spread evenly over the six ladder rungs
#: ("started", 0.2, 0.4, 0.6, 0.8, 1.0), and each rung's fraction is rounded
#: onto a four-topic course: 0 slots, 1, 2, 2, 3 and 4 out of 4. Written out by
#: hand so a ladder that quietly stops spreading learners is a failure here.
EXPECTED_PERCENTAGES = [0, 25, 50, 50, 75, 100]


@pytest.fixture
def topic_course(mock_site_context):
    """A course of four topics -- enough for the ladder to land off 0 and 100."""
    course = CourseFactory(slug="qa-report-topics")
    for order in range(4):
        ContentCollectionItemFactory(
            collection_object=course, child_object=TopicFactory(), order=order
        )
    return course


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
def test_the_seeded_percentages_climb_the_whole_ladder(seeded_records):
    """The spread is the point of the fixture: a report built on an all-zero or
    all-hundred cohort exercises none of its medians, bands or flags."""
    assert sorted(record.progress_percentage for record in seeded_records) == (
        EXPECTED_PERCENTAGES
    )


@pytest.mark.django_db
def test_every_seeded_percentage_matches_its_own_completed_cells(seeded_records):
    """Four topics, so each completed cell is worth 25 points to its own record.

    The educator matrix reads the figure from the record and the cells from the
    rows beneath it; a percentage the record's own rows contradict is the
    incoherence this fixture used to ship.
    """
    completed_cells = {
        record.pk: TopicProgress.objects.filter(
            course_progress=record, complete_time__isnull=False
        ).count()
        for record in seeded_records
    }

    assert {record.pk: record.progress_percentage for record in seeded_records} == {
        pk: cells * 25 for pk, cells in completed_cells.items()
    }


@pytest.mark.django_db
def test_a_fully_completed_record_is_stamped_complete(seeded_records):
    finished = [
        record for record in seeded_records if record.progress_percentage == 100
    ]

    assert [record.completed_time is not None for record in finished] == [True]
