"""Tests for the <c-panel-avatar-chip /> cotton component."""

from __future__ import annotations

import re

import lxml.html
import pytest

from ..cotton_helpers import render_cotton


def _circle(html: str) -> lxml.html.HtmlElement:
    (circle,) = lxml.html.fromstring(html).cssselect("[aria-hidden='true']")
    return circle


@pytest.mark.parametrize(("size", "pixels"), [("sm", "24"), ("md", "32"), ("lg", "52")])
def test_picture_url_puts_a_sized_image_in_the_circle_over_the_initials(
    size: str, pixels: str
) -> None:
    html = render_cotton(
        f'<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" size="{size}" '
        'picture_url="/media/me.webp" />'
    )

    circle = _circle(html)
    (image,) = circle.cssselect("img[data-profile-picture]")

    assert image.get("src") == "/media/me.webp"
    assert image.get("alt") == ""
    assert image.get("loading") == "lazy"
    assert image.get("width") == pixels
    assert image.get("height") == pixels
    assert circle.text_content().strip() == "TM"


@pytest.mark.parametrize(
    "source",
    [
        '<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" picture_url="" />',
        '<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" />',
    ],
)
def test_without_a_picture_url_there_is_no_image(source: str) -> None:
    circle = _circle(render_cotton(source))

    assert not circle.cssselect("img")
    assert circle.text_content().strip() == "TM"


@pytest.mark.parametrize("picture_url", ["", "/media/me.webp"])
def test_the_circle_is_aria_hidden_and_keeps_its_colour_slot(
    picture_url: str,
) -> None:
    circle = _circle(
        render_cotton(
            '<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" '
            ':picture_url="picture_url" />',
            picture_url=picture_url,
        )
    )

    assert circle.get("aria-hidden") == "true"
    assert "panel-avatar-" in circle.get("class")


def test_a_none_picture_url_renders_no_image() -> None:
    html = render_cotton(
        '<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" '
        ':picture_url="picture_url" />',
        picture_url=None,
    )

    assert "None" not in html
    assert not _circle(html).cssselect("img")


def test_initials_element_is_aria_hidden_and_holds_the_derived_initials() -> None:
    html = render_cotton('<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" />')

    match = re.search(r'<span aria-hidden="true"[^>]*>([^<]*)</span>', html)

    assert match is not None
    assert match.group(1) == "TM"


def test_name_is_visible_text_outside_the_initials_element() -> None:
    html = render_cotton('<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" />')

    initials_end = html.index("</span>")

    assert "Thandi Mokoena" in html[initials_end:]


def test_initials_attribute_overrides_the_derived_initials() -> None:
    html = render_cotton(
        '<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" initials="ZZ" />'
    )

    match = re.search(r'<span aria-hidden="true"[^>]*>([^<]*)</span>', html)

    assert match is not None
    assert match.group(1) == "ZZ"


def test_secondary_renders_when_given() -> None:
    html = render_cotton(
        '<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" secondary="Learner" />'
    )

    assert "Learner" in html


def test_name_hidden_renders_the_initials_and_no_name_text() -> None:
    html = render_cotton(
        '<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" name_hidden="true" />'
    )

    assert "Thandi Mokoena" not in html
    match = re.search(r'<span aria-hidden="true"[^>]*>([^<]*)</span>', html)
    assert match is not None
    assert match.group(1) == "TM"


def test_name_is_escaped() -> None:
    html = render_cotton(
        '<c-panel-avatar-chip name="<script>alert(1)</script>" user_id="42" />'
    )

    assert "<script>alert(1)</script>" not in html


def test_name_hidden_false_string_shows_the_name() -> None:
    html = render_cotton(
        '<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" name_hidden="False" />'
    )

    assert "Thandi Mokoena</span>" in html
