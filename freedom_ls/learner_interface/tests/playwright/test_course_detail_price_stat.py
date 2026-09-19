from decimal import Decimal

import pytest
from playwright.sync_api import Page, expect

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import PriceKind

from ..conftest import reverse_url


@pytest.mark.parametrize(
    ("width", "height"),
    [(375, 812), (768, 1024), (1920, 1080)],
    ids=["mobile", "tablet", "desktop"],
)
@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_long_price_stays_inside_its_stat_cell(
    live_server,
    live_server_site,
    mock_site_context,
    page: Page,
    width,
    height,
):
    """A discounted price is the widest compact price, and must not spill into the next cell."""
    course = CourseFactory(
        title="Price Stat Course",
        slug="price-stat-course",
        access_config={"access_type": "free"},
        price_kind=PriceKind.DISCOUNTED,
        price_amount=Decimal("1499.00"),
        price_sale_amount=Decimal("999.00"),
        price_currency="ZAR",
    )

    page.set_viewport_size({"width": width, "height": height})
    page.goto(
        reverse_url(
            live_server,
            "learner_interface:course_detail",
            kwargs={"course_slug": course.slug},
        )
    )

    stat = page.get_by_test_id("price-stat")
    expect(stat).to_be_visible()
    stat_box = stat.bounding_box()
    price_box = stat.get_by_test_id("course-price").bounding_box()
    assert stat_box is not None
    assert price_box is not None

    assert price_box["x"] + price_box["width"] <= stat_box["x"] + stat_box["width"]


@pytest.mark.parametrize("width", [375, 640], ids=["mobile", "small-tablet"])
@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_stacked_stat_cells_share_one_width_below_md(
    live_server,
    live_server_site,
    mock_site_context,
    page: Page,
    width,
):
    """When the stats stack, every cell spans the strip, so the dividers line up.

    640px is wide enough for two cells but not three with a discounted price,
    so it guards against a ragged two-then-one wrap.
    """
    course = CourseFactory(
        title="Stacked Stats Course",
        slug="stacked-stats-course",
        access_config={"access_type": "free"},
        price_kind=PriceKind.DISCOUNTED,
        price_amount=Decimal("1499.00"),
        price_sale_amount=Decimal("999.00"),
        price_currency="ZAR",
    )

    page.set_viewport_size({"width": width, "height": 900})
    page.goto(
        reverse_url(
            live_server,
            "learner_interface:course_detail",
            kwargs={"course_slug": course.slug},
        )
    )

    cells = page.get_by_test_id("price-stat").locator("xpath=../*")
    boxes = [cells.nth(i).bounding_box() for i in range(cells.count())]
    assert len(boxes) >= 2
    assert all(box is not None for box in boxes)

    right_edges = {round(box["x"] + box["width"]) for box in boxes if box}
    assert len(right_edges) == 1
