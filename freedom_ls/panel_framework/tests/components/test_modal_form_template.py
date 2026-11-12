import lxml.html

from django import forms
from django.template.loader import render_to_string


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
