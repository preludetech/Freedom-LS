"""End-to-end tests for the c-picture spotlight modal in the course player.

These cover browser-only behaviour that unit tests cannot reach: whether a
*closed* native <dialog> blankets the page, whether the background is
scroll-locked while the spotlight is open, and whether long-description chrome
stays reachable. They back the three QA regressions (Bugs 1-3) found against the
image-spotlight feature.
"""

import pytest
from playwright.sync_api import Page, expect

from conftest import reverse_url
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    FileFactory,
    TopicFactory,
)


def _build_picture_page(
    live_server,
    *,
    title: str,
    description: str = "",
    alt: str = "A demo image",
    content_after: str = "",
) -> str:
    """Create a one-topic course whose content is a single c-picture.

    Returns the URL of the player item page that renders it. The File row's
    ``file_path`` matches what ``Topic.calculate_path_from_root`` resolves for a
    topic with an empty ``file_path`` (``images/pic.svg``), so the picture
    resolves instead of rendering the "Image not found" fallback.
    """
    FileFactory(file_path="images/pic.svg")
    picture = (
        '<c-picture src="images/pic.svg" '
        f'alt="{alt}" title="{title}" description="{description}">'
        "</c-picture>"
    )
    course = CourseFactory(title="Picture Course", slug="picture-course")
    topic = TopicFactory(
        title="Picture Topic",
        slug="picture-topic",
        content=f"{picture}\n\n{content_after}",
    )
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)
    # str() because the shared reverse_url helper is untyped (returns Any).
    return str(
        reverse_url(
            live_server,
            "student_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_closed_spotlight_is_inert_and_trigger_is_clickable(
    live_server,
    logged_in_page: Page,
):
    """A closed spotlight <dialog> must be hidden so it cannot swallow clicks.

    Regression (QA Bug 1): the spotlight set ``display:flex`` on its base rule,
    overriding the UA ``dialog:not([open]){display:none}``. Closed dialogs then
    stayed laid out full-viewport and intercepted pointer events over the page.
    """
    page = logged_in_page
    url = _build_picture_page(live_server, title="Lone tree at dawn")
    page.goto(url)

    spotlight = page.get_by_role("dialog", name="Lone tree at dawn")
    # Closed: must be inert/hidden, not blanketing the viewport.
    expect(spotlight).to_be_hidden()

    # The trigger is reachable (not occluded by a closed dialog) and opens it.
    page.get_by_role("button", name="Open image").click()
    expect(spotlight).to_be_visible()


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_background_does_not_scroll_while_spotlight_open(
    live_server,
    logged_in_page: Page,
):
    """The page behind the spotlight must not scroll while it is open.

    Regression (QA Bug 2): no scroll-lock was applied, so the page behind
    scrolled while the spotlight was open.
    """
    page = logged_in_page
    filler = "\n\n".join(
        f"Filler paragraph {i}. " + ("lorem ipsum dolor sit amet " * 30)
        for i in range(15)
    )
    url = _build_picture_page(
        live_server, title="Scroll lock image", content_after=filler
    )
    page.set_viewport_size({"width": 1024, "height": 600})
    page.goto(url)

    # Precondition: a real wheel gesture scrolls the page when nothing is locked.
    # (A programmatic ``scrollTo`` is not a fair proxy — overflow:hidden blocks
    # user gestures but not scripted scrolling, which is exactly the bug's repro.)
    page.mouse.move(512, 300)
    page.mouse.wheel(0, 600)
    page.wait_for_function("window.scrollY > 0")
    page.evaluate("window.scrollTo(0, 0)")

    page.get_by_role("button", name="Open image").click()
    spotlight = page.get_by_role("dialog", name="Scroll lock image")
    expect(spotlight).to_be_visible()

    # A wheel gesture must not scroll the page behind the open spotlight.
    page.mouse.move(512, 300)
    page.mouse.wheel(0, 600)
    page.wait_for_timeout(150)
    assert page.evaluate("window.scrollY") == 0, "background scrolled behind spotlight"


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_long_description_keeps_spotlight_heading_reachable(
    live_server,
    logged_in_page: Page,
):
    """A long description must not clip the heading above the viewport.

    Regression (QA Bug 3): the centred flex column overflowed upward on a short
    viewport, leaving the top heading permanently clipped and unreachable.
    """
    page = logged_in_page
    long_desc = "This is a very long spotlight description. " * 60
    url = _build_picture_page(
        live_server, title="Detailed schematic", description=long_desc
    )
    page.set_viewport_size({"width": 375, "height": 360})
    page.goto(url)

    page.get_by_role("button", name="Open image").click()
    heading = page.get_by_role("heading", name="Detailed schematic")
    expect(heading).to_be_visible()

    # The heading must stay within the viewport (top edge reachable), not be
    # clipped above y=0 with no way to scroll up to it.
    box = heading.bounding_box()
    assert box is not None
    assert box["y"] >= 0, f"heading clipped above the viewport at y={box['y']}"
