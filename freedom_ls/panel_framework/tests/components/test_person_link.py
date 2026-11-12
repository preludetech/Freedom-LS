"""Tests for the <c-panel-person-link /> cotton component."""

from __future__ import annotations

import lxml.html
import pytest

from ..cotton_helpers import render_cotton


@pytest.mark.parametrize("href", ["", ' href="/people/42"'])
def test_picture_url_reaches_the_avatar_chip(href: str) -> None:
    html = render_cotton(
        f'<c-panel-person-link name="Thandi Mokoena" user_id="42"{href} '
        'picture_url="/media/me.webp" />'
    )

    (image,) = lxml.html.fromstring(html).cssselect("img[data-profile-picture]")

    assert image.get("src") == "/media/me.webp"


def test_without_a_picture_url_the_chip_has_no_image() -> None:
    html = render_cotton('<c-panel-person-link name="Thandi Mokoena" user_id="42" />')

    assert not lxml.html.fromstring(html).cssselect("img")


def test_with_an_href_the_chip_and_name_are_one_row_style_link() -> None:
    html = render_cotton(
        '<c-panel-person-link name="Thandi Mokoena" user_id="42" href="/people/42" />'
    )

    root = lxml.html.fromstring(html)
    links = root.findall(".//a")

    assert len(links) == 1
    classes = set(links[0].get("class", "").split())
    assert {"no-underline", "text-on-surface", "font-bold"} <= classes
    assert "underline" not in classes
    assert "text-primary" not in classes
    assert "Thandi Mokoena" in links[0].text_content()


def test_without_an_href_nothing_is_a_link() -> None:
    html = render_cotton('<c-panel-person-link name="Thandi Mokoena" user_id="42" />')

    root = lxml.html.fromstring(html)

    assert root.findall(".//a") == []
    assert "Thandi Mokoena" in root.text_content()


def test_a_quick_view_url_adds_one_labelled_drawer_trigger() -> None:
    html = render_cotton(
        '<c-panel-person-link name="Thandi Mokoena" user_id="42" '
        'href="/people/42" quick_view_url="/people/42/__quick-view" />'
    )

    root = lxml.html.fromstring(html)
    triggers = root.xpath('.//a[@aria-controls="quick-view"]')

    assert len(triggers) == 1
    assert triggers[0].get("aria-label") == "Quick view: Thandi Mokoena"
    assert triggers[0].get("hx-get") == "/people/42/__quick-view"


def test_hx_nav_makes_the_link_swap_into_main_content() -> None:
    html = render_cotton(
        '<c-panel-person-link name="Thandi Mokoena" user_id="42" href="/people/42" hx_nav="true" />'
    )

    link = lxml.html.fromstring(html).findall(".//a")[0]

    assert link.get("hx-get") == "/people/42"
    assert link.get("hx-target") == "#main-content"
    assert link.get("hx-push-url") == "true"
    assert link.get("hx-swap") == "outerHTML"
