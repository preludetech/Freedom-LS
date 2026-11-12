"""Tests for the framework's dialog forms."""

from __future__ import annotations

from freedom_ls.panel_framework.forms import REASON_LENGTH, ReasonForm


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
