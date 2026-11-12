"""Tests for the <c-panel-heading /> cotton component."""

from __future__ import annotations

import lxml.html

from ..cotton_helpers import render_cotton


def test_the_default_element_is_an_h3() -> None:
    heading = lxml.html.fromstring(
        render_cotton("<c-panel-heading>Staff</c-panel-heading>")
    )

    assert heading.tag == "h3"
    assert heading.text == "Staff"


def test_the_tag_attribute_picks_the_element() -> None:
    heading = lxml.html.fromstring(
        render_cotton('<c-panel-heading tag="h2">Staff</c-panel-heading>')
    )

    assert heading.tag == "h2"


def test_other_attributes_land_on_the_heading() -> None:
    heading = lxml.html.fromstring(
        render_cotton('<c-panel-heading id="staff-title">Staff</c-panel-heading>')
    )

    assert heading.get("id") == "staff-title"
