"""Tests for the <c-callout /> cotton component."""

import lxml.html
import pytest
from django_cotton.compiler_regex import CottonCompiler
from lxml.html import HtmlElement

from django.template import Context, Template

_cotton_compiler = CottonCompiler()

TONES = ["info", "success", "warning", "error"]


def _render(template_string: str) -> str:
    return Template(_cotton_compiler.process(template_string)).render(Context())


def _box(template_string: str) -> HtmlElement:
    [box] = lxml.html.fromstring(f"<div>{_render(template_string)}</div>").xpath("./*")
    return box


def _svg_markup(box: HtmlElement) -> str:
    [svg] = box.xpath(".//svg")
    markup: str = lxml.html.tostring(svg, encoding="unicode")
    return markup


@pytest.mark.parametrize("tone", TONES)
def test_callout_puts_its_tone_classes_on_the_box(tone: str) -> None:
    box = _box(f'<c-callout tone="{tone}">Body</c-callout>')

    assert box.get("class").split()[:2] == ["callout", f"callout-{tone}"]


@pytest.mark.parametrize("tone", TONES)
def test_callout_renders_the_icon_of_its_tone(tone: str) -> None:
    box = _box(f'<c-callout tone="{tone}">Body</c-callout>')
    expected = _box(f'<div><c-icon name="{tone}" /></div>')

    [expected_path] = expected.xpath(".//svg//path")
    [path] = box.xpath(".//svg//path")
    assert path.get("d") == expected_path.get("d")


@pytest.mark.parametrize("attrs", ['tone="purple"', ""])
def test_callout_renders_as_info_for_an_unknown_or_missing_tone(attrs: str) -> None:
    box = _box(f"<c-callout {attrs}>Body</c-callout>")
    info = _box('<c-callout tone="info">Body</c-callout>')

    assert box.get("class").split()[:2] == ["callout", "callout-info"]
    assert _svg_markup(box) == _svg_markup(info)
    assert box.get("role") is None


@pytest.mark.parametrize(
    ("tone", "role"),
    [("error", "alert"), ("success", "status"), ("info", None), ("warning", None)],
)
def test_callout_role_follows_its_tone(tone: str, role: str | None) -> None:
    box = _box(f'<c-callout tone="{tone}">Body</c-callout>')

    assert box.get("role") == role


def test_callout_title_is_a_strong_and_not_a_heading() -> None:
    box = _box('<c-callout tone="info" title="Heads up">Body</c-callout>')

    assert [s.text for s in box.xpath(".//strong")] == ["Heads up"]
    assert not box.xpath(".//h1|.//h2|.//h3|.//h4|.//h5|.//h6")


def test_callout_without_a_title_renders_no_strong() -> None:
    box = _box('<c-callout tone="info">Body</c-callout>')

    assert not box.xpath(".//strong")


def test_callout_puts_a_passed_class_in_the_boxs_one_class_attribute() -> None:
    box = _box(
        '<c-callout tone="warning" class="mx-auto max-w-reading">Body</c-callout>'
    )

    assert box.get("class").split() == [
        "callout",
        "callout-warning",
        "mx-auto",
        "max-w-reading",
    ]


def test_callout_puts_id_and_data_testid_on_the_box() -> None:
    box = _box(
        '<c-callout tone="info" id="note" data-testid="note-box">Body</c-callout>'
    )

    assert box.get("id") == "note"
    assert box.get("data-testid") == "note-box"


@pytest.mark.parametrize("tone", TONES)
def test_callout_icon_is_aria_hidden(tone: str) -> None:
    box = _box(f'<c-callout tone="{tone}">Body</c-callout>')

    [svg] = box.xpath(".//svg")
    assert svg.get("aria-hidden") == "true"


def test_callout_title_keeps_a_gap_above_a_bare_text_body() -> None:
    """A bare text body sat directly under the title with no gap.

    `space-y-3` only spaces element children, so the title carries its own
    bottom margin to clear text that is not wrapped in an element.
    """
    box = _box('<c-callout title="Heads up">Plain text body</c-callout>')

    [title] = box.xpath(".//strong")
    assert "mb-3" in title.get("class").split()
