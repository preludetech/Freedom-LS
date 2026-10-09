"""Browser flows for a learner browsing a course and its content.

The Django test client coverage of the course detail page, the outline's
statuses and the part rows' announced text lives in ``views/test_course_detail.py``.
What only a browser shows is covered here: card hit areas, the outline's
expand state and mobile sheet, flashcard and spotlight behaviour, and layout at
real widths.
"""

from __future__ import annotations

import io
from decimal import Decimal

import pytest
from PIL import Image
from playwright.sync_api import FloatRect, Locator, Page, expect

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.conftest import reverse_url
from freedom_ls.content_engine.factories import (
    ArticleFactory,
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    FileFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, PriceKind
from freedom_ls.learner_interface.templatetags.course_storage_keys import (
    course_part_storage_key,
)
from freedom_ls.learner_interface.tests.helpers import topic_completion
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.app_guards import app_not_installed
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

# Long enough that it cannot fit a 375px phone's outline, so the row has to
# truncate rather than widen the page.
LONG_TOPIC_TITLE = (
    "Understanding Advanced Assessment Design and Rubric Calibration in Practice"
)
LONG_COURSE_TITLE = "Beta Course With A Rather Long Title To Force Wrapping"
QUESTION = "Which status code for a failed write?"
PICTURE_TITLE = "Lone tree at dawn"

# A five-column table and a fenced code block: between them they set a
# min-content width several times a phone's viewport.
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

COURSE_GRID = """
<c-grid>
<c-course-card path="../courses/browse/course.md"></c-course-card>
<c-course-card path="../courses/long/course.md" variant="compact"></c-course-card>
</c-grid>
"""


def _box(locator: Locator) -> FloatRect:
    box = locator.bounding_box()
    assert box is not None
    return box


def _card_of(link: Locator) -> Locator:
    return link.locator(
        "xpath=ancestor::*[self::article or contains(@class, 'surface')][1]"
    )


def _click_card_corner(card: Locator) -> None:
    """Click the card near its bottom-right corner, away from its title link."""
    box = _box(card)
    card.click(position={"x": box["width"] - 6, "y": box["height"] - 6})


def _assert_link_sits_inside_card(link: Locator) -> None:
    link_box = _box(link)
    card_box = _box(_card_of(link))
    assert link_box["x"] >= card_box["x"]
    assert link_box["y"] >= card_box["y"]
    assert link_box["x"] + link_box["width"] <= card_box["x"] + card_box["width"]
    assert link_box["y"] + link_box["height"] <= card_box["y"] + card_box["height"]


def _item_url(live_server: object, course: Course, index: int) -> str:
    return str(
        reverse_url(
            live_server,
            "learner_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": index},
        )
    )


def _detail_url(live_server: object, course: Course) -> str:
    return str(
        reverse_url(
            live_server,
            "learner_interface:course_detail",
            kwargs={"course_slug": course.slug},
        )
    )


def _flashcard(size: str = "") -> str:
    attrs = f' size="{size}"' if size else ""
    return (
        f"<c-flashcard{attrs}>\n"
        f'<c-slot name="front">\n\n{QUESTION}\n\n</c-slot>\n'
        f'<c-slot name="back">\n{WIDE_ANSWER}\n</c-slot>\n'
        "</c-flashcard>"
    )


def _logo_upload() -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new("RGB", (200, 100)).save(buf, format="PNG")
    return SimpleUploadedFile("logo.png", buf.getvalue(), content_type="image/png")


