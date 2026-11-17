"""Forms the framework's dialogs render."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from django import forms

__all__ = ["REASON_LENGTH", "ReasonForm"]

#: The longest reason a dialog accepts unless its form says otherwise.
REASON_LENGTH = 500


class ReasonForm(forms.Form):
    """The reason a confirm dialog asks for: free text, optionally required,
    optionally with a choice from a list ahead of it. A host subclass sets the
    `reason_*_label` and `reason_help_text` attributes to word the fields its
    own way, and `reason_max_length` to the length of the column it stores
    reasons in. When a choice is offered, the text field is the details that
    go with it."""

    reason_label = "Reason (optional)"
    reason_required_label = "Reason"
    reason_choice_label = "Reason"
    reason_choice_placeholder = "Choose a reason"
    reason_detail_label = "Details (optional)"
    reason_detail_required_label = "Details"
    reason_help_text = ""
    reason_max_length = REASON_LENGTH
    # The browser must not block the submit: the server's field error is the
    # one place a missing reason is reported.
    use_required_attribute = False

    def __init__(
        self,
        data: Mapping[str, str] | None = None,
        *,
        required: bool = False,
        choices: Sequence[tuple[str, str]] = (),
    ) -> None:
        super().__init__(data)
        if choices:
            self.fields["reason_choice"] = forms.ChoiceField(
                choices=[("", self.reason_choice_placeholder), *choices],
                label=self.reason_choice_label,
                widget=forms.Select(attrs={"aria-required": "true"}),
            )
        self.fields["reason"] = forms.CharField(
            required=required,
            max_length=self.reason_max_length,
            strip=True,
            label=self._text_label(required=required, has_choices=bool(choices)),
            help_text=self.reason_help_text,
            widget=forms.TextInput(attrs={"aria-required": "true"})
            if required
            else None,
        )

    def _text_label(self, *, required: bool, has_choices: bool) -> str:
        if has_choices:
            return (
                self.reason_detail_required_label
                if required
                else self.reason_detail_label
            )
        return self.reason_required_label if required else self.reason_label
