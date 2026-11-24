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


def test_the_footer_pushes_cancel_and_the_actions_apart_and_never_scrolls() -> None:
    footer = _render()

    classes = footer.get("class", "").split()

    assert {"flex", "justify-between", "shrink-0"} <= set(classes)
    assert "sticky" not in classes
    assert "justify-end" in footer.findall("div")[1].get("class", "").split()


def _render_stepping() -> lxml.html.HtmlElement:
    return lxml.html.fromstring(
        render_cotton(
            '<c-modal-footer stepping="true">'
            '<c-slot name="previous"><button type="button">Back</button></c-slot>'
            '<c-slot name="next"><button type="button">Onward</button></c-slot>'
            "</c-modal-footer>"
        )
    )


def test_a_stepping_footer_renders_both_slots_and_no_cancel_button() -> None:
    footer = _render_stepping()

    left, right = footer.findall("div")

    assert [button.text for button in left.findall("button")] == ["Back"]
    assert [button.text for button in right.findall("button")] == ["Onward"]
    assert footer.cssselect("[x-on\\:click]") == []
    assert "Cancel" not in footer.text_content()


def test_a_stepping_footer_keeps_the_footer_shape() -> None:
    classes = _render_stepping().get("class", "").split()

    assert {"flex", "justify-between", "shrink-0"} <= set(classes)
