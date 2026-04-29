import pytest
from playwright.sync_api import Page, expect

from conftest import reverse_url
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_toc_course_part_expands_and_collapses_on_course_detail_page(
    live_server,
    logged_in_page: Page,
):
    """Clicking a course-part toggle on a course detail page reveals the part's children.

    Previously the Alpine component backing ``x-data="coursePart"`` was only loaded on
    ``course_home.html``, so on detail pages clicking the toggle did nothing.
    """
    course = CourseFactory(title="Test Course", slug="test-course")
    landing_topic = TopicFactory(
        title="Landing Topic",
        slug="landing-topic",
        content="Welcome to the course",
    )
    course_part = CoursePartFactory(title="Chapter One", slug="chapter-one")
    inner_topic = TopicFactory(
        title="Inner Topic",
        slug="inner-topic",
        content="Inside chapter one",
    )
    ContentCollectionItemFactory(
        collection_object=course, child_object=landing_topic, order=0
    )
    ContentCollectionItemFactory(
        collection_object=course, child_object=course_part, order=1
    )
    ContentCollectionItemFactory(
        collection_object=course_part, child_object=inner_topic, order=0
    )

    topic_url = reverse_url(
        live_server,
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )

    # Clear any persisted expand/collapse state so we start from collapsed.
    logged_in_page.goto(topic_url)
    logged_in_page.evaluate("localStorage.clear()")
    logged_in_page.goto(topic_url)
    logged_in_page.wait_for_load_state("networkidle")

    toggle_button = logged_in_page.get_by_role("button", name="Chapter One")
    expect(toggle_button).to_be_visible()

    inner_topic_in_toc = logged_in_page.get_by_text("Inner Topic", exact=True)

    # Collapsed by default — the inner topic's title in the TOC is not visible.
    expect(inner_topic_in_toc).to_be_hidden()

    # Clicking the course-part toggle expands it and reveals the inner topic's title.
    toggle_button.click()
    expect(inner_topic_in_toc).to_be_visible()

    # Clicking again collapses it and hides the inner topic's title.
    toggle_button.click()
    expect(inner_topic_in_toc).to_be_hidden()


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_toc_course_part_expand_state_persists_across_navigation(
    live_server,
    logged_in_page: Page,
):
    """Expanding a course part writes to localStorage and persists across navigation."""
    course = CourseFactory(title="Test Course", slug="test-course")
    landing_topic = TopicFactory(
        title="Landing Topic",
        slug="landing-topic",
        content="Welcome to the course",
    )
    course_part = CoursePartFactory(title="Chapter One", slug="chapter-one")
    inner_topic = TopicFactory(
        title="Inner Topic",
        slug="inner-topic",
        content="Inside chapter one",
    )
    ContentCollectionItemFactory(
        collection_object=course, child_object=landing_topic, order=0
    )
    ContentCollectionItemFactory(
        collection_object=course, child_object=course_part, order=1
    )
    ContentCollectionItemFactory(
        collection_object=course_part, child_object=inner_topic, order=0
    )

    topic_url = reverse_url(
        live_server,
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    course_home_url = reverse_url(
        live_server,
        "student_interface:course_home",
        kwargs={"course_slug": course.slug},
    )
    storage_key = f"coursePart_{course.slug}_2"

    # Start from a clean localStorage on the topic page.
    logged_in_page.goto(topic_url)
    logged_in_page.evaluate("localStorage.clear()")
    logged_in_page.goto(topic_url)
    logged_in_page.wait_for_load_state("networkidle")

    toggle_button = logged_in_page.get_by_role("button", name="Chapter One")
    expect(toggle_button).to_be_visible()
    inner_topic_in_toc = logged_in_page.get_by_text("Inner Topic", exact=True)
    expect(inner_topic_in_toc).to_be_hidden()

    # Expanding should write the persisted state to localStorage.
    toggle_button.click()
    expect(inner_topic_in_toc).to_be_visible()
    stored_value = logged_in_page.evaluate(
        "(key) => localStorage.getItem(key)", storage_key
    )
    assert stored_value == "true", (
        f"Expected localStorage[{storage_key!r}] to be 'true' after expanding, "
        f"got {stored_value!r}"
    )

    # Navigating to the course home should find the part already expanded.
    logged_in_page.goto(course_home_url)
    logged_in_page.wait_for_load_state("networkidle")
    inner_topic_on_home = logged_in_page.get_by_text("Inner Topic", exact=True)
    expect(inner_topic_on_home).to_be_visible()
