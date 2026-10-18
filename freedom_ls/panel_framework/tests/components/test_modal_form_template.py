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
            "form_url": "/x",
            "submit_buttons": [],
        },
    )

    assert '<input type="hidden" name="cohort" value="7"' in html
    assert 'for="id_cohort"' not in html
    assert 'for="id_entries"' in html
