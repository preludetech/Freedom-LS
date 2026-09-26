"""Tab dispatch: every tab has a URL that renders the full page, and a tab
click swaps only that tab's content."""

from __future__ import annotations

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.http import Http404

from .conftest import _make_stub
from .view_helpers import fetch

pytestmark = pytest.mark.django_db


def _tab_links(html: str) -> dict[str, lxml.html.HtmlElement]:
    document = lxml.html.fromstring(html)
    return {
        link.text_content().strip(): link
        for link in document.cssselect("[data-panel=''] > nav a")
    }


def _tab_region_id(stub_pk: object) -> str:
    html = fetch(f"stubs/{stub_pk}").content.decode()
    (region,) = lxml.html.fromstring(html).cssselect("[data-tab-set]")
    return str(region.get("id"))


def test_the_instance_url_shows_the_first_tab_as_current(
    mock_site_context: Site,
) -> None:
    stub = _make_stub(name="Tabbed Stub")

    links = _tab_links(fetch(f"stubs/{stub.pk}").content.decode())

    assert links["Stub"].get("aria-current") == "page"
    assert links["Details"].get("aria-current") is None


def test_a_hidden_tab_has_no_link(mock_site_context: Site) -> None:
    stub = _make_stub(name="Tabbed Stub")

    links = _tab_links(fetch(f"stubs/{stub.pk}").content.decode())

    assert set(links) == {"Stub", "Details"}


def test_a_plain_get_of_a_tab_url_renders_the_full_page_with_that_tab_current(
    mock_site_context: Site,
) -> None:
    stub = _make_stub(name="Tabbed Stub")

    response = fetch(f"stubs/{stub.pk}/__tabs/details")

    html = response.content.decode()
    assert 'id="sidebar-nav"' in html
    assert _tab_links(html)["Details"].get("aria-current") == "page"
    assert "<p data-stub-details>Tabbed Stub</p>" in html


def test_tab_links_push_their_own_url_into_the_tab_region(
    mock_site_context: Site,
) -> None:
    stub = _make_stub(name="Tabbed Stub")
    region_id = _tab_region_id(stub.pk)

    link = _tab_links(fetch(f"stubs/{stub.pk}").content.decode())["Details"]

    url = f"/test-panel/framework/stubs/{stub.pk}/__tabs/details"
    assert link.get("href") == url
    assert link.get("hx-get") == url
    assert link.get("hx-target") == f"#{region_id}"
    assert link.get("hx-push-url") == "true"


def test_a_tab_click_returns_that_tab_and_an_announcement(
    mock_site_context: Site,
) -> None:
    stub = _make_stub(name="Tabbed Stub")

    response = fetch(
        f"stubs/{stub.pk}/__tabs/details",
        htmx=True,
        hx_target=_tab_region_id(stub.pk),
    )

    html = response.content.decode()
    assert "<p data-stub-details>Tabbed Stub</p>" in html
    assert 'hx-swap-oob="innerHTML:#scope-announcer"' in html
    assert "Showing Details" in html
    assert 'id="sidebar-nav"' not in html
    assert "<nav" not in html


def test_a_history_restore_of_a_tab_url_returns_the_full_page(
    mock_site_context: Site,
) -> None:
    stub = _make_stub(name="Tabbed Stub")

    response = fetch(f"stubs/{stub.pk}/__tabs/details", htmx=True, restore=True)

    html = response.content.decode()
    assert 'id="sidebar-nav"' in html
    assert _tab_links(html)["Details"].get("aria-current") == "page"


def test_a_panel_inside_a_tab_renders_that_panel(mock_site_context: Site) -> None:
    stub = _make_stub(name="row-in-tab")

    response = fetch(f"stubs/{stub.pk}/__tabs/default")

    assert "row-in-tab" in response.content.decode()


@pytest.mark.parametrize(
    "suffix",
    ["__tabs/hidden", "__tabs/no-such-tab", "__tabs", "__panels/default"],
    ids=["hidden tab", "unknown tab", "missing tab name", "wrong child segment"],
)
def test_unreachable_tab_paths_404(mock_site_context: Site, suffix: str) -> None:
    stub = _make_stub(name="Tabbed Stub")

    with pytest.raises(Http404):
        fetch(f"stubs/{stub.pk}/{suffix}")
