"""Tests for carrying a course's placement due dates over when a load moves a child."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from django.contrib.sites.models import Site
from django.db import connection
from django.test.utils import CaptureQueriesContext

from freedom_ls.content_engine.management.commands import content_save
from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePart,
    CoursePartChildDueDate,
    Topic,
)
from freedom_ls.content_engine.moved_children import (
    MovedChild,
    carry_placement_due_dates,
    moved_children,
)
from freedom_ls.tests.site_context import drop_ambient_request

PART_A = "01. A"
PART_B = "02. B"


def _uuid_for(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"moved-children/{name}"))


def _write_course(root: Path, title: str, children: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "course.md").write_text(
        f"---\ncontent_type: COURSE\ntitle: {title}\nuuid: {_uuid_for(title)}\n"
        f"children:\n{children}---\n"
    )


def _write_part(root: Path, part: str, children: list[str] | None = None) -> Path:
    part_dir = root / part
    part_dir.mkdir(parents=True, exist_ok=True)
    lines = ["---", "content_type: COURSE_PART", f"title: {part}"]
    lines.append(f"uuid: {_uuid_for(part)}")
    if children is not None:
        lines.append("children:")
        lines.extend(f"  - path: {child}" for child in children)
    (part_dir / "part.yaml").write_text("\n".join(lines) + "\n")
    return part_dir


def _write_topic(part_dir: Path, name: str) -> None:
    (part_dir / f"{name}.md").write_text(
        f"---\ncontent_type: TOPIC\ntitle: {name}\nuuid: {_uuid_for(name)}\n---\n\nBody.\n"
    )


def _load(root: Path, site: Site) -> None:
    drop_ambient_request()
    save_content_to_db(root, site.name)


def _row_in_part(name: str, part_title: str) -> ContentCollectionItem:
    topic = Topic.objects.get(title=name)
    return ContentCollectionItem._base_manager.get(
        child_id=topic.pk, course_part__title=part_title
    )


def _days_for(row: ContentCollectionItem) -> list[int]:
    return sorted(
        CoursePartChildDueDate._base_manager.filter(
            collection_item=row, due_days_after_registration__isnull=False
        ).values_list("due_days_after_registration", flat=True)
    )


def _write_course_beside_parts(root: Path, nested: str) -> Path:
    """A course in its own directory, with part A and part B in a sibling `parts`
    directory, so the parts can be loaded together without the course."""
    _write_course(
        root / "course",
        "Moving Course",
        f"  - path: ../parts/{PART_A}/part.yaml\n{nested}"
        f"  - path: ../parts/{PART_B}/part.yaml\n",
    )
    parts = root / "parts"
    _write_part(parts, PART_A)
    _write_part(parts, PART_B)
    return parts


_MOVING_DATED_5 = (
    "    children:\n      - path: moving.md\n        due_days_after_registration: 5\n"
)


@pytest.mark.django_db
def test_moving_a_topic_carries_the_courses_date_when_the_old_part_is_loaded(
    site, mock_site_context, tmp_path
):
    """Both parts are reloaded and the course is not, so the course's rows are not
    reconciled; the date the course gave the child follows the child's new row."""
    parts = _write_course_beside_parts(tmp_path, _MOVING_DATED_5)
    _write_topic(parts / PART_A, "moving")
    _load(tmp_path, site)
    old_row = _row_in_part("moving", PART_A)

    (parts / PART_A / "moving.md").rename(parts / PART_B / "moving.md")
    _load(parts, site)

    new_row = _row_in_part("moving", PART_B)
    assert new_row.pk != old_row.pk
    assert _days_for(new_row) == [5]
    assert _days_for(old_row) == []


@pytest.mark.django_db
def test_a_carried_date_is_keyed_by_the_courses_placement_of_the_new_part(
    site, mock_site_context, tmp_path
):
    parts = _write_course_beside_parts(tmp_path, _MOVING_DATED_5)
    _write_topic(parts / PART_A, "moving")
    _load(tmp_path, site)

    (parts / PART_A / "moving.md").rename(parts / PART_B / "moving.md")
    _load(parts, site)

    date = CoursePartChildDueDate._base_manager.get(
        collection_item=_row_in_part("moving", PART_B)
    )
    placement = date.part_collection_item
    assert (placement.child_id, placement.collection_id) == (
        CoursePart.objects.get(title=PART_B).pk,
        Course.objects.get(title="Moving Course").pk,
    )


@pytest.mark.django_db
def test_reloading_only_the_new_part_carries_nothing(site, mock_site_context, tmp_path):
    """Part A is not in the load, so its row may be a placement made on purpose; the
    load cannot tell, and leaves the date where it is."""
    parts = _write_course_beside_parts(tmp_path, _MOVING_DATED_5)
    _write_topic(parts / PART_A, "moving")
    _load(tmp_path, site)
    old_row = _row_in_part("moving", PART_A)

    (parts / PART_A / "moving.md").rename(parts / PART_B / "moving.md")
    _load(parts / PART_B, site)

    assert _days_for(_row_in_part("moving", PART_B)) == []
    assert _days_for(old_row) == [5]


