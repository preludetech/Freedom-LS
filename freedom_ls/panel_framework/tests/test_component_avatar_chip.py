"""Tests for the <c-panel-avatar-chip /> cotton component."""

from __future__ import annotations

import re

from .cotton_helpers import render_cotton


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


def test_no_secondary_line_when_not_given() -> None:
    html = render_cotton('<c-panel-avatar-chip name="Thandi Mokoena" user_id="42" />')

    assert "text-muted" not in html


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
