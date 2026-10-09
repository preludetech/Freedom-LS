"""Browser flow for reading the blog: the index, an article and its pictures.

What only a browser shows is covered here: a card's whole area acting as its
link, the picture lightbox, and layout at real widths (overflow, the focused
link staying inside its card, and cards and pictures sharing a row's height).
"""

from __future__ import annotations

import base64
import re
from datetime import date

import pytest
from playwright.sync_api import Locator, Page, expect

from django.core.files.base import ContentFile

from freedom_ls.conftest import reverse_url
from freedom_ls.content_engine.factories import ArticleFactory, FileFactory
from freedom_ls.content_engine.models import Article
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

HOST_CONTENT = """
<c-grid>
<c-article-card path="../articles/first.md"></c-article-card>
<c-article-card path="../articles/second.md" variant="compact"></c-article-card>
<c-article-card path="../articles/third.md"></c-article-card>
</c-grid>
<c-grid columns="2">
<c-article-card path="../articles/row.md"></c-article-card>
<c-picture src="../images/cat.png" alt="A cat" title="Cat" />
</c-grid>
"""

LONG_TITLE = "Another Plain Article With A Rather Long Title To Force Wrapping"
# Articles that sort ahead of the host's cards, so the first index row holds
# exactly these three.
FIRST_ROW_TITLES = ("Illustrated Article", "Plain Article", LONG_TITLE)
# The host's own cards, dated earlier so they sort after the first row.
EARLIER = date(2026, 1, 1)


def _card_of(link: Locator) -> Locator:
    return link.locator("xpath=ancestor::article[1]")


def _height_of(card: Locator) -> float:
    box = card.bounding_box()
    assert box is not None
    return box["height"]


@pytest.fixture
def blog(mock_site_context) -> Article:
    """An index of cards plus a host article gridding cards and a picture."""
    FileFactory(
        file_path="images/cat.png",
        original_filename="cat.png",
        file_type="image",
        file=ContentFile(PNG_BYTES, name="cat.png"),
    )
    FileFactory(
        file_path="articles/photo.png",
        original_filename="photo.png",
        file_type="image",
        file=ContentFile(PNG_BYTES, name="photo.png"),
    )
    ArticleFactory(
        title="Illustrated Article",
        slug="illustrated-article",
        description="A description long enough to wrap onto several lines in a card.",
        file_path="articles/illustrated.md",
        image="photo.png",
        image_alt="A grey square",
        published_on=date(2026, 3, 3),
    )
    ArticleFactory(
        title="Plain Article",
        slug="plain-article",
        file_path="articles/plain.md",
        published_on=date(2026, 3, 2),
    )
    ArticleFactory(
        title=LONG_TITLE,
        slug="another-plain-article",
        file_path="articles/another.md",
        published_on=date(2026, 3, 1),
    )
    ArticleFactory(
        title="First Card Article",
        slug="first-card-article",
        description="A description long enough to wrap onto several lines on a phone.",
        file_path="articles/first.md",
        published_on=EARLIER,
    )
    ArticleFactory(
        title="Second Card Article",
        slug="second-card-article",
        file_path="articles/second.md",
        published_on=EARLIER,
    )
    ArticleFactory(
        title="Third Card Article With A Rather Long Title To Force Wrapping",
        slug="third-card-article",
        file_path="articles/third.md",
        published_on=EARLIER,
    )
    ArticleFactory(
        title="Row Card Article",
        slug="row-card-article",
        file_path="articles/row.md",
        published_on=EARLIER,
    )
    host: Article = ArticleFactory(
        title="Host Article",
        slug="host-article",
        file_path="articles/host.md",
        content=HOST_CONTENT,
        published_on=EARLIER,
    )
    return host


def test_reading_the_blog(live_server, blog: Article, page: Page) -> None:
    index_url = reverse_url(live_server, "blog:index")
    article_url = reverse_url(
        live_server, "blog:article_detail", kwargs={"slug": blog.slug}
    )

    # Clicking a card away from its title opens the article.
    page.goto(index_url)
    card = _card_of(page.get_by_role("link", name="Host Article", exact=True))
    box = card.bounding_box()
    assert box is not None
    card.click(position={"x": box["width"] - 6, "y": box["height"] - 6})
    expect(page).to_have_url(article_url)

    # Expanding a picture opens the lightbox.
    page.get_by_role("button", name="Expand").click()
    expect(page.get_by_role("dialog", name="Cat")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog", name="Cat")).to_be_hidden()

    # A card inside the article reaches its own article from a corner too.
    first = _card_of(page.get_by_role("link", name="First Card Article"))
    first_box = first.bounding_box()
    assert first_box is not None
    first.click(position={"x": first_box["width"] - 6, "y": first_box["height"] - 6})
    expect(page).to_have_url(re.compile(r"/first-card-article/?$"))

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        _check_layout(page, index_url, article_url, viewport["width"])


def _check_layout(page: Page, index_url: str, article_url: str, width: int) -> None:
    page.goto(index_url)
    expect(page.get_by_role("link", name="Host Article")).to_be_visible()
    assert_no_horizontal_overflow(page)
    if width >= 1280:
        heights = {
            _height_of(_card_of(page.get_by_role("link", name=title, exact=True)))
            for title in FIRST_ROW_TITLES
        }
        assert len(heights) == 1

    page.goto(article_url)
    expect(page.get_by_role("link", name="First Card Article")).to_be_visible()
    expect(page.get_by_role("link", name="Second Card Article")).to_be_visible()
    assert_no_horizontal_overflow(page)

    # Keyboard focus on a card's link stays inside the card.
    link = page.get_by_role("link", name="Second Card Article")
    for _ in range(40):
        page.keyboard.press("Tab")
        if link.evaluate("el => el === document.activeElement"):
            break
    expect(link).to_be_focused()
    link_box = link.bounding_box()
    card_box = _card_of(link).bounding_box()
    assert link_box is not None
    assert card_box is not None
    assert link_box["x"] >= card_box["x"]
    assert link_box["y"] >= card_box["y"]
    assert link_box["x"] + link_box["width"] <= card_box["x"] + card_box["width"]
    assert link_box["y"] + link_box["height"] <= card_box["y"] + card_box["height"]

    # A card and a picture in one grid row share their top and height.
    if width == 768:
        row_card = _card_of(
            page.get_by_role("link", name="Row Card Article")
        ).bounding_box()
        picture = page.locator("[x-data='contentLightbox']").bounding_box()
        assert row_card is not None
        assert picture is not None
        assert picture["y"] == row_card["y"]
        assert picture["height"] == row_card["height"]