def _browse_course(user: User) -> Course:
    """The course the flow browses.

    Its first item is a topic gridding two course cards; the second is a part
    holding a standard flashcard, a wide flashcard and a picture; the last is a
    topic with a title too long for a phone's outline. It is discounted, so its
    detail page carries the widest compact price.
    """
    CourseFactory(
        title=LONG_COURSE_TITLE,
        slug="long-course",
        file_path="courses/long/course.md",
        access_config={"access_type": "free"},
    )
    course: Course = CourseFactory(
        title="Browse Course",
        slug="browse-course",
        file_path="courses/browse/course.md",
        description="A course description long enough to wrap on a phone screen.",
        access_config={"access_type": "free"},
        price_kind=PriceKind.DISCOUNTED,
        price_amount=Decimal("1499.00"),
        price_sale_amount=Decimal("999.00"),
        price_currency="ZAR",
    )
    LearnerCourseRegistrationFactory(learner__user=user, course=course, is_active=True)
    FileFactory(file_path="images/pic.svg")
    filler = "\n\n".join(
        f"Filler paragraph {i}. " + ("lorem ipsum dolor sit amet " * 30)
        for i in range(15)
    )
    picture = (
        f'<c-picture src="images/pic.svg" alt="A demo image" title="{PICTURE_TITLE}" '
        f'description="{"This is a very long spotlight description. " * 60}">'
        "</c-picture>"
    )
    part = CoursePartFactory(title="Chapter One", slug="chapter-one")
    topics = [
        TopicFactory(
            title="Course Grid",
            slug="course-grid",
            file_path="topics/grid.md",
            content=COURSE_GRID,
        ),
        TopicFactory(
            title="Flashcard Topic", slug="flashcard-topic", content=_flashcard()
        ),
        TopicFactory(
            title="Wide Flashcard Topic",
            slug="wide-flashcard-topic",
            content=_flashcard("wide"),
        ),
        TopicFactory(
            title="Picture Topic",
            slug="picture-topic",
            content=f"{picture}\n\n{filler}",
        ),
        TopicFactory(title=LONG_TOPIC_TITLE, slug="long-title-topic", content="x"),
    ]
    ContentCollectionItemFactory(
        collection_object=course, child_object=topics[0], order=0
    )
    ContentCollectionItemFactory(collection_object=course, child_object=part, order=1)
    for order, topic in enumerate(topics[1:4]):
        ContentCollectionItemFactory(
            collection_object=part, child_object=topic, order=order
        )
    ContentCollectionItemFactory(
        collection_object=course, child_object=topics[4], order=2
    )
    # Items open in order, so finishing the earlier ones unlocks every page.
    for topic in topics[:4]:
        topic_completion(course, user, topic, complete_time=timezone.now())
    return course


