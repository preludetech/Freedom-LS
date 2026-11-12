"""Tests for the <c-modal-footer /> cotton component."""

from __future__ import annotations

import lxml.html

from ..cotton_helpers import render_cotton


def _render(
    attrs: str = "", slot: str = '<button type="submit">Save</button>'
) -> lxml.html.HtmlElement:
    return lxml.html.fromstring(
        render_cotton(f"<c-modal-footer {attrs}>{slot}</c-modal-footer>")
    )


def _cancel(footer: lxml.html.HtmlElement) -> lxml.html.HtmlElement:
    return footer.findall("div")[0][0]


def test_cancel_defaults_to_a_button_labelled_cancel_calling_cancel() -> None:
    cancel = _cancel(_render())

    assert cancel.tag == "button"
    assert cancel.text.strip() == "Cancel"
    assert cancel.get("type") == "button"
    assert cancel.get("x-on:click") == "cancel"


def test_cancel_attribute_sets_the_label() -> None:
    assert _cancel(_render('cancel="Close"')).text.strip() == "Close"


def test_cancel_href_renders_a_link_with_no_click_handler() -> None:
    cancel = _cancel(_render('cancel_href="/people/"'))

    assert cancel.tag == "a"
    assert cancel.get("href") == "/people/"
    assert cancel.get("x-on:click") is None


def test_cancel_click_names_the_method_called() -> None:
    cancel = _cancel(_render('cancel_click="keepEditing"'))

    assert cancel.get("x-on:click") == "keepEditing"


def test_focus_cancel_sets_autofocus() -> None:
    assert _cancel(_render('focus_cancel="true"')).get("autofocus") is not None
    assert _cancel(_render()).get("autofocus") is None


def test_the_default_slot_renders_after_the_cancel() -> None:
    footer = _render()

    boxes = footer.findall("div")

    assert footer.tag == "footer"
    assert [button.text for button in boxes[1].findall("button")] == ["Save"]


def test_the_footer_pushes_cancel_and_the_actions_apart_and_stays_in_view() -> None:
    footer = _render()

    classes = footer.get("class", "").split()

    assert {"flex", "justify-between", "sticky", "bottom-0"} <= set(classes)
    assert "justify-end" in footer.findall("div")[1].get("class", "").split()
