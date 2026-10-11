"""Forms for course_applications."""

from __future__ import annotations

from django import forms
from django.http import HttpRequest, QueryDict
from django.utils.translation import gettext_lazy as _

from freedom_ls.accounts.forms import (
    apply_signup_name_policy,
    honeypot_field,
    reject_honeypot,
)
from freedom_ls.accounts.utils import get_signup_policy_for_request
from freedom_ls.course_applications.applicant_email import normalise_email
from freedom_ls.course_applications.models import AnonymousApplicant

HONEYPOT_APPLICATION_MESSAGE = _(
    "We couldn't process this application. If you used autofill or a password "
    "manager, please try typing your details in by hand."
)


class ApplicantDetailsForm(forms.ModelForm):
    """The signup details without a password, written onto an AnonymousApplicant.

    Nothing here reads the User table: the response is the same whether or not
    the address has an account, so the step cannot be used to find out.
    """

    # Declared, not taken from the model, so the policy can make it required.
    first_name = forms.CharField(max_length=200)
    fax_number = honeypot_field()

    class Meta:
        model = AnonymousApplicant
        fields = ["email", "first_name", "last_name"]

    def __init__(
        self,
        data: QueryDict | None = None,
        *,
        request: HttpRequest,
        instance: AnonymousApplicant,
    ) -> None:
        super().__init__(data, instance=instance)
        self.request = request
        apply_signup_name_policy(self, get_signup_policy_for_request(request))

    def clean_email(self) -> str:
        return normalise_email(self.cleaned_data["email"])

    def clean(self) -> dict[str, object]:
        cleaned_data: dict[str, object] = super().clean() or {}
        reject_honeypot(self, self.request, HONEYPOT_APPLICATION_MESSAGE)
        return cleaned_data
