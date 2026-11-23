"""Tests for the sidebar reference outline tag."""

from __future__ import annotations

import lxml.html
import pytest
from pytest_django import DjangoAssertNumQueries

from django.contrib.sites.models import Site
from django.db import connection
from django.template import Context, Template
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    CourseReferencePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_interface.utils import reference_outline

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


def _heading(html: str) -> lxml.html.HtmlElement:
    [heading] = [
        link
        for link in _links(html)
        if link.text_content().strip() == "Reference"
        and "/reference/" in link.get("href", "")
    ]
    return heading


@pytest.mark.django_db
def test_the_heading_links_to_the_reference_listing_when_the_course_has_reference_parts(
    mock_site_context: Site,
) -> None:
    course = _course_with_reference()

    html = TEMPLATE.render(Context({"course": course}))

    assert _heading(html).get("href") == reverse(
        "learner_interface:course_reference", kwargs={"course_slug": course.slug}
    )


@pytest.mark.django_db
def test_the_reference_parts_render_as_outline_rows(mock_site_context: Site) -> None:
    course = _course_with_reference()

    html = TEMPLATE.render(Context({"course": course}))

    root = lxml.html.fromstring(html)
    [nav] = root.cssselect('nav[aria-label="Reference"]')
    assert len(nav.cssselect('li[x-data="coursePart"]')) == 1
    assert nav.cssselect('svg[data-icon="folder"]')
    assert nav.cssselect(".toc-counter") == []


@pytest.mark.django_db
def test_nothing_renders_for_a_course_without_reference_parts(
    mock_site_context: Site,
) -> None:
    html = TEMPLATE.render(Context({"course": CourseFactory()}))

    assert _links(html) == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("on_reference_page", "expected"), [(True, "page"), (False, None)]
)
def test_the_heading_is_current_only_on_the_reference_listing(
    mock_site_context: Site, on_reference_page: bool, expected: str | None
) -> None:
    course = _course_with_reference()
    context = Context({"course": course, "on_reference_page": on_reference_page})

    assert _heading(TEMPLATE.render(context)).get("aria-current") == expected


@pytest.mark.django_db
def test_the_tag_query_count_does_not_grow_with_parts(
    mock_site_context: Site, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    small = _course_with_reference()
    large: Course = CourseFactory()
    for order in range(3):
        part = CoursePartFactory()
        CourseReferencePartFactory(course=large, course_part=part, order=order)
        for position in range(3):
            ContentCollectionItemFactory(
                collection_object=part, child_object=TopicFactory(), order=position
            )
    with CaptureQueriesContext(connection) as baseline:
        TEMPLATE.render(Context({"course": small}))

    with django_assert_num_queries(len(baseline)):
        TEMPLATE.render(Context({"course": large}))


def _topic_links(html: str) -> list[lxml.html.HtmlElement]:
    """The links on the reference topic rows, the heading left out."""
    links: list[lxml.html.HtmlElement] = lxml.html.fromstring(html).cssselect(
        'nav[aria-label="Reference"] li[x-data="coursePart"] ul a'
    )
    return links


@pytest.mark.django_db
def test_topic_rows_link_where_the_page_says_reference_is_linked(
    mock_site_context: Site,
) -> None:
    course = _course_with_reference()

    html = TEMPLATE.render(Context({"course": course, "reference_linked": True}))

    assert len(_topic_links(html)) == 1


@pytest.mark.django_db
def test_topic_rows_do_not_link_where_the_page_does_not_say_reference_is_linked(
    mock_site_context: Site,
) -> None:
    course = _course_with_reference()

    html = TEMPLATE.render(Context({"course": course}))

    assert _topic_links(html) == []


@pytest.mark.django_db
def test_a_reference_outline_the_page_supplies_is_drawn_without_reading_the_parts(
    mock_site_context: Site, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    course = _course_with_reference()
    outline = reference_outline(course, linked=True)

    with django_assert_num_queries(0):
        html = TEMPLATE.render(
            Context({"course": course, "reference_outline": outline})
        )

    assert len(_topic_links(html)) == 1