def test_learner_browses_a_course(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    course = _browse_course(logged_in_user)
    grid_url = _item_url(live_server, course, 1)
    flashcard_url = _item_url(live_server, course, 2)
    wide_flashcard_url = _item_url(live_server, course, 3)
    picture_url = _item_url(live_server, course, 4)

    # A course card opens its course from anywhere on the card, not only the title.
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(grid_url)
    card = _card_of(page.get_by_role("link", name="Browse Course").last)
    _click_card_corner(card)
    expect(page).to_have_url(_detail_url(live_server, course))

    # The outline's part opens and closes, and stays open across pages.
    page.goto(grid_url)
    outline = page.get_by_role("navigation", name="Course outline")
    toggle = outline.get_by_role("button", name="Chapter One")
    flashcard_row = outline.get_by_text("Flashcard Topic", exact=True)
    expect(flashcard_row).to_be_hidden()
    toggle.click()
    expect(flashcard_row).to_be_visible()
    toggle.click()
    expect(flashcard_row).to_be_hidden()
    toggle.click()
    storage_key = course_part_storage_key(course.slug, 2)
    assert page.evaluate("(key) => localStorage.getItem(key)", storage_key) == "true"
    page.goto(flashcard_url)
    expect(
        page.get_by_role("navigation", name="Course outline").get_by_text(
            "Flashcard Topic", exact=True
        )
    ).to_be_visible()

    # A flashcard keeps wide answers inside a phone-width card, scrolls a table
    # instead of clipping it, and flips when its prose is clicked.
    page.set_viewport_size({"width": 375, "height": 812})
    for url in (flashcard_url, wide_flashcard_url):
        page.goto(url)
        face = page.locator(".flashcard-back")
        expect(face).to_be_attached()
        # offsetWidth, not the bounding box: the resting face is rotated in 3-D
        # and its projected box is not its layout width.
        assert face.evaluate("el => el.offsetWidth") <= 375
        assert_no_horizontal_overflow(page)
    page.goto(flashcard_url)
    back = page.locator(".flashcard-back")
    # The faces pass pointer events through to the flip trigger beneath them, so
    # a raw mouse click, not Locator.click, which would read that as obscured.
    page.mouse.click(_box(back)["x"] + 12, _box(back)["y"] + 12)
    table = page.locator(".flashcard-back table")
    metrics = table.evaluate("el => ({scroll: el.scrollWidth, client: el.clientWidth})")
    assert metrics["scroll"] > metrics["client"]
    table.evaluate("el => el.scrollLeft = 200")
    assert table.evaluate("el => el.scrollLeft") > 0
    page.goto(flashcard_url)
    trigger = page.get_by_role("button", name="Flip card")
    expect(trigger).to_have_attribute("aria-pressed", "false")
    prose = _box(page.get_by_text(QUESTION))
    page.mouse.click(prose["x"] + prose["width"] / 2, prose["y"] + prose["height"] / 2)
    expect(trigger).to_have_attribute("aria-pressed", "true")

    # A picture's closed spotlight leaves the page clickable; open, it locks the
    # background scroll and keeps a long description's heading reachable.
    page.set_viewport_size({"width": 1024, "height": 600})
    page.goto(picture_url)
    spotlight = page.get_by_role("dialog", name=PICTURE_TITLE)
    expect(spotlight).to_be_hidden()
    # A real wheel gesture scrolls the page when nothing is locked. A scripted
    # scrollTo is no proxy: overflow:hidden blocks gestures, not scripts.
    page.mouse.move(512, 300)
    page.mouse.wheel(0, 600)
    page.wait_for_function("window.scrollY > 0")
    page.evaluate("window.scrollTo(0, 0)")
    page.get_by_role("button", name="Expand").click()
    expect(spotlight).to_be_visible()
    page.mouse.move(512, 300)
    page.mouse.wheel(0, 600)
    page.evaluate(
        "new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
    )
    assert page.evaluate("window.scrollY") == 0
    page.keyboard.press("Escape")
    expect(spotlight).to_be_hidden()
    page.set_viewport_size({"width": 375, "height": 360})
    page.get_by_role("button", name="Expand").click()
    heading = page.get_by_role("heading", name=PICTURE_TITLE)
    expect(heading).to_be_visible()
    assert _box(heading)["y"] >= 0

    # Back closes the mobile outline sheet without leaving the page.
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(grid_url)
    sheet = page.get_by_role("dialog", name="Course outline")
    sheet_toggle = page.get_by_role("button", name="Open course outline")
    expect(sheet).to_be_hidden()
    sheet_toggle.click()
    expect(sheet).to_be_visible()
    page.go_back()
    expect(sheet).to_be_hidden()
    expect(sheet_toggle).to_have_attribute("aria-expanded", "false")
    expect(page).to_have_url(grid_url)

    # Layout at every width.
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)

        page.goto(grid_url)
        for title in ("Browse Course", "Beta Course With"):
            link = page.get_by_role("link", name=title).last
            expect(link).to_be_visible()
            link.focus()
            expect(link).to_be_focused()
            _assert_link_sits_inside_card(link)
        assert_no_horizontal_overflow(page)

        page.goto(_detail_url(live_server, course))
        stat = page.get_by_test_id("price-stat")
        expect(stat).to_be_visible()
        stat_box = _box(stat)
        price_box = _box(stat.get_by_test_id("course-price"))
        assert price_box["x"] + price_box["width"] <= stat_box["x"] + stat_box["width"]
        assert_no_horizontal_overflow(page)

        if viewport["width"] == 375:
            title_span = page.get_by_role("navigation", name="Course outline").locator(
                "span.truncate", has_text=LONG_TOPIC_TITLE
            )
            expect(title_span).to_have_count(1)
            # The row fits because the title is clipped, not because it fit.
            assert title_span.evaluate("el => el.scrollWidth > el.clientWidth")

    # Below md the stat cells stack, each spanning the strip so dividers line up.
    for width in (375, 640):
        page.set_viewport_size({"width": width, "height": 900})
        page.goto(_detail_url(live_server, course))
        cells = page.get_by_test_id("price-stat").locator("xpath=../*")
        expect(cells.first).to_be_visible()
        boxes = [_box(cells.nth(i)) for i in range(cells.count())]
        assert len(boxes) >= 2
        assert len({round(box["x"] + box["width"]) for box in boxes}) == 1


