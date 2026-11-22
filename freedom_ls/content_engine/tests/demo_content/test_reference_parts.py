"""The shipped demo content includes a course with reference parts beside its learning
path: one inside the course's own `reference/` directory and one shared from outside it.

Marked `fls_internal`: it reads `demo_content/`, which only this repo ships.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from django.contrib.sites.models import Site

from freedom_ls.content_engine.models import Course, CoursePart
from freedom_ls.content_engine.validate import (
    get_all_files,
    parse_single_file,
    validate_reference_lists,
)

pytestmark = pytest.mark.fls_internal

REFERENCE_COURSE_TITLE = "Functionality Demo - Reference Material"
REFERENCE_COURSE_DIR = Path("demo_content/functionality_demo_reference_material")


@pytest.mark.django_db
def test_the_learning_path_holds_only_the_flying_basics_part(
    site: Site, loaded_demo_content: Site, mock_site_context: Site
) -> None:
    course = Course.objects.get(title=REFERENCE_COURSE_TITLE)

    assert [item.child.title for item in course.items.all()] == ["Flying Basics"]


@pytest.mark.django_db
def test_the_reference_parts_are_listed_in_order(
    site: Site, loaded_demo_content: Site, mock_site_context: Site
) -> None:
    course = Course.objects.get(title=REFERENCE_COURSE_TITLE)

    assert [row.course_part.title for row in course.reference_parts.all()] == [
        "Airspace Rules",
        "Glossary",
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("title", ["Airspace Rules", "Glossary"])
def test_a_reference_part_is_not_a_child_of_the_course(
    title: str, site: Site, loaded_demo_content: Site, mock_site_context: Site
) -> None:
    course = Course.objects.get(title=REFERENCE_COURSE_TITLE)
    part = CoursePart.objects.get(title=title)

    assert not course.items.filter(child_id=part.pk).exists()


def test_the_course_directory_passes_the_reference_list_check_on_its_own() -> None:
    """The glossary lives in a sibling directory; the reference list is checked against
    it all the same, and passes."""
    parsed = [
        item
        for file_path in get_all_files(REFERENCE_COURSE_DIR)
        for item in parse_single_file(file_path)
    ]

    assert validate_reference_lists(parsed) == []
