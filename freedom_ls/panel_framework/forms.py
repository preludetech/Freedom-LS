"""Forms the framework's dialogs render."""

from __future__ import annotations

from collections.abc import Mapping

from django import forms

__all__ = ["REASON_LENGTH", "ReasonForm"]

#: The longest reason a dialog accepts. A host that stores reasons elsewhere
#: keeps its own column at least this long.
REASON_LENGTH = 500


class ReasonForm(forms.Form):
    """The optional reason a confirm dialog asks for. A host subclass sets
    `reason_label` and `reason_help_text` to word the field its own way."""

    reason_label = "Reason (optional)"
    reason_help_text = ""

    reason = forms.CharField(
        required=False,
        max_length=REASON_LENGTH,
        strip=True,
        widget=forms.TextInput(attrs={"maxlength": str(REASON_LENGTH)}),
    )

    def __init__(self, data: Mapping[str, str] | None = None) -> None:
        super().__init__(data)
        self.fields["reason"].label = self.reason_label
        self.fields["reason"].help_text = self.reason_help_text
