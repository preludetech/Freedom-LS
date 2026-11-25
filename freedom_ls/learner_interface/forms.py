from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from django.http import QueryDict
from django.utils.translation import gettext_lazy as _

from freedom_ls.form_engine.declarations import declaration_text_hash


class FormDeclarationForm(forms.Form):
    """The signature a learner gives before a declaration quiz attempt."""

    agreed = forms.BooleanField(
        required=True,
        error_messages={"required": _("Tick the box to make the declaration.")},
    )
    typed_name = forms.CharField(
        max_length=200,
        strip=False,
        error_messages={"required": _("Type your full name to sign.")},
    )
    text_hash = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, data: QueryDict | None = None, *, declaration_text: str) -> None:
        super().__init__(data)
        self.expected_hash = declaration_text_hash(declaration_text)
        self.fields["text_hash"].initial = self.expected_hash

    def clean_typed_name(self) -> str:
        name: str = self.cleaned_data["typed_name"]
        if not name.strip():
            raise ValidationError(_("Type your full name to sign."), code="required")
        # Stored as typed, spaces kept: the signature is what the learner entered.
        return name

    def clean_text_hash(self) -> str:
        # The page re-checks the text it showed, so the stored text is always
        # the text the learner read.
        value: str = self.cleaned_data["text_hash"]
        if value != self.expected_hash:
            raise ValidationError("stale", code="stale")
        return value

    def declaration_changed(self) -> bool:
        """Whether the text on the page changed since the learner loaded it.

        A missing hash counts too: the learner can't be shown to have read the
        current text, and the page re-renders with the right one."""
        return self.has_error("text_hash")
