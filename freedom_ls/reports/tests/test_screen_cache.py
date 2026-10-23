"""Tests for the short-lived cache the on-screen panels read the progress gather through."""

from __future__ import annotations

from uuid import UUID

import pytest

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from freedom_ls.accounts.factories import SiteFactory, UserFactory
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
from freedom_ls.reports.screen_cache import _cache_key, cached_cohort_progress
from freedom_ls.reports.tests.helpers import topic_progress


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


def test_the_cache_key_carries_the_site_id_and_cohort() -> None:
    cohort_id = UUID("11111111-1111-1111-1111-111111111111")

    assert _cache_key(7, cohort_id, "progress") == (
        "reports:screen:1:7:11111111-1111-1111-1111-111111111111:progress"
    )


def test_two_sites_with_the_same_cohort_pk_never_share_a_key() -> None:
    cohort_id = UUID("11111111-1111-1111-1111-111111111111")
    other_site = SiteFactory.build(pk=2)

    assert _cache_key(1, cohort_id, "progress") != _cache_key(
        other_site.pk, cohort_id, "progress"
    )
