"""Forms for course_applications."""

from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from freedom_ls.accounts.forms import HoneypotFormMixin


class ApplicantEmailForm(HoneypotFormMixin, forms.Form):
    """The address an anonymous applicant types at submit."""

    honeypot_context_label = "Application"
    honeypot_error_message = _(
        "We couldn't process this application. If you used autofill or a "
        "password manager, please try typing your email address in by hand."
    )

    email = forms.EmailField(label="Where should we send your decision?")

    def clean_email(self) -> str:
        # Lowercased the way allauth stores addresses, so the claim's
        # case-insensitive match and the stored value agree.
        email: str = self.cleaned_data["email"]
        return email.lower()
