"""FLS's `panel-*` template overrides render the modal and inline record forms as before.

Each golden holds the markup of a form with no file field, so the comparison
fails when an override adds or drops an attribute.
"""

from __future__ import annotations

import re

import lxml.html

from django import forms
from django.template.loader import render_to_string
from django.test import override_settings


def normalised_form_markup(html: str) -> str:
    """A form render with the request-error element and the loading-label
    attribute removed, so a render that lacks them can be compared with
    one that has them."""
    root = lxml.html.fromstring(f"<div>{html}</div>")
    for holder in root.xpath("//*[@data-request-error]"):
        holder.drop_tree()
    for span in root.xpath("//*[@data-loading-label]"):
        del span.attrib["data-loading-label"]
    serialised = lxml.html.tostring(root, encoding="unicode")
    return re.sub(r">\s+<", "><", " ".join(serialised.split()))


# A render of a form with no file field: the markup must carry no encoding
# attributes.
GOLDEN_MODAL_FORM_WITHOUT_FILE_FIELD = """



<header class="panel-surface shrink-0 flex items-center justify-between gap-4 border-b border-border px-6 py-4">
    <h2 id="app-modal-title" class="min-w-0 wrap-anywhere text-lg font-semibold">Add</h2>




    <button type="button"
            x-on:click="requestClose"
            x-bind:disabled="running"
            aria-label="Close"
            class="-my-2 -me-3 flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-md text-muted transition-colors hover:bg-surface-2 hover:text-on-surface disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent">




<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" class="inline size-5" aria-hidden="true" data-icon="close"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M6 18L18 6M6 6l12 12"/></svg>



    </button>


</header>


<form hx-post="/x"
      hx-target="#app-modal-body"
      hx-swap="innerHTML"
      hx-disabled-elt="#app-modal-body button[type='submit']">



<div data-modal-scroll class="panel-surface space-y-4 py-5 text-sm " >





    <div class="space-y-4     text-left">

        <div class="form-field">
            <label for="id_name">Name:</label>
            <input type="text" name="name" required id="id_name">


        </div>

        <div class="form-field">
            <label for="id_note">Note:</label>
            <input type="text" name="note" required id="id_note">


        </div>



</div>

    </div>





<footer data-modal-footer class="panel-surface shrink-0 flex items-center justify-between gap-3 border-t border-border px-6 py-4 max-sm:flex-wrap " >
    <div class="shrink-0">




<button




 type="button"




data-variant="secondary"
class="btn btn-secondary "
x-on:click="cancel" x-bind:disabled="running"
>

Cancel

</button>





    </div>
    <div class="flex min-w-0 grow flex-wrap items-center justify-end gap-3">

        <button type="submit" hidden tabindex="-1" aria-hidden="true"></button>





<button




 type="submit"




data-variant="primary"
class="btn btn-primary "

>



<span class="inline-flex items-center gap-2 [.htmx-request_&]:hidden">
                    Save
                </span>
<span class="hidden [.htmx-request_&]:inline-flex [.htmx-request_&]:items-center [.htmx-request_&]:gap-2">



<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" class="inline size-5 animate-spin" aria-hidden="true" data-icon="loading"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99"/></svg>


 Saving…</span>

</button>






    </div>
</footer>

</form>

"""

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


def _render_modal_form_without_file_field() -> str:
    # The golden markup holds heroicons' SVGs, so pin the set: a concrete project
    # running this suite may configure another one.
    with override_settings(SEMANTIC_ICONS_SET="heroicons"):
        return render_to_string(
            "panel_framework/modal/form.html",
            {
                "form": _TextFieldsForm(),
                "form_title": "Add",
                "action_url": "/x",
                "submit_buttons": [{"label": "Save", "variant": "primary"}],
            },
        )


def _render_inline_form(form: forms.Form) -> str:
    return render_to_string(
        "panel_framework/partials/inline_record_form.html",
        {"form": form, "action_url": "/x", "form_id": "stub-form"},
    )


def _render_inline_form_without_file_field() -> str:
    # The golden markup holds heroicons' SVGs, so pin the set: a concrete project
    # running this suite may configure another one.
    with override_settings(SEMANTIC_ICONS_SET="heroicons"):
        return _render_inline_form(_TextFieldsForm())


def test_modal_form_a_form_without_a_file_field_renders_as_it_always_did() -> None:
    html = _render_modal_form_without_file_field()

    assert normalised_form_markup(html) == normalised_form_markup(
        GOLDEN_MODAL_FORM_WITHOUT_FILE_FIELD
    )


@override_settings(SEMANTIC_ICONS_SET="phosphor")
def test_modal_form_the_golden_comparison_holds_when_the_project_uses_another_icon_set() -> (
    None
):
    html = _render_modal_form_without_file_field()

    assert normalised_form_markup(html) == normalised_form_markup(
        GOLDEN_MODAL_FORM_WITHOUT_FILE_FIELD
    )


def test_inline_form_a_form_without_a_file_field_renders_the_golden_markup() -> None:
    html = _render_inline_form_without_file_field()

    assert normalised_form_markup(html) == normalised_form_markup(
        GOLDEN_INLINE_FORM_WITHOUT_FILE_FIELD
    )


@override_settings(SEMANTIC_ICONS_SET="phosphor")
def test_inline_form_the_golden_comparison_holds_when_the_project_uses_another_icon_set() -> (
    None
):
    html = _render_inline_form_without_file_field()

    assert normalised_form_markup(html) == normalised_form_markup(
        GOLDEN_INLINE_FORM_WITHOUT_FILE_FIELD
    )
