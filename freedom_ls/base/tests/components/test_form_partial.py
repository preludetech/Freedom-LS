"""Tests for the partials/form.html template."""

import lxml.html

from django import forms
from django.template.loader import render_to_string


class _ErrorForm(forms.Form):
    name = forms.CharField(required=False)


def _form_with_non_field_error() -> _ErrorForm:
    form = _ErrorForm(data={})
    form.is_valid()
    form.add_error(None, "The two dates overlap.")
    return form


def test_form_partial_renders_non_field_errors_as_an_error_callout() -> None:
    html = render_to_string(
        "partials/form.html", {"form": _form_with_non_field_error()}
    )

    [callout] = lxml.html.fromstring(html).xpath("//*[@role='alert']")
    assert callout.get("class").split()[:2] == ["callout", "callout-error"]
    assert "The two dates overlap." in callout.text_content()


def test_form_partial_does_not_hand_build_the_error_box() -> None:
    html = render_to_string(
        "partials/form.html", {"form": _form_with_non_field_error()}
    )

    assert "bg-error/10" not in html


def test_form_partial_leaves_out_non_field_errors_when_asked() -> None:
    html = render_to_string(
        "partials/form.html",
        {"form": _form_with_non_field_error(), "hide_non_field_errors": True},
    )

    assert "The two dates overlap." not in html
    assert 'role="alert"' not in html
