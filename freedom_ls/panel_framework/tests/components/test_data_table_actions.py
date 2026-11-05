"""Tests for the <c-data-table-actions /> cotton component."""

from __future__ import annotations

import lxml.html

from ..cotton_helpers import render_cotton


def test_the_wrapper_lays_its_buttons_out_with_a_gap_and_wraps() -> None:
    html = render_cotton(
        '<c-data-table-actions class="mt-2"><button>A</button><button>B</button></c-data-table-actions>'
    )

    wrapper = lxml.html.fromstring(html)
    classes = set(wrapper.get("class", "").split())

    assert {"flex", "flex-wrap", "gap-2", "mt-2"} <= classes
    assert [button.text for button in wrapper.findall("button")] == ["A", "B"]
