"""Tests for carrying deadline overrides over when a re-sync moves a collection item."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from django.contrib.sites.models import Site
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePart,
    Topic,
)
from freedom_ls.content_engine.signals import collection_items_synced
from freedom_ls.deadlines.factories import (
    CohortDeadlineOverrideFactory,
    LearnerDeadlineOverrideFactory,
)
from freedom_ls.deadlines.models import CohortDeadlineOverride, LearnerDeadlineOverride
from freedom_ls.deadlines.signals import carry_over_deadline_overrides
from freedom_ls.deadlines.tests.helpers import (
    write_course,
    write_part,
    write_topic,
)
from freedom_ls.learner_management.factories import CohortCourseRegistrationFactory
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import drop_ambient_request

PART_A = "01. A"
PART_B = "02. B"
PART_C = "03. C"


def _load(root: Path, site: Site) -> None:
    drop_ambient_request()
    call_command("content_save", str(root), site.name)


def _row_in_part(topic: Topic, part_title: str) -> ContentCollectionItem:
    return ContentCollectionItem._base_manager.get(
        child_id=topic.pk, course_part__title=part_title
    )


def _topic() -> Topic:
    topic: Topic = Topic.objects.get(title="moving")
    return topic


def _first_load_with_overrides(
    root: Path, site: Site
) -> tuple[ContentCollectionItem, CohortDeadlineOverride, LearnerDeadlineOverride]:
    """Load a topic in part A and put a cohort and a learner override on its row."""
    write_course(root)
    part_a = write_part(root, PART_A)
    write_part(root, PART_B)
    write_part(root, PART_C)
    write_topic(part_a, "moving")
    call_command("content_save", str(root), site.name)

    course = Course.objects.get()
    old_row = _row_in_part(_topic(), PART_A)
    cohort_override: CohortDeadlineOverride = CohortDeadlineOverrideFactory(
        cohort_registration=CohortCourseRegistrationFactory(course=course),
        collection_item=old_row,
    )
    learner_override: LearnerDeadlineOverride = LearnerDeadlineOverrideFactory(
        course_progress=CourseProgressFactory(course=course),
        collection_item=old_row,
    )
    return old_row, cohort_override, learner_override


def _move_topic_to_part_b(root: Path) -> None:
    (root / PART_A / "moving.md").rename(root / PART_B / "moving.md")


def _item_of(override: CohortDeadlineOverride | LearnerDeadlineOverride) -> UUID | None:
    model = type(override)
    return model._base_manager.get(pk=override.pk).collection_item_id


@pytest.mark.django_db
def test_moving_a_topic_carries_both_override_models_to_the_new_row(
    site, mock_site_context, tmp_path
):
    old_row, cohort_override, learner_override = _first_load_with_overrides(
        tmp_path, site
    )
    _move_topic_to_part_b(tmp_path)

    _load(tmp_path, site)

    new_row = _row_in_part(_topic(), PART_B)
    assert new_row.pk != old_row.pk
    assert _item_of(cohort_override) == new_row.pk
    assert _item_of(learner_override) == new_row.pk
    assert ContentCollectionItem._base_manager.filter(pk=old_row.pk).exists()


@pytest.mark.django_db
def test_a_reload_without_a_move_leaves_the_overrides(
    site, mock_site_context, tmp_path
):
    old_row, cohort_override, learner_override = _first_load_with_overrides(
        tmp_path, site
    )

    _load(tmp_path, site)

    assert _item_of(cohort_override) == old_row.pk
    assert _item_of(learner_override) == old_row.pk


@pytest.mark.django_db
def test_a_topic_placed_in_two_parts_on_purpose_keeps_its_overrides(
    site, mock_site_context, tmp_path
):
    old_row, cohort_override, learner_override = _first_load_with_overrides(
        tmp_path, site
    )
    write_part(tmp_path, PART_B, children=[f"../{PART_A}/moving.md"])

    _load(tmp_path, site)

    assert _row_in_part(_topic(), PART_B).pk != old_row.pk
    assert _item_of(cohort_override) == old_row.pk
    assert _item_of(learner_override) == old_row.pk


@pytest.mark.django_db
def test_a_child_with_two_stale_rows_keeps_its_overrides(
    site, mock_site_context, tmp_path
):
    old_row, cohort_override, learner_override = _first_load_with_overrides(
        tmp_path, site
    )
    second_stale_row = ContentCollectionItem.objects.create(
        site=site,
        collection=CoursePart.objects.get(title=PART_B),
        child=_topic(),
        order=0,
    )
    (tmp_path / PART_A / "moving.md").rename(tmp_path / PART_C / "moving.md")

    _load(tmp_path, site)

    assert _row_in_part(_topic(), PART_C).pk not in {old_row.pk, second_stale_row.pk}
    assert _item_of(cohort_override) == old_row.pk
    assert _item_of(learner_override) == old_row.pk


@pytest.mark.django_db
def test_another_sites_row_for_the_same_child_is_never_moved(
    site, mock_site_context, tmp_path
):
    old_row, cohort_override, learner_override = _first_load_with_overrides(
        tmp_path, site
    )
    other_site = SiteFactory(name="Other", domain="other.example")
    other_row = ContentCollectionItem._base_manager.create(
        site=other_site,
        collection_type=old_row.collection_type,
        collection_id=old_row.collection_id,
        child_type=old_row.child_type,
        child_id=old_row.child_id,
        order=5,
    )
    other_override = CohortDeadlineOverrideFactory(
        site=other_site,
        cohort_registration=cohort_override.cohort_registration,
        collection_item=other_row,
    )
    _move_topic_to_part_b(tmp_path)

    _load(tmp_path, site)

    new_row = _row_in_part(_topic(), PART_B)
    assert _item_of(cohort_override) == new_row.pk
    assert _item_of(learner_override) == new_row.pk
    assert _item_of(other_override) == other_row.pk


@pytest.mark.django_db
def test_a_receiver_that_raises_rolls_the_move_back(site, mock_site_context, tmp_path):
    old_row, cohort_override, learner_override = _first_load_with_overrides(
        tmp_path, site
    )
    _move_topic_to_part_b(tmp_path)

    def failing_receiver(**kwargs: object) -> None:
        raise RuntimeError("receiver failed")

    collection_items_synced.connect(failing_receiver, weak=False)
    try:
        with pytest.raises(RuntimeError, match="receiver failed"):
            _load(tmp_path, site)
    finally:
        collection_items_synced.disconnect(failing_receiver)

    assert _item_of(cohort_override) == old_row.pk
    assert _item_of(learner_override) == old_row.pk


def _receiver_query_count(root: Path, site: Site, topic_count: int) -> int:
    """The receiver's own queries for a first load of one course, one part, N topics."""
    write_course(root)
    part = write_part(root, PART_A)
    for index in range(topic_count):
        write_topic(part, f"topic-{index}")
    _load(root, site)
    rows = list(ContentCollectionItem._base_manager.filter(site=site))
    with CaptureQueriesContext(connection) as queries:
        carry_over_deadline_overrides(
            sender=ContentCollectionItem, site=site, created=rows, written=rows
        )
    return len(queries)


@pytest.mark.django_db
def test_a_first_loads_carry_over_cost_does_not_grow_with_the_rows(
    site, mock_site_context, tmp_path
):
    """Every row of a first load is new, and the receiver used to look its course up and
    rebuild the whole item tree once per row."""
    small = _receiver_query_count(tmp_path / "small", site, topic_count=3)
    large = _receiver_query_count(tmp_path / "large", site, topic_count=9)

    assert small == large
