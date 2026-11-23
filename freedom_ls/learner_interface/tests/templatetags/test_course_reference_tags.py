"""Tests for the sidebar reference link tag."""

from __future__ import annotations

import lxml.html
import pytest

from django.template import Context, Template
from django.urls import reverse

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    CourseReferencePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course

TEMPLATE = Template("{% load course_reference_tags %}{% reference_link %}")


def _course_with_reference() -> Course:
    course: Course = CourseFactory()
    part = CoursePartFactory()
    CourseReferencePartFactory(course=course, course_part=part, order=0)
    ContentCollectionItemFactory(
        collection_object=part, child_object=TopicFactory(), order=0
    )
    return course


def _links(html: str) -> list[lxml.html.HtmlElement]:
    if not html.strip():
        return []
    links: list[lxml.html.HtmlElement] = lxml.html.fromstring(html).cssselect("a")
    return links


@pytest.mark.django_db
def test_the_link_points_at_the_reference_listing_when_the_course_has_reference_parts(
    mock_site_context,
):
    course = _course_with_reference()

    html = TEMPLATE.render(Context({"course": course}))

    [link] = _links(html)
    assert link.get("href") == reverse(
        "learner_interface:course_reference", kwargs={"course_slug": course.slug}
    )
    assert link.cssselect('svg[data-icon="reference"]')


@pytest.mark.django_db
def test_nothing_renders_for_a_course_without_reference_parts(mock_site_context):
    html = TEMPLATE.render(Context({"course": CourseFactory()}))

    assert _links(html) == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("on_reference_page", "expected"), [(True, "page"), (False, None)]
)
def test_the_link_is_current_only_on_a_reference_page(
    mock_site_context, on_reference_page, expected
):
    course = _course_with_reference()
    context = Context({"course": course, "on_reference_page": on_reference_page})

    [link] = _links(TEMPLATE.render(context))

    assert link.get("aria-current") == expected


@pytest.mark.django_db
def test_the_tag_costs_one_query(mock_site_context, django_assert_max_num_queries):
    course = _course_with_reference()

    with django_assert_max_num_queries(1):
        TEMPLATE.render(Context({"course": course}))
