import lxml.html
import pytest

from django import forms
from django.template.loader import render_to_string
from django.test import override_settings

from ..helpers import normalised_form_markup

GOLDEN_INLINE_FORM_WITHOUT_FILE_FIELD = """
<form id="stub-form"
      method="post"
      action="/x"
      hx-post="/x"
      hx-target="#stub-form"
      hx-swap="outerHTML"
      hx-disabled-elt="#stub-form-submit"
      hx-indicator="#stub-form-submit"
      x-data="refocusAfterRequest"
      data-refocus-id="id_name"
      x-on:htmx:after-request="refocus"
      class="flex flex-col gap-3 space-y-0">
    <div class="flex flex-wrap gap-3">
            <div class="form-field min-w-48 grow">
                <label for="id_name">Name:</label>
                <input type="text" name="name" required id="id_name">
            </div>
            <div class="form-field min-w-48 grow">
                <label for="id_note">Note:</label>
                <input type="text" name="note" required id="id_note">
            </div>
    </div>
</form>
"""


class _TextFieldsForm(forms.Form):
    name = forms.CharField()
    note = forms.CharField()


class _FileFieldForm(forms.Form):
    name = forms.CharField()
    attachment = forms.FileField()


def _render(form: forms.Form) -> str:
    return render_to_string(
        "panel_framework/partials/inline_record_form.html",
        {"form": form, "action_url": "/x", "form_id": "stub-form"},
    )


def _render_golden_candidate() -> str:
    # The golden markup holds heroicons' SVGs, so pin the set: a concrete project
    # running this suite may configure another one.
    with override_settings(FREEDOM_LS_ICON_SET="heroicons"):
        return _render(_TextFieldsForm())


@pytest.mark.needs_fls_host
def test_a_form_without_a_file_field_renders_the_golden_markup() -> None:
    html = _render_golden_candidate()

    assert normalised_form_markup(html) == normalised_form_markup(
        GOLDEN_INLINE_FORM_WITHOUT_FILE_FIELD
    )


@pytest.mark.needs_fls_host
@override_settings(FREEDOM_LS_ICON_SET="phosphor")
def test_the_golden_comparison_holds_when_the_project_uses_another_icon_set() -> None:
    html = _render_golden_candidate()

    assert normalised_form_markup(html) == normalised_form_markup(
        GOLDEN_INLINE_FORM_WITHOUT_FILE_FIELD
    )


def test_a_form_without_a_file_field_carries_no_encoding_attributes() -> None:
    root = lxml.html.fromstring(_render(_TextFieldsForm()))

    assert root.get("hx-encoding") is None
    assert root.get("enctype") is None


def test_a_form_with_a_file_field_posts_multipart() -> None:
    root = lxml.html.fromstring(_render(_FileFieldForm()))

    assert root.get("hx-encoding") == "multipart/form-data"
    assert root.get("enctype") == "multipart/form-data"


def test_the_request_error_holder_is_empty_and_inside_the_form() -> None:
    root = lxml.html.fromstring(_render(_TextFieldsForm()))

    (holder,) = root.cssselect("[data-request-error]")
    assert holder.get("tabindex") == "-1"
    assert holder.get("hidden") is not None
    assert holder.text_content() == ""


def test_the_form_holds_no_submit_button() -> None:
    root = lxml.html.fromstring(_render(_TextFieldsForm()))

    assert root.cssselect("button") == []


def _render_submit(**extra: str) -> lxml.html.HtmlElement:
    html = render_to_string(
        "panel_framework/partials/inline_record_form_submit.html",
        {"form_id": "stub-form", **extra},
    )
    return lxml.html.fromstring(html)


def test_the_footer_submit_names_its_form_and_carries_the_id_the_form_points_at() -> (
    None
):
    button = _render_submit()

    assert button.tag == "button"
    assert button.get("type") == "submit"
    assert button.get("form") == "stub-form"
    assert button.get("id") == "stub-form-submit"
    assert "Save" in button.text_content()
    assert button.cssselect("[data-loading-label='Saving…']")


def test_the_footer_submit_takes_its_own_label() -> None:
    button = _render_submit(label="Save picture")

    assert "Save picture" in button.text_content()