@pytest.mark.django_db
def test_a_topic_the_course_dates_in_one_of_its_two_parts_keeps_that_date(
    site, mock_site_context, tmp_path
):
    """The topic sits in part A and part B on purpose, and the course dates it under part
    A only. Reloading part B alone is no move."""
    _write_course(
        tmp_path,
        "Shared Course",
        f"  - path: {PART_A}/part.yaml\n"
        f"    children:\n      - path: ../{PART_B}/shared.md\n"
        "        due_days_after_registration: 1\n"
        f"  - path: {PART_B}/part.yaml\n",
    )
    _write_part(tmp_path, PART_A, children=[f"../{PART_B}/shared.md"])
    _write_topic(_write_part(tmp_path, PART_B), "shared")
    _load(tmp_path, site)
    row_a = _row_in_part("shared", PART_A)

    _load(tmp_path / PART_B, site)

    assert _days_for(row_a) == [1]
    assert _days_for(_row_in_part("shared", PART_B)) == []


@pytest.mark.django_db
def test_a_topic_the_course_dates_in_both_parts_keeps_one_date_per_row(
    site, mock_site_context, tmp_path
):
    """The topic sits in part A and part B, and the course dates it under both. Reloading
    part B alone must not pile part A's date onto part B's row: the course would then have
    two values for one row."""
    _write_course(
        tmp_path,
        "Shared Course",
        f"  - path: {PART_A}/part.yaml\n"
        f"    children:\n      - path: ../{PART_B}/shared.md\n"
        "        due_days_after_registration: 1\n"
        f"  - path: {PART_B}/part.yaml\n"
        "    children:\n      - path: shared.md\n"
        "        due_days_after_registration: 2\n",
    )
    _write_part(tmp_path, PART_A, children=[f"../{PART_B}/shared.md"])
    _write_topic(_write_part(tmp_path, PART_B), "shared")
    _load(tmp_path, site)
    row_a = _row_in_part("shared", PART_A)
    row_b = _row_in_part("shared", PART_B)

    _load(tmp_path / PART_B, site)

    assert _days_for(row_b) == [2]
    assert _days_for(row_a) == [1]


@pytest.mark.django_db
def test_a_move_never_takes_another_courses_date(site, mock_site_context, tmp_path):
    """Part A sits in two courses, each dating the topic. The move in one course carries
    that course's date only."""
    parts = tmp_path / "parts"
    _write_topic(_write_part(parts, PART_A), "moving")
    _write_part(parts, PART_B)
    for title, days in (("Course X", 3), ("Course Y", 4)):
        _write_course(
            tmp_path / title,
            title,
            f"  - path: ../parts/{PART_A}/part.yaml\n"
            "    children:\n      - path: moving.md\n"
            f"        due_days_after_registration: {days}\n"
            f"  - path: ../parts/{PART_B}/part.yaml\n",
        )
    _load(tmp_path, site)
    old_row = _row_in_part("moving", PART_A)

    (parts / PART_A / "moving.md").rename(parts / PART_B / "moving.md")
    _load(parts, site)

    new_row = _row_in_part("moving", PART_B)
    assert _days_for(new_row) == [3, 4]
    assert _days_for(old_row) == []


def _carry_query_count(root: Path, site: Site, topic_count: int) -> int:
    """The carry-over's own queries for a first load of one course, one part, N topics."""
    _write_course(root, "Cost Course", f"  - path: {PART_A}/part.yaml\n")
    part = _write_part(root, PART_A)
    for index in range(topic_count):
        _write_topic(part, f"cost-{topic_count}-{index}")
    _load(root, site)
    rows = list(ContentCollectionItem._base_manager.filter(site=site))
    loaded = {(row.collection_type_id, row.collection_id) for row in rows}
    with CaptureQueriesContext(connection) as queries:
        carry_placement_due_dates(site, moved_children(site, rows, loaded))
    return len(queries)


@pytest.mark.django_db
def test_a_first_loads_carry_over_cost_does_not_grow_with_the_rows(
    site, mock_site_context, tmp_path
):
    small = _carry_query_count(tmp_path / "small", site, topic_count=3)
    large = _carry_query_count(tmp_path / "large", site, topic_count=9)

    assert small == large


def _carry_query_count_for_moves(
    root: Path, site: Site, monkeypatch: pytest.MonkeyPatch, topic_count: int
) -> int:
    """The carry's own queries when a load moves N dated topics from part A to part B."""
    names = [f"moved-{topic_count}-{index}" for index in range(topic_count)]
    nested = "    children:\n" + "".join(
        f"      - path: {name}.md\n        due_days_after_registration: 2\n"
        for name in names
    )
    parts = _write_course_beside_parts(root, nested)
    for name in names:
        _write_topic(parts / PART_A, name)
    _load(root, site)
    for name in names:
        (parts / PART_A / f"{name}.md").rename(parts / PART_B / f"{name}.md")

    counts: list[tuple[int, int]] = []

    def counting(site: Site, moves: list[MovedChild]) -> None:
        with CaptureQueriesContext(connection) as queries:
            carry_placement_due_dates(site, moves)
        counts.append((len(moves), len(queries)))

    monkeypatch.setattr(content_save, "carry_placement_due_dates", counting)
    _load(parts, site)

    [(move_count, query_count)] = counts
    assert move_count == topic_count
    return query_count


@pytest.mark.django_db
def test_the_carry_cost_does_not_grow_with_the_moves(
    site, mock_site_context, tmp_path, monkeypatch
):
    small = _carry_query_count_for_moves(tmp_path / "s", site, monkeypatch, 3)
    large = _carry_query_count_for_moves(tmp_path / "l", site, monkeypatch, 9)

    assert small == large
