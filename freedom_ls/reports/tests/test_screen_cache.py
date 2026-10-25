"""Tests for the short-lived cache the on-screen panels read the progress gather through."""

from __future__ import annotations

from uuid import UUID

import pytest

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.learner_management.models import Cohort, Learner
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.reports.report_data import ReportTooLargeError
from freedom_ls.reports.screen_cache import (
    _cache_key,
    cached_cohort_progress,
    cached_cohort_progress_many,
    cached_cohort_report,
)
from freedom_ls.reports.tests.helpers import topic_progress
from freedom_ls.tests.factories import SiteFactory


@pytest.fixture(autouse=True)
def _empty_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def cohort(mock_site_context) -> Cohort:
    """Two members, one of whom finished the only topic."""
    course = CourseFactory()
    topic = TopicFactory()
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)
    cohort: Cohort = CohortFactory()
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    for last_name in ("Able", "Baker"):
        user = UserFactory(first_name="Learner", last_name=last_name)
        CohortMembershipFactory(cohort=cohort, learner__user=user)
        record = course_progress_record(course, user)
        if last_name == "Able":
            topic_progress(record, topic, complete_time=timezone.now())
    return cohort


@pytest.mark.django_db
class TestCachedCohortProgress:
    def test_a_second_read_within_the_ttl_runs_only_the_active_member_query(
        self, cohort, django_assert_max_num_queries
    ):
        cached_cohort_progress(cohort)

        with django_assert_max_num_queries(1):
            data = cached_cohort_progress(cohort)

        assert data.cohort_size == 2

    def test_refresh_gathers_again(self, cohort):
        cached_cohort_progress(cohort)
        completed_before = cached_cohort_progress(cohort).complete_count
        Learner.objects.filter(user__last_name="Able").update(is_active=False)

        refreshed = cached_cohort_progress(cohort, refresh=True)

        assert (completed_before, refreshed.cohort_size) == (1, 1)

    def test_a_learner_removed_after_caching_leaves_every_figure_on_the_next_read(
        self, cohort
    ):
        before = cached_cohort_progress(cohort)
        Learner.objects.filter(user__last_name="Able").update(is_active=False)

        after = cached_cohort_progress(cohort)

        assert [learner.full_name for learner in before.learners] == [
            "Learner Able",
            "Learner Baker",
        ]
        assert [learner.full_name for learner in after.learners] == ["Learner Baker"]
        assert (after.cohort_size, after.complete_count, after.not_started_count) == (
            1,
            0,
            1,
        )

    def test_a_learner_removed_after_caching_leaves_the_attention_list(self, cohort):
        cached_cohort_progress(cohort)
        Learner.objects.filter(user__last_name="Baker").update(is_active=False)

        after = cached_cohort_progress(cohort)

        assert [learner.full_name for learner in after.attention_list.learners] == []

    @override_settings(REPORTS_MAX_LEARNERS=1)
    def test_a_refused_cohort_is_not_cached(self, cohort):
        with pytest.raises(ReportTooLargeError):
            cached_cohort_progress(cohort)

        with pytest.raises(ReportTooLargeError):
            cached_cohort_progress(cohort)

    def test_the_data_is_gathered_again_once_the_entry_expires(self, cohort):
        cached_cohort_progress(cohort)
        Learner.objects.filter(user__last_name="Able").update(is_active=False)
        cache.delete(_cache_key(cohort.site_id, cohort.pk, "progress"))

        assert cached_cohort_progress(cohort).cohort_size == 1

    def test_a_learner_added_after_caching_is_listed_on_the_next_read(self, cohort):
        cached_cohort_progress(cohort)
        CohortMembershipFactory(
            cohort=cohort,
            learner__user=UserFactory(first_name="Learner", last_name="Charlie"),
        )

        after = cached_cohort_progress(cohort)

        assert [learner.full_name for learner in after.learners] == [
            "Learner Able",
            "Learner Baker",
            "Learner Charlie",
        ]

    def test_a_course_registered_after_caching_counts_on_the_next_read(self, cohort):
        before = cached_cohort_progress(cohort)
        course = CourseFactory()
        ContentCollectionItemFactory(
            collection_object=course, child_object=TopicFactory(), order=0
        )
        CohortCourseRegistrationFactory(cohort=cohort, course=course)

        after = cached_cohort_progress(cohort)

        assert (before.complete_count, after.complete_count) == (1, 0)


