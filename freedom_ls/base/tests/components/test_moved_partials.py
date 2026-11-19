"""FLS's page title and form partials render exactly what the framework's partials render."""

from __future__ import annotations

import pytest

from django import forms
from django.template.loader import render_to_string


class _SampleForm(forms.Form):
    name = forms.CharField(help_text="Your full name")
    token = forms.CharField(widget=forms.HiddenInput)


def _invalid_form() -> _SampleForm:
    form = _SampleForm(data={"token": "x"})
    form.add_error(None, "Something went wrong")
    return form


PAIRS = [
    pytest.param(
        "page_title.html",
        {"page_title": "Learners", "page_subtitle": "Everyone enrolled"},
        id="title-and-subtitle",
    ),
    pytest.param("page_title.html", {"page_title": "Learners"}, id="title-only"),
    pytest.param("page_title.html", {"page_title": "", "oob": True}, id="empty-oob"),
    pytest.param("form.html", {"form": _SampleForm()}, id="unbound-form"),
    pytest.param("form.html", {"form": _invalid_form()}, id="form-with-errors"),
]


@pytest.mark.parametrize(("name", "context"), PAIRS)
def test_the_fls_partial_renders_the_same_html_as_the_framework_partial(
    name: str, context: dict[str, object]
) -> None:
    fls = render_to_string(f"partials/{name}", context)
    framework = render_to_string(f"panel_framework/partials/{name}", context)

    assert fls.strip() == framework.strip()
