"""End-to-end tests for a flashcard whose answer face carries wide content.

These cover layout and hit-testing that unit tests cannot reach: whether a
markdown table on the answer face pushes the card off a narrow viewport, whether
that table scrolls instead of being clipped, and whether the flip trigger still
receives a click now that it paints *below* both faces. They back QA bug B1.
"""

import pytest
from playwright.sync_api import Page, expect

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory

from ..conftest import reverse_url

MOBILE_VIEWPORT = {"width": 375, "height": 812}

QUESTION = "Which status code for a failed write?"

# A five-column table and a fenced code block: between them they set a
# min-content width several times a phone's viewport. This is the shape of the
# demo content that exposed B1.
WIDE_ANSWER = """
| Code | Meaning | Client should | Retryable | Notes |
| --- | --- | --- | --- | --- |
| `400` | Malformed request | Fix the payload | No | Syntax only |
| `409` | Conflicts with current state | Re-read, then retry | Yes | Optimistic locking |
| `422` | Well-formed but semantically invalid | Fix the values | No | Validation errors |

```json
{"errors": {"email": ["Enter a valid email address."], "role": ["Unknown role."]}}
```
"""


def _build_flashcard_page(
    live_server,
    *,
    user: User,
    size: str = "",
    back: str = WIDE_ANSWER,
) -> str:
    """Create a one-topic course whose content is a single c-flashcard.

    Returns the URL of the player item page that renders it. ``user`` is
    registered for the course: item content gates on registration
    (``decision.can_access_content``), so the browsing user must be enrolled.
    """
    attrs = f' size="{size}"' if size else ""
    flashcard = (
        f"<c-flashcard{attrs}>\n"
        f'<c-slot name="front">\n\n{QUESTION}\n\n</c-slot>\n'
        f'<c-slot name="back">\n{back}\n</c-slot>\n'
        "</c-flashcard>"
    )
    course = CourseFactory(title="Flashcard Course", slug="flashcard-course")
    topic = TopicFactory(
        title="Flashcard Topic", slug="flashcard-topic", content=flashcard
    )
    ContentCollectionItemFactory(collection_object=course, child_object=topic, order=0)
    LearnerCourseRegistrationFactory(learner__user=user, course=course, is_active=True)
    # str() because the shared reverse_url helper is untyped (returns Any).
    return str(
        reverse_url(
            live_server,
            "learner_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )


def _click_card_corner(page: Page) -> None:
    """Click the card near its top-left, where the decorative kicker sits.

    A raw mouse click rather than ``locator.click()``: the faces are
    transparent to pointer events so the click lands on the flip trigger
    beneath them, and Playwright's actionability check would read that
    pass-through as the trigger being obscured.
    """
    box = page.locator(".flashcard-back").bounding_box()
    assert box is not None
    page.mouse.click(box["x"] + 12, box["y"] + 12)


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("size", ["", "wide"], ids=["standard", "wide"])
def test_a_wide_answer_does_not_push_the_card_off_a_narrow_viewport(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
    size: str,
):
    """A table on the answer face must not widen the card past the viewport.

    Regression (QA bug B1): both faces were grid items in a ``1fr`` track with
    the default ``min-width: auto``, so the answer table's min-content width
    became a floor the card could not go below. At 375px the card measured
    586px and took the whole page's horizontal scroll with it.
    """
    page = logged_in_page
    url = _build_flashcard_page(live_server, user=logged_in_user, size=size)
    page.set_viewport_size(MOBILE_VIEWPORT)
    page.goto(url)

    face = page.locator(".flashcard-back")
    expect(face).to_be_attached()

    # offsetWidth, not the bounding box: the resting face is rotated in 3-D and
    # its projected box is not its layout width, which is what is under test.
    width = face.evaluate("el => el.offsetWidth")
    assert width <= MOBILE_VIEWPORT["width"], (
        f"card lays out {width}px wide on a {MOBILE_VIEWPORT['width']}px viewport"
    )

    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 0, f"page scrolls {overflow}px horizontally"


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_the_answer_table_scrolls_instead_of_being_clipped(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
):
    """Content too wide for the face gets its own horizontal scroll.

    Capping the face without this would simply hide the far columns: the point
    of the cap is that nothing is lost, only moved behind a scroll.
    """
    page = logged_in_page
    url = _build_flashcard_page(live_server, user=logged_in_user)
    page.set_viewport_size(MOBILE_VIEWPORT)
    page.goto(url)
    _click_card_corner(page)

    table = page.locator(".flashcard-back table")
    expect(table).to_be_attached()

    metrics = table.evaluate("el => ({scroll: el.scrollWidth, client: el.clientWidth})")
    assert metrics["scroll"] > metrics["client"], (
        "the table fits its face, so this test is no longer exercising the overflow"
    )

    # It really is a scroll container, not merely an element that overflows.
    table.evaluate("el => el.scrollLeft = 200")
    assert table.evaluate("el => el.scrollLeft") > 0, "table did not scroll"


@pytest.mark.playwright
# transaction=True so the Playwright browser (separate connection) sees committed data
@pytest.mark.django_db(transaction=True)
def test_clicking_prose_still_flips_the_card(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
):
    """A click on the face still reaches the flip trigger underneath it.

    The trigger had to move below both faces so a swipe on a scrolling table
    could reach the table. The faces are transparent to pointer events to keep
    "click anywhere to flip" working; this is the check that it does.
    """
    page = logged_in_page
    url = _build_flashcard_page(live_server, user=logged_in_user)
    page.goto(url)

    trigger = page.get_by_role("button", name="Flip card")
    expect(trigger).to_have_attribute("aria-pressed", "false")

    # Click the question text itself, not the trigger — the point is that the
    # click passes through the face to the trigger beneath it.
    box = page.get_by_text(QUESTION).bounding_box()
    assert box is not None
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)

    expect(trigger).to_have_attribute("aria-pressed", "true")
