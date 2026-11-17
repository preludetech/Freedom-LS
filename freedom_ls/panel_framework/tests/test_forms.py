"""Tests for the framework's dialog forms."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import pytest

from django import forms

from freedom_ls.panel_framework.forms import REASON_LENGTH, ReasonForm

CHOICES = [("moved", "Moved away"), ("other", "Other")]

# The default form's markup, pinned so a host that uses neither option sees no change.
DEFAULT_FORM_HTML = (
    '<div>\n    <label for="id_reason">Reason (optional):</label>\n\n\n\n'
    '<input type="text" name="reason" maxlength="500" id="id_reason">\n'
    "    \n      \n    \n</div>"
)


def _choice_field(form: ReasonForm) -> forms.ChoiceField:
    return cast(forms.ChoiceField, form.fields["reason_choice"])


def test_the_reason_form_labels_the_field_and_has_no_help_text_by_default() -> None:
    field = ReasonForm().fields["reason"]

    assert field.label == "Reason (optional)"
    assert field.help_text == ""


def test_a_subclass_can_override_the_label_and_help_text() -> None:
    class StubReasonForm(ReasonForm):
        reason_label = "Why?"
        reason_help_text = "Visible to admins."

    field = StubReasonForm().fields["reason"]

    assert field.label == "Why?"
    assert field.help_text == "Visible to admins."


def test_the_reason_field_is_optional_and_stripped() -> None:
    form = ReasonForm({"reason": "  Moved away  "})

    assert form.is_valid()
    assert form.cleaned_data["reason"] == "Moved away"
    assert ReasonForm({}).is_valid()


def test_a_reason_over_the_limit_is_invalid() -> None:
    assert ReasonForm({"reason": "x" * REASON_LENGTH}).is_valid()
    assert not ReasonForm({"reason": "x" * (REASON_LENGTH + 1)}).is_valid()


def test_a_subclass_can_set_the_longest_reason_it_takes() -> None:
    class ShortReasonForm(ReasonForm):
        reason_max_length = 10

    assert ShortReasonForm({"reason": "x" * 10}).is_valid()
    assert not ShortReasonForm({"reason": "x" * 11}).is_valid()
    assert ShortReasonForm().fields["reason"].widget.attrs["maxlength"] == "10"


def test_the_default_form_renders_the_html_it_always_has() -> None:
    assert str(ReasonForm()) == DEFAULT_FORM_HTML


@pytest.mark.parametrize(
    ("required", "choices", "expected"),
    [
        (False, [], "Reason (optional)"),
        (True, [], "Reason"),
        (False, CHOICES, "Details (optional)"),
        (True, CHOICES, "Details"),
    ],
)
def test_the_text_field_is_labelled_for_whether_it_is_required_and_has_choices(
    required: bool, choices: Sequence[tuple[str, str]], expected: str
) -> None:
    form = ReasonForm(required=required, choices=choices)

    assert form.fields["reason"].label == expected


def test_a_subclass_can_reword_each_label() -> None:
    class WordedForm(ReasonForm):
        reason_label = "a"
        reason_required_label = "b"
        reason_choice_label = "c"
        reason_choice_placeholder = "d"
        reason_detail_label = "e"
        reason_detail_required_label = "f"

    assert WordedForm().fields["reason"].label == "a"
    assert WordedForm(required=True).fields["reason"].label == "b"
    assert WordedForm(choices=CHOICES).fields["reason"].label == "e"
    assert WordedForm(required=True, choices=CHOICES).fields["reason"].label == "f"
    choice = _choice_field(WordedForm(choices=CHOICES))
    assert choice.label == "c"
    assert next(iter(choice.choices)) == ("", "d")


def test_the_choice_select_starts_with_an_empty_placeholder_option() -> None:
    choice = _choice_field(ReasonForm(choices=CHOICES))

    assert list(choice.choices) == [("", "Choose a reason"), *CHOICES]


@pytest.mark.parametrize("data", [{"reason": ""}, {"reason": "   "}, {}])
def test_a_required_reason_refuses_empty_whitespace_only_and_missing_text(
    data: dict[str, str],
) -> None:
    form = ReasonForm(data, required=True)

    assert not form.is_valid()
    assert "reason" in form.errors


@pytest.mark.parametrize("value", ["", "unknown"])
def test_an_empty_or_unknown_choice_is_a_field_error(value: str) -> None:
    form = ReasonForm({"reason_choice": value}, choices=CHOICES)

    assert not form.is_valid()
    assert "reason_choice" in form.errors


def test_a_listed_choice_is_cleaned() -> None:
    form = ReasonForm({"reason_choice": "moved"}, choices=CHOICES)

    assert form.is_valid()
    assert form.cleaned_data["reason_choice"] == "moved"


def test_no_field_renders_the_required_attribute_and_required_ones_are_aria_required() -> (
    None
):
    html = str(ReasonForm(required=True, choices=CHOICES))

    assert " required" not in html
    assert html.count('aria-required="true"') == 2
    assert "aria-required" not in str(ReasonForm())