@pytest.mark.django_db
class TestCachedCohortProgressMany:
    def test_a_warm_read_of_several_cohorts_runs_only_the_membership_query(
        self, cohort, django_assert_max_num_queries
    ):
        other: Cohort = CohortFactory()
        CohortMembershipFactory(cohort=other)
        cached_cohort_progress_many([cohort, other])

        with django_assert_max_num_queries(1):
            gathers = cached_cohort_progress_many([cohort, other])

        assert {
            cohort_id: data.cohort_size for cohort_id, data in gathers.gathered.items()
        } == {cohort.pk: 2, other.pk: 1}

    @override_settings(REPORTS_MAX_LEARNERS=1)
    def test_an_oversized_cohort_is_refused_without_hiding_the_others(self, cohort):
        small: Cohort = CohortFactory()
        CohortMembershipFactory(cohort=small)

        gathers = cached_cohort_progress_many([cohort, small])

        assert set(gathers.gathered) == {small.pk}
        assert isinstance(gathers.refused[cohort.pk], ReportTooLargeError)

    def test_no_cohorts_is_an_empty_result_and_no_query(
        self, mock_site_context, django_assert_num_queries
    ):
        with django_assert_num_queries(0):
            gathers = cached_cohort_progress_many([])

        assert (gathers.gathered, gathers.refused) == ({}, {})


def test_the_cache_key_carries_the_site_id_and_cohort() -> None:
    cohort_id = UUID("11111111-1111-1111-1111-111111111111")

    assert _cache_key(7, cohort_id, "progress") == (
        "reports:screen:2:7:11111111-1111-1111-1111-111111111111:progress"
    )


def test_two_sites_with_the_same_cohort_pk_never_share_a_key() -> None:
    cohort_id = UUID("11111111-1111-1111-1111-111111111111")
    other_site = SiteFactory.build(pk=2)

    assert _cache_key(1, cohort_id, "progress") != _cache_key(
        other_site.pk, cohort_id, "progress"
    )


@pytest.mark.django_db
class TestCachedCohortReport:
    def test_a_learner_removed_after_caching_leaves_every_figure_on_the_next_read(
        self, cohort
    ):
        before = cached_cohort_report(cohort)
        Learner.objects.filter(user__last_name="Able").update(is_active=False)

        after = cached_cohort_report(cohort)

        (course,) = after.courses
        (table,) = course.summary_tables
        assert [learner.full_name for learner in before.learners] == [
            "Learner Able",
            "Learner Baker",
        ]
        assert [learner.full_name for learner in after.learners] == ["Learner Baker"]
        assert [row.full_name for row in course.learner_rows] == ["Learner Baker"]
        assert [row.full_name for row in table.rows] == ["Learner Baker"]
        assert [learner.full_name for learner in after.attention_list.learners] == [
            "Learner Baker"
        ]
        assert (after.cohort_size, after.complete_count, after.not_started_count) == (
            1,
            0,
            1,
        )

    def test_the_confusion_blocks_are_left_as_gathered_when_a_learner_is_trimmed(
        self, cohort
    ):
        before = cached_cohort_report(cohort)
        Learner.objects.filter(user__last_name="Able").update(is_active=False)

        after = cached_cohort_report(cohort)

        assert (
            after.courses[0].confusions_by_quiz == before.courses[0].confusions_by_quiz
        )

    def test_refresh_gathers_again(self, cohort):
        cached_cohort_report(cohort)
        Learner.objects.filter(user__last_name="Able").update(is_active=False)
        Learner.objects.filter(user__last_name="Baker").update(is_active=False)

        assert cached_cohort_report(cohort, refresh=True).cohort_size == 0

    def test_the_entry_carries_neither_a_logo_nor_wrong_answers(self, cohort):
        cached_cohort_report(cohort)

        entry = cache.get(_cache_key(cohort.site_id, cohort.pk, "report"))

        assert entry.organisation.logo_data_uri is None
        assert [learner.wrong_answers for learner in entry.learners] == [[], []]

    def test_a_learner_added_after_caching_is_listed_on_the_next_read(self, cohort):
        cached_cohort_report(cohort)
        CohortMembershipFactory(
            cohort=cohort,
            learner__user=UserFactory(first_name="Learner", last_name="Charlie"),
        )

        after = cached_cohort_report(cohort)

        assert [row.full_name for row in after.courses[0].learner_rows] == [
            "Learner Able",
            "Learner Baker",
            "Learner Charlie",
        ]
