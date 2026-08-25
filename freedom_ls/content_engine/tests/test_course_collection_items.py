"""Tests for the collection_items()/collection_items_flat()/viewable_collection_items()
trio on Course and CoursePart, and their positional relationship to the existing
children()/children_flat()/viewable_items() accessors."""

import pytest

from freedom_ls.content_engine.factories import (
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, CoursePart
from freedom_ls.form_engine.factories import FormFactory


@pytest.mark.django_db
def test_viewable_collection_items_names_same_content_as_viewable_items(
    mock_site_context,
):
    """viewable_collection_items()[n].child is viewable_items()[n] at every position.

    The course player's 1-based index depends on this positional identity.
    """
    course: Course = CourseFactory(title="C", slug="c")
    part: CoursePart = CoursePartFactory(title="P", slug="p")
    inside_topic = TopicFactory(title="T1", slug="t1")
    inside_form = FormFactory(title="F1", slug="f1")
    direct_topic = TopicFactory(title="T2", slug="t2")

    course.items.create(child=part, order=0)
    part.items.create(child=inside_topic, order=0)
    part.items.create(child=inside_form, order=1)
    course.items.create(child=direct_topic, order=1)

    viewable_items = course.viewable_items()
    viewable_collection_items = course.viewable_collection_items()

    assert len(viewable_items) == len(viewable_collection_items)
    assert [ci.child for ci in viewable_collection_items] == viewable_items


@pytest.mark.django_db
def test_children_unchanged_for_course_without_course_parts(mock_site_context):
    """children() still returns exactly the resolved children, with no CoursePart."""
    course: Course = CourseFactory(title="C", slug="c")
    topic = TopicFactory(title="T1", slug="t1")
    form = FormFactory(title="F1", slug="f1")

    course.items.create(child=topic, order=0)
    course.items.create(child=form, order=1)

    assert course.children() == [topic, form]


@pytest.mark.django_db
def test_children_unchanged_for_course_with_course_parts(mock_site_context):
    """children() still returns the top-level children only, including the CoursePart itself."""
    course: Course = CourseFactory(title="C", slug="c")
    part: CoursePart = CoursePartFactory(title="P", slug="p")
    inside_topic = TopicFactory(title="T1", slug="t1")
    direct_topic = TopicFactory(title="T2", slug="t2")

    course.items.create(child=part, order=0)
    part.items.create(child=inside_topic, order=0)
    course.items.create(child=direct_topic, order=1)

    assert course.children() == [part, direct_topic]


@pytest.mark.django_db
def test_children_flat_unchanged_for_course_with_course_parts(mock_site_context):
    """children_flat() still descends into CourseParts in order."""
    course: Course = CourseFactory(title="C", slug="c")
    part: CoursePart = CoursePartFactory(title="P", slug="p")
    inside_topic = TopicFactory(title="T1", slug="t1")
    direct_topic = TopicFactory(title="T2", slug="t2")

    course.items.create(child=part, order=0)
    part.items.create(child=inside_topic, order=0)
    course.items.create(child=direct_topic, order=1)

    assert course.children_flat() == [part, inside_topic, direct_topic]


@pytest.mark.django_db
def test_viewable_items_unchanged_for_course_with_course_parts(mock_site_context):
    """viewable_items() still excludes CourseParts, derived through the new trio."""
    course: Course = CourseFactory(title="C", slug="c")
    part: CoursePart = CoursePartFactory(title="P", slug="p")
    inside_topic = TopicFactory(title="T1", slug="t1")
    direct_topic = TopicFactory(title="T2", slug="t2")

    course.items.create(child=part, order=0)
    part.items.create(child=inside_topic, order=0)
    course.items.create(child=direct_topic, order=1)

    assert course.viewable_items() == [inside_topic, direct_topic]


@pytest.mark.django_db
def test_collection_items_memoized_issues_one_items_query(
    mock_site_context, django_assert_num_queries
):
    """Two collection_items() calls on one instance issue only one round of queries.

    A single call issues two queries: the items query itself, plus one
    prefetch_related query resolving "child" for the one content type
    present. The second collection_items() call must add none.
    """
    course: Course = CourseFactory(title="C", slug="c")
    topic = TopicFactory(title="T1", slug="t1")
    course.items.create(child=topic, order=0)

    with django_assert_num_queries(2):
        course.collection_items()
        course.collection_items()


@pytest.mark.django_db
def test_course_part_collection_items_names_same_content_as_children(
    mock_site_context,
):
    """CoursePart.collection_items()[n].child is children()[n] at every position."""
    part: CoursePart = CoursePartFactory(title="P", slug="p")
    inside_topic = TopicFactory(title="T1", slug="t1")
    inside_form = FormFactory(title="F1", slug="f1")

    part.items.create(child=inside_topic, order=0)
    part.items.create(child=inside_form, order=1)

    assert [ci.child for ci in part.collection_items()] == part.children()
