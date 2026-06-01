import pytest
from playwright.sync_api import Page, expect

from conftest import reverse_url
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.student_interface.templatetags.course_storage_keys import (
    course_part_storage_key,
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
    the retired course start page, so on detail pages clicking the toggle did nothing.
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

    # ``reset_local_storage`` (autouse) ensures localStorage is empty before
    # the first navigation, so the course-part starts collapsed.
    logged_in_page.goto(topic_url)

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
    # course_home is now a resume redirector, so navigate to a concrete item URL
    # to re-render the player TOC and assert the expand state persisted.
    second_item_url = reverse_url(
        live_server,
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 2},
    )
    # Single source of truth for the storage key — production helper, not an
    # ad-hoc f-string in the test.
    storage_key = course_part_storage_key(course.slug, 2)

    # ``reset_local_storage`` (autouse) clears localStorage before navigation.
    logged_in_page.goto(topic_url)

    # Scope lookups to the outline panel: the current item's title also appears
    # in the breadcrumb, the mobile compact header, and the content <h1>, so an
    # unscoped get_by_text would match several elements.
    outline = logged_in_page.get_by_role("navigation", name="Course outline")
    toggle_button = outline.get_by_role("button", name="Chapter One")
    expect(toggle_button).to_be_visible()
    inner_topic_in_toc = outline.get_by_text("Inner Topic", exact=True)
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

    # Navigating to another item page should find the part already expanded.
    logged_in_page.goto(second_item_url)
    outline_after_nav = logged_in_page.get_by_role("navigation", name="Course outline")
    inner_topic_after_nav = outline_after_nav.get_by_text("Inner Topic", exact=True)
    expect(inner_topic_after_nav).to_be_visible()


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_back_button_closes_mobile_bottom_sheet(
    live_server,
    logged_in_page: Page,
):
    """Pressing Back with the mobile outline bottom sheet open closes the sheet.

    The browser/device Back button is one of the three required dismiss routes
    (alongside scrim tap and Escape). It must close the modal sheet and keep the
    learner on the same page — it must NOT perform a normal navigation away.
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

    item_url = reverse_url(
        live_server,
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )

    # Below lg the panel becomes a modal bottom sheet with a visible toggle.
    logged_in_page.set_viewport_size({"width": 375, "height": 812})
    logged_in_page.goto(item_url)

    sheet = logged_in_page.get_by_role("dialog", name="Course outline")
    toggle = logged_in_page.get_by_role("button", name="Open course outline")

    expect(sheet).to_be_hidden()
    toggle.click()
    expect(sheet).to_be_visible()

    logged_in_page.go_back()

    # Back closes the sheet and we stay on the same item page (no navigation).
    expect(sheet).to_be_hidden()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(logged_in_page).to_have_url(item_url)


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_course_part_toggle_accessible_name_is_just_the_title(
    live_server,
    logged_in_page: Page,
):
    """The part-toggle's accessible name is the part title only.

    The decorative expand/collapse chevron must not fold its icon name into the
    button's accessible name (state is conveyed by ``aria-expanded``), so a
    screen reader announces "Chapter One", not "expand Chapter One".
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

    item_url = reverse_url(
        live_server,
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    logged_in_page.goto(item_url)

    outline = logged_in_page.get_by_role("navigation", name="Course outline")
    # exact=True fails if the chevron's icon name ("expand"/"collapse") leaks
    # into the accessible name.
    toggle = outline.get_by_role("button", name="Chapter One", exact=True)
    expect(toggle).to_be_visible()
