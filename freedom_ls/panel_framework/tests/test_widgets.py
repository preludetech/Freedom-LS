"""Tests for the framework's file widget: what it prints for the current file
and how it keeps the Remove checkbox apart from the file input."""

from __future__ import annotations

import lxml.html
import pytest
from lxml.html import HtmlElement

from django import forms

from freedom_ls.panel_framework.widgets import PanelClearableFileInput


class _StoredFile:
    """A stored file whose `url` raises, as a private or URL-less storage does."""

    def __init__(self, name: str) -> None:
        self.name = name

    @property
    def url(self) -> str:
        raise ValueError("this storage has no URL")

    def __str__(self) -> str:
        return self.name


def _render(
    value: object,
    *,
    required: bool = False,
    attrs: dict[str, object] | None = None,
    data: dict[str, str] | None = None,
) -> tuple[str, HtmlElement]:
    widget = PanelClearableFileInput(attrs=attrs)
    widget.is_required = required
    if data is not None:
        widget.value_from_datadict(data, {}, "attachment")
    html = widget.render("attachment", value, attrs=attrs)
    return html, lxml.html.fromstring(f"<div>{html}</div>")


def _file_input(root: HtmlElement) -> HtmlElement:
    (file_input,) = root.xpath("//input[@type='file']")
    return file_input


def _checkboxes(root: HtmlElement) -> list[HtmlElement]:
    return list(root.xpath("//input[@type='checkbox']"))


def test_current_file_shows_its_basename_with_the_full_name_in_title() -> None:
    html, root = _render(_StoredFile("stub_files/2026/notes.txt"))

    (name_span,) = root.xpath("//span[@title]")
    assert "Current file:" in root.text_content()
    assert name_span.text == "notes.txt"
    assert name_span.get("title") == "notes.txt"
    assert "stub_files" not in html


def test_current_file_is_not_a_link() -> None:
    _, root = _render(_StoredFile("stub_files/notes.txt"))

    assert root.xpath("//a") == []


def test_a_file_whose_url_raises_still_renders() -> None:
    _, root = _render(_StoredFile("stub_files/notes.txt"))

    assert len(root.xpath("//input[@type='file']")) == 1


def test_a_hostile_file_name_is_escaped() -> None:
    html, root = _render(_StoredFile('dir/<script>"x.png'))

    assert "<script>" not in html
    assert root.xpath("//script") == []
    assert root.xpath("//span[@title]")[0].text == '<script>"x.png'


def test_an_optional_field_offers_a_remove_checkbox_named_for_the_basename() -> None:
    _, root = _render(_StoredFile("stub_files/notes.txt"), required=False)

    (checkbox,) = _checkboxes(root)
    (label,) = root.xpath(f"//label[@for='{checkbox.get('id')}']")
    assert checkbox.get("name") == "attachment-clear"
    assert label.text_content().split() == ["Remove", "notes.txt"]
    assert label.xpath(".//span[contains(@class, 'sr-only')]")[0].text == " notes.txt"


def test_a_required_field_offers_no_remove_checkbox() -> None:
    _, root = _render(_StoredFile("stub_files/notes.txt"), required=True)

    assert _checkboxes(root) == []
    assert root.xpath("//label") == []


@pytest.mark.parametrize("value", [None, "", _StoredFile("")])
def test_no_current_file_leaves_only_the_file_input(value: object) -> None:
    _, root = _render(value, required=False)

    assert _checkboxes(root) == []
    assert root.xpath("//p") == []
    assert _file_input(root).get("name") == "attachment"


def test_a_ticked_remove_renders_the_checkbox_ticked_not_the_file_input() -> None:
    _, root = _render(
        _StoredFile("stub_files/notes.txt"), data={"attachment-clear": "on"}
    )

    (checkbox,) = _checkboxes(root)
    assert checkbox.get("checked") is not None
    assert _file_input(root).get("checked") is None


def test_an_unticked_remove_renders_the_checkbox_unticked() -> None:
    _, root = _render(_StoredFile("stub_files/notes.txt"), data={})

    (checkbox,) = _checkboxes(root)
    assert checkbox.get("checked") is None


def test_the_file_input_keeps_the_field_attributes_and_the_checkbox_has_none() -> None:
    _, root = _render(
        _StoredFile("stub_files/notes.txt"),
        attrs={
            "id": "id_attachment",
            "aria-describedby": "id_attachment_error",
            "aria-invalid": "true",
        },
    )

    file_input = _file_input(root)
    (checkbox,) = _checkboxes(root)
    assert file_input.get("id") == "id_attachment"
    assert file_input.get("aria-describedby") == "id_attachment_error"
    assert file_input.get("aria-invalid") == "true"
    assert checkbox.get("id") == "id_attachment_clear"
    assert checkbox.get("aria-describedby") is None
    assert checkbox.get("aria-invalid") is None


def test_without_an_id_the_checkbox_keeps_django_s_id() -> None:
    _, root = _render(_StoredFile("stub_files/notes.txt"))

    (checkbox,) = _checkboxes(root)
    (label,) = root.xpath("//label")
    assert checkbox.get("id") == "attachment-clear_id"
    assert label.get("for") == "attachment-clear_id"


def test_two_forms_with_the_same_file_field_get_different_checkbox_ids() -> None:
    class _Form(forms.Form):
        attachment = forms.FileField(required=False, widget=PanelClearableFileInput)

    initial = {"attachment": _StoredFile("stub_files/notes.txt")}
    ids = []
    for prefix in ("inline", "dialog"):
        html = str(_Form(initial=initial, prefix=prefix)["attachment"])
        root = lxml.html.fromstring(f"<div>{html}</div>")
        (checkbox,) = _checkboxes(root)
        (label,) = root.xpath("//label")
        assert label.get("for") == checkbox.get("id")
        ids.append(checkbox.get("id"))

    assert ids == ["id_inline-attachment_clear", "id_dialog-attachment_clear"]


def test_the_remove_label_lays_the_checkbox_out_beside_its_text_with_a_gap() -> None:
    """The Remove label used to be a bare block label, so the checkbox touched the text."""
    _, root = _render(_StoredFile("stub_files/notes.txt"), required=False)

    (checkbox,) = _checkboxes(root)
    (label,) = root.xpath(f"//label[@for='{checkbox.get('id')}']")
    classes = label.get("class", "").split()
    assert {"flex", "items-center", "gap-2"} <= set(classes)
