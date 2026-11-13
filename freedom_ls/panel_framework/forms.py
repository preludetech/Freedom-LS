"""Forms the framework's dialogs render."""

from __future__ import annotations

from collections.abc import Mapping

from django import forms

__all__ = ["REASON_LENGTH", "ReasonForm"]

#: The longest reason a dialog accepts unless its form says otherwise.
REASON_LENGTH = 500


class ReasonForm(forms.Form):
    """The optional reason a confirm dialog asks for. A host subclass sets
    `reason_label` and `reason_help_text` to word the field its own way, and
    `reason_max_length` to the length of the column it stores reasons in."""

    reason_label = "Reason (optional)"
    reason_help_text = ""
    reason_max_length = REASON_LENGTH

    def __init__(self, data: Mapping[str, str] | None = None) -> None:
        super().__init__(data)
        self.fields["reason"] = forms.CharField(
            required=False,
            max_length=self.reason_max_length,
            strip=True,
            label=self.reason_label,
            help_text=self.reason_help_text,
        )
