"""Tests for the <c-panel-callout /> cotton component."""

from __future__ import annotations

import re

import lxml.html
import pytest

from ..cotton_helpers import render_cotton, render_framework_default

TONES = ["info", "success", "warning", "error"]


def _default(attrs: str = "", slot: str = "Careful") -> lxml.html.HtmlElement:
    return lxml.html.fromstring(
        render_framework_default(f"<c-panel-callout {attrs}>{slot}</c-panel-callout>")
    )


def _classes(element: lxml.html.HtmlElement) -> list[str]:
    return (element.get("class") or "").split()


def _normalised(html: str) -> str:
    """Serialise parsed HTML with runs of whitespace collapsed."""
    markup = lxml.html.tostring(lxml.html.fromstring(html), encoding="unicode")
    return re.sub(r"\s+", " ", markup).replace("> <", "><").strip()


def test_the_framework_default_renders_without_a_callout_class() -> None:
    """The first test proves the framework file rendered, not the host wrapper."""
    box = _default()

    assert "callout" not in " ".join(box.xpath("descendant-or-self::*/@class"))
    assert "Careful" in box.text_content()


@pytest.mark.parametrize("tone", TONES)
def test_framework_default_tints_each_tone_from_theme_tokens(tone: str) -> None:
    classes = _classes(_default(f'tone="{tone}"'))

    assert f"bg-{tone}/10" in classes
    assert f"border-{tone}/20" in classes


@pytest.mark.parametrize("tone", TONES)
def test_framework_default_shows_a_decorative_tone_icon(tone: str) -> None:
    icons = _default(f'tone="{tone}"').xpath("//svg")

    assert len(icons) == 1
    assert icons[0].get("aria-hidden") == "true"


@pytest.mark.parametrize(
    ("tone", "role"),
    [("info", None), ("warning", None), ("error", "alert"), ("success", "status")],
)
def test_framework_default_gives_each_tone_its_role(
    tone: str, role: str | None
) -> None:
    assert _default(f'tone="{tone}"').get("role") == role


def test_framework_default_renders_an_unknown_tone_as_info() -> None:
    box = _default('tone="bogus"')

    assert "bg-info/10" in _classes(box)
    assert box.get("role") is None


def test_framework_default_passes_attributes_through() -> None:
    box = _default('data-testid="x" data-error-summary class="mt-4"')

    assert box.get("data-testid") == "x"
    assert box.get("data-error-summary") is not None
    assert "mt-4" in _classes(box)


def test_framework_default_renders_the_title_escaped_once() -> None:
    html = render_framework_default(
        '<c-panel-callout title="We couldn\'t save">x</c-panel-callout>'
    )

    assert "We couldn&#x27;t save" in html or "We couldn't save" in html
    assert "&amp;" not in html


@pytest.mark.needs_fls_host
@pytest.mark.parametrize("tone", TONES)
def test_under_fls_panel_callout_renders_the_same_html_as_callout(tone: str) -> None:
    attrs = f'tone="{tone}" title="We couldn\'t save" class="mt-4" data-testid="x"'

    panel = render_cotton(f"<c-panel-callout {attrs}>Body</c-panel-callout>")
    host = render_cotton(f"<c-callout {attrs}>Body</c-callout>")

    assert _normalised(panel) == _normalised(host)
