"""Tests for the <c-panel-list /> and <c-panel-list-row /> cotton components."""

from __future__ import annotations

import lxml.html

from ..cotton_helpers import render_cotton


def _row(attrs: str, slot: str = "") -> lxml.html.HtmlElement:
    html = render_cotton(
        f"<c-panel-list><c-panel-list-row {attrs}>{slot}</c-panel-list-row></c-panel-list>"
    )
    return lxml.html.fromstring(html).find("li")


def test_the_list_is_a_ul_holding_its_rows() -> None:
    root = lxml.html.fromstring(
        render_cotton(
            '<c-panel-list data-testid="rows"><c-panel-list-row title="A" /><c-panel-list-row title="B" /></c-panel-list>'
        )
    )

    assert root.tag == "ul"
    assert root.get("data-testid") == "rows"
    assert len(root.findall("li")) == 2


def test_a_row_with_only_a_title_is_plain_text() -> None:
    row = _row('title="Intro course"')

    assert row.find(".//a") is None
    assert "Intro course" in row.text_content()
    assert row.find(".//p") is None


def test_the_detail_renders_under_the_title() -> None:
    row = _row('title="Intro course" detail="via Cohort A"')

    assert row.find(".//p").text == "via Cohort A"


def test_the_figure_renders_at_the_end() -> None:
    row = _row('title="Intro course" figure="80%"')

    assert row.xpath("./span[contains(@class, 'tabular-nums')]")[0].text == "80%"


def test_a_zero_figure_still_renders() -> None:
    row = _row('title="X" :figure="0"')

    assert row.xpath("./span[contains(@class, 'tabular-nums')]")[0].text == "0"


def test_a_row_without_a_figure_renders_none() -> None:
    row = _row('title="Intro course"')

    assert row.xpath("./span[contains(@class, 'tabular-nums')]") == []


def test_with_href_the_title_is_one_stretched_link() -> None:
    row = _row('title="Intro course" href="/courses/1/"')

    links = row.findall(".//a")
    assert len(links) == 1
    assert links[0].get("href") == "/courses/1/"
    assert links[0].text == "Intro course"
    assert "no-underline" in links[0].get("class")
    assert "after:absolute" in links[0].get("class")


def test_a_linked_row_ends_in_a_decorative_next_icon() -> None:
    row = _row('title="Intro course" href="/courses/1/"')

    icon = row.xpath(".//span[@aria-hidden='true'][.//svg]")
    assert icon


def test_a_plain_row_has_no_next_icon() -> None:
    assert _row('title="Intro course"').find(".//svg") is None


def test_a_trailing_control_renders_in_the_default_slot() -> None:
    row = _row(
        'title="Intro course" href="/x/"', '<button type="button">Deactivate</button>'
    )

    button = row.find(".//button")
    assert button is not None
    assert "z-10" in button.getparent().get("class")


def test_without_a_slot_there_is_no_trailing_wrapper() -> None:
    assert _row('title="Intro course"').xpath(".//div[contains(@class, 'z-10')]") == []


def test_attributes_pass_through_to_the_row() -> None:
    assert (
        _row('title="A" data-testid="registration-row"').get("data-testid")
        == "registration-row"
    )