def test_mobile_outline_sheet_and_drawer_stay_within_the_viewport(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
) -> None:
    page = logged_in_page
    organisation = OrganisationFactory(name="Acme Corp", logo=_logo_upload())
    course = CourseFactory(title="Tall Course", slug="tall-course")
    LearnerCourseRegistrationFactory(
        learner__user=logged_in_user,
        learner__organisation=organisation,
        course=course,
        is_active=True,
    )
    # Comfortably past 85vh at this viewport, so the clamp has to engage.
    for order in range(20):
        ContentCollectionItemFactory(
            collection_object=course,
            child_object=TopicFactory(
                title=f"Topic {order:02d}", slug=f"topic-{order:02d}"
            ),
            order=order,
        )

    # A sheet taller than the screen clamps and scrolls rather than running off
    # the top, taking the first thing in the panel with it.
    viewport_height = 812
    page.set_viewport_size({"width": 375, "height": viewport_height})
    page.goto(_item_url(live_server, course, 1))
    sheet = page.get_by_role("dialog", name="Course outline")
    page.get_by_role("button", name="Open course outline").click()
    expect(sheet).to_be_visible()
    # The sheet slides up on open; measuring mid-flight reads a transient offset.
    expect(sheet).to_have_css("transform", "none")
    sheet_box = _box(sheet)
    assert sheet_box["y"] >= 0
    assert sheet_box["height"] <= viewport_height * 0.85 + 1
    chip_box = _box(page.locator("#course-organisation-chip"))
    assert chip_box["y"] >= 0
    assert chip_box["y"] + chip_box["height"] <= viewport_height
    # The overflow the clamp creates has somewhere to go.
    assert page.locator(".side-panel-body").evaluate(
        "el => el.scrollHeight > el.clientHeight"
    )

    # The drawer presentation caps at 24rem instead of taking 80% of the screen.
    # No shipped page selects it, so the variant is switched on the element.
    page.keyboard.press("Escape")
    expect(sheet).to_be_hidden()
    page.set_viewport_size({"width": 900, "height": 812})
    dialog = page.locator(".side-panel-dialog")
    dialog.evaluate("el => el.setAttribute('data-variant', 'side-drawer')")
    page.get_by_role("button", name="Open course outline").click()
    expect(dialog).to_be_visible()
    expect(dialog).to_have_css("transform", "none")
    assert dialog.evaluate("el => getComputedStyle(el).maxWidth") == "384px"
    drawer_box = _box(dialog)
    assert drawer_box["width"] <= 384
    # It is the cap doing the work, not a narrow viewport.
    assert drawer_box["width"] < 900 * 0.8


@pytest.mark.skipif(
    app_not_installed("freedom_ls.blog"), reason="the article card needs the blog"
)
def test_learner_browses_a_grid_of_article_and_course_cards(
    live_server,
    page: Page,
    live_server_site,
    mock_site_context,
) -> None:
    ArticleFactory(
        title="Card Target Article",
        slug="card-target-article",
        file_path="articles/card.md",
    )
    CourseFactory(
        title="Alpha Course",
        slug="alpha-course",
        file_path="courses/alpha/course.md",
        description="A course description long enough to wrap on a phone screen.",
        access_config={"access_type": "free"},
    )
    host = ArticleFactory(
        title="Host Article",
        slug="host-article",
        file_path="articles/host.md",
        content=(
            "<c-grid>\n"
            '<c-article-card path="../articles/card.md"></c-article-card>\n'
            '<c-course-card path="../courses/alpha/course.md"></c-course-card>\n'
            "</c-grid>"
        ),
    )
    host_url = str(
        reverse_url(live_server, "blog:article_detail", kwargs={"slug": host.slug})
    )

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(host_url)
        for title in ("Alpha Course", "Card Target Article"):
            link = page.get_by_role("link", name=title)
            expect(link).to_be_visible()
            link.focus()
            expect(link).to_be_focused()
            _assert_link_sits_inside_card(link)
        assert_no_horizontal_overflow(page)

        _click_card_corner(
            _card_of(page.get_by_role("link", name="Card Target Article"))
        )
        expect(page).to_have_url(
            reverse_url(
                live_server,
                "blog:article_detail",
                kwargs={"slug": "card-target-article"},
            )
        )
        page.goto(host_url)
        _click_card_corner(_card_of(page.get_by_role("link", name="Alpha Course")))
        expect(page).to_have_url(
            reverse_url(
                live_server,
                "learner_interface:course_detail",
                kwargs={"course_slug": "alpha-course"},
            )
        )
