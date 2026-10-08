"""Forms for course_applications."""

from __future__ import annotations

from django import forms


class ApplicantEmailForm(forms.Form):
    """The address an anonymous applicant types at submit."""

    email = forms.EmailField(label="Where should we send your decision?")

    def clean_email(self) -> str:
        # Lowercased the way allauth stores addresses, so the claim's
        # case-insensitive match and the stored value agree.
        email: str = self.cleaned_data["email"]
        return email.lower()
