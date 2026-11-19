import lxml.html
import pytest

from django import forms
from django.template.loader import render_to_string
from django.test import override_settings

from ..helpers import normalised_form_markup

# The loading text reads "Saving…" (the single ellipsis character), so this is not a byte copy of a render that read "Saving...".
GOLDEN_INLINE_FORM_WITHOUT_FILE_FIELD = """
<form id="stub-form"
      hx-post="/x"
      hx-target="#stub-form"
      hx-swap="outerHTML"
      hx-disabled-elt="find button[type='submit']"
      x-data="refocusAfterRequest"
      data-refocus-id="id_name"
      x-on:htmx:after-request="refocus"
      class="flex flex-col gap-3 space-y-0">

    <div class="flex flex-wrap items-end gap-3">

            <div class="form-field min-w-48 grow">
                <label for="id_name">Name:</label>
                <input type="text" name="name" required id="id_name">
            </div>

            <div class="form-field min-w-48 grow">
                <label for="id_note">Note:</label>
                <input type="text" name="note" required id="id_note">
            </div>




<button




 type="submit"




data-variant="primary"
class="panel-btn panel-btn-primary panel-btn-sm "

>



<span class="inline-flex items-center gap-2 [.htmx-request_&]:hidden">Save</span>
<span class="hidden [.htmx-request_&]:inline-flex [.htmx-request_&]:items-center [.htmx-request_&]:gap-2">



<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" class="inline size-5 animate-spin" aria-hidden="true" data-icon="loading"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99"/></svg>


 Saving…</span>

</button>




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
