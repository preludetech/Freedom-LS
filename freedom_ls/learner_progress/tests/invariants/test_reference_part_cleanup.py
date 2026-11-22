"""Moving a part from children: to reference: takes its topics out of course progress."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import cast

import pytest

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.learner_progress.factories import (
    CourseProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.utils import calculate_course_progress_percentage

_COURSE_UUID = "40000000-0000-0000-0000-000000000001"
_PART_UUID = "40000000-0000-0000-0000-000000000002"
_PART_TOPIC_UUID = "40000000-0000-0000-0000-000000000003"
_INTRO_UUID = "40000000-0000-0000-0000-000000000004"


def _write_course(course_dir: Path, *, reference: bool) -> None:
    """A course with an intro topic and a part holding one topic; the part sits under
    reference: when `reference` is true and under children: otherwise."""
    shutil.rmtree(course_dir, ignore_errors=True)
    (course_dir / "part").mkdir(parents=True)
    (course_dir / "intro.md").write_text(
        f"---\ncontent_type: TOPIC\ntitle: Intro\nuuid: {_INTRO_UUID}\n---\n\nBody\n"
    )
    (course_dir / "part" / "inside.md").write_text(
        f"---\ncontent_type: TOPIC\ntitle: Inside\nuuid: {_PART_TOPIC_UUID}\n"
        "---\n\nBody\n"
    )
    (course_dir / "part" / "part.yaml").write_text(
        f"---\ncontent_type: COURSE_PART\ntitle: Part\nuuid: {_PART_UUID}\n"
        "children:\n  - path: inside.md\n"
    )
    part_entry = "  - path: part/part.yaml\n"
    lists = (
        f"children:\n  - path: intro.md\nreference:\n{part_entry}"
        if reference
        else f"children:\n  - path: intro.md\n{part_entry}"
    )
    (course_dir / "course.md").write_text(
        f"---\ncontent_type: COURSE\ntitle: Course\nuuid: {_COURSE_UUID}\n{lists}---\n"
    )


@pytest.mark.django_db
def test_the_moved_parts_topics_no_longer_count_towards_course_progress(
    site: Site, mock_site_context: Site
) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "course"
        _write_course(course_dir, reference=False)
        save_content_to_db(course_dir, site.name)
        course = Course.objects.get(pk=_COURSE_UUID)
        intro_item = next(
            item
            for item in course.viewable_collection_items()
            if item.child.title == "Intro"
        )
        assert calculate_course_progress_percentage(course, {intro_item.id}) == 50

        _write_course(course_dir, reference=True)
        save_content_to_db(course_dir, site.name)

    reloaded = Course.objects.get(pk=_COURSE_UUID)
    assert calculate_course_progress_percentage(reloaded, {intro_item.id}) == 100


def _intro_item(course: Course) -> ContentCollectionItem:
    return next(
        item
        for item in course.viewable_collection_items()
        if item.child is not None and item.child.title == "Intro"
    )


def _record_with_intro_done(course: Course) -> CourseProgress:
    """A learner's record with the intro completed and nothing in the part."""
    record = cast(CourseProgress, CourseProgressFactory(course=course))
    intro_item = _intro_item(course)
    TopicProgressFactory(
        course_progress=record,
        topic=intro_item.child,
        collection_item=intro_item,
        complete_time=timezone.now(),
    )
    CourseProgress.objects.filter(pk=record.pk).update(progress_percentage=50)
    return record


@pytest.mark.django_db
def test_moving_a_part_to_reference_recalculates_the_stored_course_progress(
    site: Site, mock_site_context: Site
) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "course"
        _write_course(course_dir, reference=False)
        save_content_to_db(course_dir, site.name)
        record = _record_with_intro_done(Course.objects.get(pk=_COURSE_UUID))

        _write_course(course_dir, reference=True)
        save_content_to_db(course_dir, site.name)

    record.refresh_from_db()
    assert record.progress_percentage == 100


@pytest.mark.django_db
def test_a_reload_that_removes_no_placement_leaves_stored_progress_alone(
    site: Site, mock_site_context: Site
) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "course"
        _write_course(course_dir, reference=False)
        save_content_to_db(course_dir, site.name)
        record = _record_with_intro_done(Course.objects.get(pk=_COURSE_UUID))
        record.refresh_from_db()
        updated_at = record.updated_at

        save_content_to_db(course_dir, site.name)

    record.refresh_from_db()
    assert record.progress_percentage == 50
    assert record.updated_at == updated_at
