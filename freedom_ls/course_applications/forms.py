"""Forms for course_applications."""

from __future__ import annotations

from django import forms
from django.http import QueryDict
from django.utils.translation import gettext_lazy as _

from freedom_ls.accounts.forms import HoneypotFormMixin, _get_request_or_none
from freedom_ls.accounts.utils import (
    get_effective_require_name,
    get_signup_policy_for_request,
)

DETAIL_FIELDS = ("first_name", "last_name", "email")


class ApplicantDetailsForm(HoneypotFormMixin, forms.Form):
    """The details the About you page asks for.

    `ask_for` limits the form to the details still needed: a signed-in
    applicant is only asked for what the account lacks. Whether a first name
    is required follows the site's signup rule, so an application never
    demands more than signup does.
    """

    honeypot_context_label = "Application"
    honeypot_error_message = _(
        "We couldn't process this application. If you used autofill or a "
        "password manager, please try typing your details in by hand."
    )

    first_name = forms.CharField(
        max_length=200,
        required=False,
        label="First name",
        widget=forms.TextInput(attrs={"autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        max_length=200,
        required=False,
        label="Last name (optional)",
        widget=forms.TextInput(attrs={"autocomplete": "family-name"}),
    )
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )

    def __init__(
        self,
        data: QueryDict | None = None,
        *,
        initial: dict[str, str] | None = None,
        ask_for: tuple[str, ...] = DETAIL_FIELDS,
    ) -> None:
        super().__init__(data, initial=initial)
        for name in DETAIL_FIELDS:
            if name not in ask_for:
                del self.fields[name]
        if "first_name" in self.fields:
            if self._first_name_required():
                self.fields["first_name"].required = True
            else:
                self.fields["first_name"].label = "First name (optional)"

    def _first_name_required(self) -> bool:
        return get_effective_require_name(
            get_signup_policy_for_request(_get_request_or_none())
        )

    def clean_email(self) -> str:
        """Addresses are matched case-insensitively at claim, so the stored form is lowercase."""
        email: str = self.cleaned_data["email"]
        return email.lower()

    @property
    def details(self) -> dict[str, str]:
        """The cleaned values of the details asked for, ready to set on an application."""
        return {
            name: self.cleaned_data[name]
            for name in DETAIL_FIELDS
            if name in self.fields
        }
