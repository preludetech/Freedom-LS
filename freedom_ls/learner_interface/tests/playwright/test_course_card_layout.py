from typing import cast

import pytest
from playwright.sync_api import Locator, Page, expect

from freedom_ls.conftest import reverse_url
from freedom_ls.content_engine.factories import ArticleFactory, CourseFactory
from freedom_ls.content_engine.models import Article
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.blog"):
    pytest.skip("blog not installed", allow_module_level=True)

VIEWPORTS = pytest.mark.parametrize(
    ("width", "height"),
    [(375, 812), (768, 1024), (1280, 800)],
    ids=["mobile", "tablet", "desktop"],
)

MIXED_GRID = """
<c-grid>
<c-article-card path="../articles/card.md"></c-article-card>
<c-course-card path="../courses/alpha/course.md"></c-course-card>
<c-course-card path="../courses/beta/course.md" variant="compact"></c-course-card>
</c-grid>
"""


@pytest.fixture
def mixed_grid_article(mock_site_context) -> Article:
    """An article whose content grids an article card and two course cards."""
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
    CourseFactory(
        title="Beta Course With A Rather Long Title To Force Wrapping",
        slug="beta-course",
        file_path="courses/beta/course.md",
        access_config={"access_type": "free"},
    )
    return cast(
        "Article",
        ArticleFactory(
            title="Host Article",
            slug="host-article",
            file_path="articles/host.md",
            content=MIXED_GRID,
        ),
    )


def _open_host(live_server, page: Page, article: Article) -> None:
    page.goto(
        reverse_url(live_server, "blog:article_detail", kwargs={"slug": article.slug})
    )


def _card_of(link: Locator) -> Locator:
    return link.locator(
        "xpath=ancestor::*[self::article or contains(@class, 'surface')][1]"
    )


@VIEWPORTS
@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_mixed_card_grid_does_not_overflow_the_viewport(
    live_server, live_server_site, mixed_grid_article, page: Page, width, height
):
    page.set_viewport_size({"width": width, "height": height})
    _open_host(live_server, page, mixed_grid_article)

    expect(page.get_by_role("link", name="Alpha Course")).to_be_visible()
    expect(page.get_by_role("link", name="Card Target Article")).to_be_visible()
    assert not page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
    )


@VIEWPORTS
@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_clicking_a_course_card_away_from_its_title_opens_the_course(
    live_server, live_server_site, mixed_grid_article, page: Page, width, height
):
    page.set_viewport_size({"width": width, "height": height})
    _open_host(live_server, page, mixed_grid_article)

    card = _card_of(page.get_by_role("link", name="Alpha Course"))
    box = card.bounding_box()
    assert box is not None
    card.click(position={"x": box["width"] - 6, "y": box["height"] - 6})

    expect(page).to_have_url(
        reverse_url(
            live_server,
            "learner_interface:course_detail",
            kwargs={"course_slug": "alpha-course"},
        )
    )


@VIEWPORTS
@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_clicking_an_article_card_in_the_mixed_grid_opens_the_article(
    live_server, live_server_site, mixed_grid_article, page: Page, width, height
):
    page.set_viewport_size({"width": width, "height": height})
    _open_host(live_server, page, mixed_grid_article)

    card = _card_of(page.get_by_role("link", name="Card Target Article"))
    box = card.bounding_box()
    assert box is not None
    card.click(position={"x": box["width"] - 6, "y": box["height"] - 6})

    expect(page).to_have_url(
        reverse_url(
            live_server, "blog:article_detail", kwargs={"slug": "card-target-article"}
        )
    )


@VIEWPORTS
@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("title", ["Alpha Course", "Beta Course With"])
def test_focused_card_link_sits_inside_its_card(
    live_server, live_server_site, mixed_grid_article, page: Page, width, height, title
):
    page.set_viewport_size({"width": width, "height": height})
    _open_host(live_server, page, mixed_grid_article)

    link = page.get_by_role("link", name=title)
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
