"""Tests for the <c-quick-view-trigger /> cotton component."""

from freedom_ls.panel_framework.tests.cotton_helpers import render_cotton


class TestQuickViewTrigger:
    """<c-quick-view-trigger /> is a link that loads its url into the quick view."""

    def test_anchor_links_to_the_full_page(self) -> None:
        result = render_cotton(
            '<c-quick-view-trigger href="/full/" url="/frame/">Ada</c-quick-view-trigger>'
        )
        assert 'href="/full/"' in result
        assert "Ada" in result

    def test_anchor_loads_the_url_into_the_quick_view_body(self) -> None:
        result = render_cotton(
            '<c-quick-view-trigger href="/full/" url="/frame/">Ada</c-quick-view-trigger>'
        )
        assert 'hx-get="/frame/"' in result
        assert 'hx-target="#quick-view-body"' in result
