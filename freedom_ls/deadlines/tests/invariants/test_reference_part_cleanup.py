"""Moving a part from children: to reference: leaves no deadline on its placement."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from django.contrib.sites.models import Site

from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.deadlines.factories import (
    CohortDeadlineOverrideFactory,
    DeadlineExtensionFactory,
    LearnerDeadlineOverrideFactory,
)
from freedom_ls.deadlines.models import (
    CohortDeadlineOverride,
    DeadlineExtension,
    ExtensionTarget,
    LearnerDeadlineOverride,
)
from freedom_ls.learner_management.factories import CohortCourseRegistrationFactory
from freedom_ls.learner_progress.factories import CourseProgressFactory

_FIRST_COURSE_UUID = "30000000-0000-0000-0000-000000000001"
_SECOND_COURSE_UUID = "30000000-0000-0000-0000-000000000002"
_PART_UUID = "30000000-0000-0000-0000-000000000003"
_INTRO_UUID = "30000000-0000-0000-0000-000000000004"
_PART_TOPIC_UUID = "30000000-0000-0000-0000-000000000005"


def _write_course(course_dir: Path, course_uuid: str, *, reference: bool) -> None:
    """A course with an intro topic and one part, which sits under reference: when
    `reference` is true and under children: otherwise."""
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
        f"---\ncontent_type: COURSE\ntitle: Course {course_uuid[-1]}\n"
        f"uuid: {course_uuid}\n{lists}---\n"
    )


def _put_deadlines_on_placement(course_uuid: str) -> None:
    """One of each deadline kind that can hang off the course's placement of the part."""
    _put_deadlines_on(
        course_uuid,
        ContentCollectionItem.objects.get(
            collection_id=course_uuid, child_id=_PART_UUID
        ),
    )


def _put_deadlines_on_part_topic(course_uuid: str) -> None:
    """One of each deadline kind for the course on the part's own row for its topic."""
    _put_deadlines_on(
        course_uuid,
        ContentCollectionItem.objects.get(
            collection_id=_PART_UUID, child_id=_PART_TOPIC_UUID
        ),
    )


def _put_deadlines_on(course_uuid: str, placement: ContentCollectionItem) -> None:
    course = Course.objects.get(pk=course_uuid)
    CohortDeadlineOverrideFactory.create(
        cohort_registration=CohortCourseRegistrationFactory.create(course=course),
        collection_item=placement,
    )
    LearnerDeadlineOverrideFactory.create(
        course_progress=CourseProgressFactory.create(course=course),
        collection_item=placement,
    )
    DeadlineExtensionFactory.create(
        course_progress=CourseProgressFactory.create(course=course),
        target_kind=ExtensionTarget.COLLECTION_ITEM,
        collection_item=placement,
    )


def _part_topic_deadline_counts(course_uuid: str) -> tuple[int, int, int]:
    on_topic = {"collection_item__collection_id": _PART_UUID}
    return (
        CohortDeadlineOverride.objects.filter(
            cohort_registration__course_id=course_uuid, **on_topic
        ).count(),
        LearnerDeadlineOverride.objects.filter(
            course_progress__course_id=course_uuid, **on_topic
        ).count(),
        DeadlineExtension.objects.filter(
            course_progress__course_id=course_uuid, **on_topic
        ).count(),
    )


def _deadline_counts(course_uuid: str) -> tuple[int, int, int]:
    cohort = CohortDeadlineOverride.objects.filter(
        collection_item__collection_id=course_uuid
    ).count()
    learner = LearnerDeadlineOverride.objects.filter(
        collection_item__collection_id=course_uuid
    ).count()
    extension = DeadlineExtension.objects.filter(
        collection_item__collection_id=course_uuid
    ).count()
    return cohort, learner, extension


@pytest.mark.django_db
def test_moving_a_part_to_reference_deletes_the_deadlines_on_its_placement_only(
    site: Site, mock_site_context: Site, capsys: pytest.CaptureFixture[str]
) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        first_dir = Path(tmpdir) / "first"
        second_dir = Path(tmpdir) / "second"
        for directory, course_uuid in (
            (first_dir, _FIRST_COURSE_UUID),
            (second_dir, _SECOND_COURSE_UUID),
        ):
            _write_course(directory, course_uuid, reference=False)
            save_content_to_db(directory, site.name)
            _put_deadlines_on_placement(course_uuid)
        capsys.readouterr()

        _write_course(first_dir, _FIRST_COURSE_UUID, reference=True)
        save_content_to_db(first_dir, site.name)

    assert _deadline_counts(_FIRST_COURSE_UUID) == (0, 0, 0)
    assert _deadline_counts(_SECOND_COURSE_UUID) == (1, 1, 1)
    assert (
        "Deleted with it: 1 cohort deadline override(s), "
        "1 learner deadline override(s), 1 deadline extension(s)"
    ) in capsys.readouterr().out


@pytest.mark.django_db
def test_moving_a_part_to_reference_deletes_the_courses_deadlines_on_its_topics(
    site: Site, mock_site_context: Site, capsys: pytest.CaptureFixture[str]
) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        first_dir = Path(tmpdir) / "first"
        second_dir = Path(tmpdir) / "second"
        for directory, course_uuid in (
            (first_dir, _FIRST_COURSE_UUID),
            (second_dir, _SECOND_COURSE_UUID),
        ):
            _write_course(directory, course_uuid, reference=False)
            save_content_to_db(directory, site.name)
            _put_deadlines_on_part_topic(course_uuid)
        capsys.readouterr()

        _write_course(first_dir, _FIRST_COURSE_UUID, reference=True)
        save_content_to_db(first_dir, site.name)

    assert _part_topic_deadline_counts(_FIRST_COURSE_UUID) == (0, 0, 0)
    assert _part_topic_deadline_counts(_SECOND_COURSE_UUID) == (1, 1, 1)
    assert (
        "Deleted with it: 1 cohort deadline override(s), "
        "1 learner deadline override(s), 1 deadline extension(s)"
    ) in capsys.readouterr().out
