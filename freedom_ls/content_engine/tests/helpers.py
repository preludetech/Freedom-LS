"""Helpers shared by tests of the content tree."""

from __future__ import annotations

from pathlib import Path

from freedom_ls.content_engine.models import ContentCollectionItem, Course, Topic
from freedom_ls.form_engine.models import Form


def collection_item_for(course: Course, child: Form | Topic) -> ContentCollectionItem:
    """The collection item placing `child` in `course`.

    Read off a freshly loaded Course: `collection_items()` memoizes per
    instance, so a test that attaches more content between two lookups would
    otherwise be handed the list as it stood at the first one.
    """
    placed: Course = Course.objects.get(pk=course.pk)
    for collection_item in placed.viewable_collection_items():
        if collection_item.child == child:
            return collection_item
    raise AssertionError(f"{child} is not placed in {course}.")


def write_organisation_course(repo_dir: Path, extra_frontmatter: str = "") -> Path:
    """Write a one-file course under `repo_dir` and return its `course.md`.

    `extra_frontmatter` is YAML lines, each ending in a newline, placed after
    the course's uuid.
    """
    course_dir = repo_dir / "org_course"
    course_dir.mkdir(exist_ok=True)
    course_file = course_dir / "course.md"
    course_file.write_text(f"""---
content_type: COURSE
title: Org Course
uuid: 70000000-0000-0000-0000-000000000001
{extra_frontmatter}---
""")
    return course_file
