import base64
from datetime import date
from typing import cast

import pytest
from playwright.sync_api import Locator, Page, expect

from django.core.files.base import ContentFile

from freedom_ls.conftest import reverse_url
from freedom_ls.content_engine.factories import ArticleFactory, FileFactory
from freedom_ls.content_engine.models import Article

VIEWPORTS = pytest.mark.parametrize(
    ("width", "height"),
    [(375, 812), (768, 1024), (1280, 800)],
    ids=["mobile", "tablet", "desktop"],
)

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

GRID_OF_ARTICLE_CARDS = """
<c-grid>
<c-article-card path="../articles/first.md"></c-article-card>
<c-article-card path="../articles/second.md" variant="compact"></c-article-card>
<c-article-card path="../articles/third.md"></c-article-card>
</c-grid>
"""


@pytest.fixture
def grid_article(mock_site_context) -> Article:
    """An article whose content grids three article cards, plus the cards' targets."""
    ArticleFactory(
        title="First Card Article",
        slug="first-card-article",
        description="A description long enough to wrap onto several lines on a phone.",
        file_path="articles/first.md",
    )
    ArticleFactory(
        title="Second Card Article",
        slug="second-card-article",
        file_path="articles/second.md",
    )
    ArticleFactory(
        title="Third Card Article With A Rather Long Title To Force Wrapping",
        slug="third-card-article",
        file_path="articles/third.md",
    )
    return cast(
        "Article",
        ArticleFactory(
            title="Host Article",
            slug="host-article",
            file_path="articles/host.md",
            content=GRID_OF_ARTICLE_CARDS,
        ),
    )


def factory_png() -> ContentFile:
    return ContentFile(PNG_BYTES, name="cat.png")


def _overflows(page: Page) -> bool:
    return cast(
        "bool",
        page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        ),
    )


def _card_of(link: Locator) -> Locator:
    return link.locator("xpath=ancestor::article[1]")


@VIEWPORTS
@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_index_does_not_overflow_the_viewport(
    live_server, live_server_site, grid_article, page: Page, width, height
):
    page.set_viewport_size({"width": width, "height": height})
    page.goto(reverse_url(live_server, "blog:index"))

    expect(page.get_by_role("link", name="Host Article")).to_be_visible()
    assert _overflows(page) is False


@VIEWPORTS
@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_article_with_card_grid_does_not_overflow_the_viewport(
    live_server, live_server_site, grid_article, page: Page, width, height
):
    page.set_viewport_size({"width": width, "height": height})
    page.goto(
        reverse_url(
            live_server, "blog:article_detail", kwargs={"slug": grid_article.slug}
        )
    )

    expect(page.get_by_role("link", name="First Card Article")).to_be_visible()
    expect(page.get_by_role("link", name="Second Card Article")).to_be_visible()
    assert _overflows(page) is False


@VIEWPORTS
@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_clicking_a_card_away_from_its_title_opens_the_article(
    live_server, live_server_site, grid_article, page: Page, width, height
):
    page.set_viewport_size({"width": width, "height": height})
    page.goto(
        reverse_url(
            live_server, "blog:article_detail", kwargs={"slug": grid_article.slug}
        )
    )

    card = _card_of(page.get_by_role("link", name="First Card Article"))
    box = card.bounding_box()
    assert box is not None
    card.click(position={"x": box["width"] - 6, "y": box["height"] - 6})

    expect(page).to_have_url(
        reverse_url(
            live_server, "blog:article_detail", kwargs={"slug": "first-card-article"}
        )
    )


@VIEWPORTS
@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_focused_card_link_sits_inside_its_card(
    live_server, live_server_site, grid_article, page: Page, width, height
):
    page.set_viewport_size({"width": width, "height": height})
    page.goto(
        reverse_url(
            live_server, "blog:article_detail", kwargs={"slug": grid_article.slug}
        )
    )

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


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_clicking_expand_on_an_article_picture_opens_the_lightbox(
    live_server, live_server_site, mock_site_context, page: Page
):
    FileFactory(
        file_path="images/cat.png",
        original_filename="cat.png",
        file_type="image",
        file=factory_png(),
    )
    article = ArticleFactory(
        title="Picture Article",
        slug="picture-article",
        file_path="articles/picture.md",
        content='<c-picture src="../images/cat.png" alt="A cat" title="Cat" />',
    )

    page.goto(
        reverse_url(live_server, "blog:article_detail", kwargs={"slug": article.slug})
    )
    page.get_by_role("button", name="Expand").click()

    expect(page.get_by_role("dialog", name="Cat")).to_be_visible()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_card_and_picture_in_the_same_grid_row_share_top_and_height(
    live_server, live_server_site, mock_site_context, page: Page
):
    FileFactory(
        file_path="images/cat.png",
        original_filename="cat.png",
        file_type="image",
        file=factory_png(),
    )
    ArticleFactory(
        title="Row Card Article",
        slug="row-card-article",
        file_path="articles/row.md",
    )
    host = ArticleFactory(
        title="Mixed Grid Host",
        slug="mixed-grid-host",
        file_path="articles/mixed.md",
        content=(
            '<c-grid columns="2">'
            '<c-article-card path="../articles/row.md"></c-article-card>'
            '<c-picture src="../images/cat.png" alt="A cat" title="Cat" />'
            "</c-grid>"
        ),
    )

    page.set_viewport_size({"width": 768, "height": 1024})
    page.goto(
        reverse_url(live_server, "blog:article_detail", kwargs={"slug": host.slug})
    )

    card_box = _card_of(
        page.get_by_role("link", name="Row Card Article")
    ).bounding_box()
    picture_box = page.locator("[x-data='contentLightbox']").bounding_box()
    assert card_box is not None
    assert picture_box is not None
    assert picture_box["y"] == card_box["y"]
    assert picture_box["height"] == card_box["height"]


@pytest.fixture
def index_with_one_image(mock_site_context) -> None:
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
        title="Another Plain Article With A Rather Long Title To Force Wrapping",
        slug="another-plain-article",
        file_path="articles/another.md",
        published_on=date(2026, 3, 1),
    )


@VIEWPORTS
@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_index_of_cards_does_not_overflow_the_viewport(
    live_server, live_server_site, index_with_one_image, page: Page, width, height
):
    page.set_viewport_size({"width": width, "height": height})
    page.goto(reverse_url(live_server, "blog:index"))

    expect(page.get_by_role("link", name="Illustrated Article")).to_be_visible()
    assert _overflows(page) is False


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_index_cards_in_the_first_row_share_one_height_at_desktop_width(
    live_server, live_server_site, index_with_one_image, page: Page
):
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(reverse_url(live_server, "blog:index"))

    heights = []
    for title in (
        "Illustrated Article",
        "Plain Article",
        "Another Plain Article With A Rather Long Title To Force Wrapping",
    ):
        box = _card_of(page.get_by_role("link", name=title, exact=True)).bounding_box()
        assert box is not None
        heights.append(box["height"])

    assert len(set(heights)) == 1
