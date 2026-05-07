"""Tests for Course.viewable_items()."""

import pytest

from freedom_ls.content_engine.factories import (
    CourseFactory,
    CoursePartFactory,
    FormFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CoursePart


@pytest.mark.django_db
def test_viewable_items_excludes_course_part_sentinels(mock_site_context):
    """viewable_items() returns only Topic/Form items in order, never CoursePart."""
    course: Course = CourseFactory(title="C", slug="c")
    part: CoursePart = CoursePartFactory(title="P", slug="p")
    inside_topic = TopicFactory(title="T1", slug="t1")
    inside_form = FormFactory(title="F1", slug="f1")
    direct_topic = TopicFactory(title="T2", slug="t2")

    course.items.create(child=part, order=0)
    part.items.create(child=inside_topic, order=0)
    part.items.create(child=inside_form, order=1)
    course.items.create(child=direct_topic, order=1)

    result = course.viewable_items()

    assert result == [inside_topic, inside_form, direct_topic]
    assert not any(isinstance(item, CoursePart) for item in result)


@pytest.mark.django_db
def test_viewable_items_matches_children_flat_filtered(mock_site_context):
    """viewable_items() preserves the relative order of children_flat() minus CourseParts."""
    course: Course = CourseFactory(title="C", slug="c")
    part: CoursePart = CoursePartFactory(title="P", slug="p")
    inside_topic = TopicFactory(title="T1", slug="t1")
    direct_topic = TopicFactory(title="T2", slug="t2")

    course.items.create(child=part, order=0)
    part.items.create(child=inside_topic, order=0)
    course.items.create(child=direct_topic, order=1)

    expected = [c for c in course.children_flat() if not isinstance(c, CoursePart)]
    assert course.viewable_items() == expected


@pytest.mark.django_db
def test_viewable_items_empty_when_only_empty_part(mock_site_context):
    """A course whose only child is an empty CoursePart returns an empty list."""
    course: Course = CourseFactory(title="C", slug="c")
    part: CoursePart = CoursePartFactory(title="P", slug="p")
    course.items.create(child=part, order=0)

    assert course.viewable_items() == []
