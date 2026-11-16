"""Tests for the <c-panel-notice /> cotton component."""

from __future__ import annotations

import lxml.html
import pytest

from ..cotton_helpers import render_cotton


def _render(attrs: str = "", slot: str = "Careful") -> lxml.html.HtmlElement:
    return lxml.html.fromstring(
        render_cotton(f"<c-panel-notice {attrs}>{slot}</c-panel-notice>")
    )


def test_the_default_tone_is_info_with_no_role() -> None:
    notice = _render()

    assert notice.get("role") is None
    assert "Careful" in notice.text_content()


@pytest.mark.parametrize("tone", ["info", "warning"])
def test_info_and_warning_carry_no_role(tone: str) -> None:
    assert _render(f'tone="{tone}"').get("role") is None


def test_error_carries_the_alert_role() -> None:
    assert _render('tone="error"').get("role") == "alert"


def test_success_carries_the_status_role() -> None:
    assert _render('tone="success"').get("role") == "status"


@pytest.mark.parametrize("tone", ["info", "warning", "error", "success"])
def test_each_tone_has_its_own_theme_token_classes(tone: str) -> None:
    classes = _render(f'tone="{tone}"').get("class")

    assert f"border-{tone}" in classes
    assert f"bg-{tone}" in classes


def test_a_title_is_a_bold_first_line() -> None:
    notice = _render('title="Heads up"')

    strong = notice.find(".//strong")
    assert strong is not None
    assert strong.text == "Heads up"
    assert notice.text_content().strip().startswith("Heads up")


def test_without_a_title_there_is_no_bold_line() -> None:
    assert _render().find(".//strong") is None


def test_attributes_pass_through() -> None:
    assert _render("data-status-message").get("data-status-message") is not None
