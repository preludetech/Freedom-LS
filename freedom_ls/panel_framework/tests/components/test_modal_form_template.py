import lxml.html

from django import forms
from django.template.loader import render_to_string

from ..helpers import normalised_form_markup

# A render of a form with no file field: the markup must carry no encoding
# attributes.
GOLDEN_FORM_WITHOUT_FILE_FIELD = """



<header class="panel-surface shrink-0 flex items-center justify-between gap-4 border-b border-border px-6 py-4">
    <h2 id="app-modal-title" class="min-w-0 wrap-anywhere text-lg font-semibold">Add</h2>




    <button type="button"
            x-on:click="requestClose"
            aria-label="Close"
            class="-my-2 -me-3 flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-md text-muted transition-colors hover:bg-surface-2 hover:text-on-surface">




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
x-on:click="cancel"
>

Cancel

</button>





    </div>
    <div class="flex min-w-0 flex-wrap items-center justify-end gap-3">

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


class _TextFieldsForm(forms.Form):
    name = forms.CharField()
    note = forms.CharField()


class _FileFieldForm(forms.Form):
    name = forms.CharField()
    attachment = forms.FileField(required=False)


class _FixedCohortForm(forms.Form):
    entries = forms.CharField()
    cohort = forms.CharField(widget=forms.HiddenInput(), initial="7")


def test_hidden_field_renders_input_without_label() -> None:
    """A hidden field used to leave a bare label behind in the modal form."""
    html = render_to_string(
        "panel_framework/modal/form.html",
        {
            "form": _FixedCohortForm(),
            "form_title": "Add",
            "action_url": "/x",
            "submit_buttons": [],
        },
    )

    assert '<input type="hidden" name="cohort" value="7"' in html
    assert 'for="id_cohort"' not in html
    assert 'for="id_entries"' in html


def _render(**extra: object) -> lxml.html.HtmlElement:
    context: dict[str, object] = {
        "form": _FixedCohortForm(),
        "form_title": "Add",
        "action_url": "/x",
        "submit_buttons": [],
    }
    context.update(extra)
    return lxml.html.fromstring(
        render_to_string("panel_framework/modal/form.html", context)
    )


def test_the_error_summary_keeps_its_focus_hooks_and_field_count() -> None:
    form = _FixedCohortForm(data={"cohort": "7"})
    form.is_valid()

    document = _render(form=form, field_error_count=1)

    (summary,) = document.cssselect("[data-error-summary]")
    assert summary.get("tabindex") == "-1"
    assert summary.get("role") == "alert"
    assert "1 field to fix." in summary.text_content()


def test_a_status_message_is_announced_as_a_status() -> None:
    document = _render(status_message="Added Ada.")

    (notice,) = document.cssselect("[data-status-message]")
    assert notice.get("role") == "status"
    assert "Added Ada." in notice.text_content()


def test_an_empty_message_renders_with_a_focused_close() -> None:
    document = _render(empty_message="Nothing to add.")

    assert "Nothing to add." in document.text_content()
    assert document.cssselect("form") == []
    (close,) = [
        el for el in document.iter("button") if el.text_content().strip() == "Close"
    ]
    assert close.get("autofocus") is not None


def test_a_form_with_a_file_field_posts_multipart() -> None:
    document = _render(form=_FileFieldForm())

    (form,) = document.cssselect("form")
    assert form.get("hx-encoding") == "multipart/form-data"
    assert form.get("enctype") == "multipart/form-data"


def test_a_form_without_a_file_field_declares_no_encoding() -> None:
    document = _render(form=_TextFieldsForm())

    (form,) = document.cssselect("form")
    assert form.get("hx-encoding") is None
    assert form.get("enctype") is None


def test_a_form_without_a_file_field_renders_as_it_always_did() -> None:
    html = render_to_string(
        "panel_framework/modal/form.html",
        {
            "form": _TextFieldsForm(),
            "form_title": "Add",
            "action_url": "/x",
            "submit_buttons": [{"label": "Save", "variant": "primary"}],
        },
    )

    assert normalised_form_markup(html) == normalised_form_markup(
        GOLDEN_FORM_WITHOUT_FILE_FIELD
    )


def test_the_request_error_holder_is_empty_and_inside_the_modal_body() -> None:
    document = _render(form=_TextFieldsForm())

    (holder,) = document.cssselect("form [data-request-error]")
    assert holder.get("tabindex") == "-1"
    assert holder.get("hidden") is not None
    assert holder.text_content() == ""
    assert document.cssselect("[data-modal-scroll] [data-request-error]") == [holder]
    assert document.cssselect("footer [data-request-error]") == []
