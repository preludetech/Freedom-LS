"""The shipped per-placement demo course sets due dates for a shared part's children.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

from datetime import time
from pathlib import Path

import pytest

from freedom_ls.content_engine.models import (
    Course,
    CoursePart,
    CoursePartChildDueDate,
    Topic,
)
from freedom_ls.content_engine.validate import (
    get_all_files,
    parse_single_file,
    validate_due_date_placements,
)
from freedom_ls.form_engine.models import Form

pytestmark = pytest.mark.fls_internal

PLACEMENT_COURSE_TITLE = "Functionality Demo - Per-placement Due Dates"
PLACEMENT_COURSE_DIR = Path("demo_content/functionality_demo_course_parts_placement")


def test_the_placement_course_directory_passes_the_placement_check_on_its_own():
    """The part it places lives in a sibling directory; the nested list is checked against
    that part all the same, and passes."""
    parsed = [
        item
        for file_path in get_all_files(PLACEMENT_COURSE_DIR)
        for item in parse_single_file(file_path)
    ]

    assert validate_due_date_placements(parsed) == []


@pytest.mark.django_db
def test_placement_gives_key_ideas_its_own_due_days(
    site, loaded_demo_content, mock_site_context
):
    course = Course.objects.get(title=PLACEMENT_COURSE_TITLE)
    part_placement = course.items.get()
    key_ideas = Topic.objects.get(title="Key Ideas")

    row = CoursePartChildDueDate.objects.get(
        part_collection_item=part_placement, collection_item__child_id=key_ideas.pk
    )

    assert row.due_days_after_registration == 3
    assert row.no_due_date is False


@pytest.mark.django_db
def test_placement_removes_the_knowledge_check_deadline(
    site, loaded_demo_content, mock_site_context
):
    course = Course.objects.get(title=PLACEMENT_COURSE_TITLE)
    part_placement = course.items.get()
    knowledge_check = Form.objects.get(title="Knowledge Check")

    row = CoursePartChildDueDate.objects.get(
        part_collection_item=part_placement,
        collection_item__child_id=knowledge_check.pk,
    )

    assert row.no_due_date is True
    assert row.due_days_after_registration is None


@pytest.mark.django_db
def test_placement_holds_exactly_two_child_due_date_rows(
    site, loaded_demo_content, mock_site_context
):
    course = Course.objects.get(title=PLACEMENT_COURSE_TITLE)

    rows = CoursePartChildDueDate.objects.filter(
        part_collection_item=course.items.get()
    )

    assert rows.count() == 2


@pytest.mark.django_db
def test_core_concepts_part_keeps_the_dates_from_its_files(
    site, loaded_demo_content, mock_site_context
):
    part = CoursePart.objects.get(title="Core Concepts")

    key_ideas_row = part.items.get(child_id=Topic.objects.get(title="Key Ideas").pk)
    check_row = part.items.get(child_id=Form.objects.get(title="Knowledge Check").pk)

    assert (key_ideas_row.due_days_after_registration, key_ideas_row.due_time) == (
        14,
        time(17, 0),
    )
    assert check_row.due_days_after_registration == 21
