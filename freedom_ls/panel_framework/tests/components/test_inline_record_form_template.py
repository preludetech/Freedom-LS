import lxml.html

from django import forms
from django.template.loader import render_to_string


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
    assert holder.text_content().strip() == ""
    assert holder.get("role") == "alert"
    assert holder.cssselect("[data-request-error-text]")


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
