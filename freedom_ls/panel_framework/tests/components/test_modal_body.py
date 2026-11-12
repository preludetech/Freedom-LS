"""Tests for the <c-modal-body /> and <c-modal-header /> cotton components."""

from __future__ import annotations

import lxml.html

from ..cotton_helpers import render_cotton


def test_the_body_owns_its_padding_and_the_gap_between_blocks() -> None:
    body = lxml.html.fromstring(
        render_cotton("<c-modal-body><p>One</p><p>Two</p></c-modal-body>")
    )

    classes = set(body.get("class", "").split())

    assert body.tag == "div"
    assert {"px-6", "py-5", "space-y-4", "text-sm"} <= classes
    assert [p.text for p in body.findall("p")] == ["One", "Two"]


def test_the_header_has_a_close_control_by_default() -> None:
    header = lxml.html.fromstring(
        render_cotton("<c-modal-header>Title</c-modal-header>")
    )

    assert header.find("h2").get("id") == "app-modal-title"
    assert header.find("button").get("aria-label") == "Close"


def test_a_header_that_must_be_answered_drops_the_close_control() -> None:
    header = lxml.html.fromstring(
        render_cotton(
            '<c-modal-header title_id="prompt-title" closable="">Discard?</c-modal-header>'
        )
    )

    assert header.find("h2").get("id") == "prompt-title"
    assert header.find("button") is None


def test_it_renders_its_slot() -> None:
    html = render_cotton("<c-modal-body><p>Hello</p></c-modal-body>")

    body = lxml.html.fromstring(html)
    assert body.find("p").text == "Hello"


def test_a_class_passes_through() -> None:
    html = render_cotton('<c-modal-body class="max-w-prose">x</c-modal-body>')

    assert "max-w-prose" in lxml.html.fromstring(html).get("class")


def test_other_attributes_pass_through() -> None:
    html = render_cotton('<c-modal-body data-probe="1">x</c-modal-body>')

    assert lxml.html.fromstring(html).get("data-probe") == "1"
