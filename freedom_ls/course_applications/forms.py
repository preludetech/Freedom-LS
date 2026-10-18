"""Forms for course_applications."""

from __future__ import annotations

from django import forms
from django.contrib.sites.models import Site
from django.http import HttpRequest, QueryDict
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from freedom_ls.accounts.forms import (
    accepted_legal_docs,
    add_consent_fields,
    apply_signup_name_policy,
    honeypot_field,
    reject_honeypot,
    tripped_honeypot,
)
from freedom_ls.accounts.utils import get_client_ip, get_signup_policy_for_request
from freedom_ls.course_applications.applicant_email import normalise_email
from freedom_ls.course_applications.models import AnonymousApplicant
from freedom_ls.site_aware_models.models import get_cached_site

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
        policy = get_signup_policy_for_request(request)
        apply_signup_name_policy(self, policy)
        add_consent_fields(self, request, policy)

    def clean_email(self) -> str:
        return normalise_email(self.cleaned_data["email"])

    @property
    def tripped_honeypot(self) -> bool:
        """Whether the submission filled the field only a bot can see."""
        return tripped_honeypot(self)

    def clean(self) -> dict[str, object]:
        cleaned_data: dict[str, object] = super().clean() or {}
        reject_honeypot(self, self.request, HONEYPOT_APPLICATION_MESSAGE)
        return cleaned_data

    def save(self, commit: bool = True) -> AnonymousApplicant:
        applicant: AnonymousApplicant = super().save(commit=False)
        site = get_cached_site(self.request)
        # The checkboxes only exist when a real Site resolved, so an unresolved
        # host simply has nothing to record here.
        if isinstance(site, Site):
            self._record_consent_evidence(applicant, site)
        if commit:
            applicant.save()
        return applicant

    def _record_consent_evidence(
        self, applicant: AnonymousApplicant, site: Site
    ) -> None:
        """Keep what a LegalConsent row will need, since no user exists yet to hold one."""
        accepted = accepted_legal_docs(site, self.cleaned_data)
        for doc_type, doc in accepted:
            if doc_type == "terms":
                applicant.terms_version, applicant.terms_git_hash = (
                    doc.version,
                    doc.git_hash,
                )
            else:
                applicant.privacy_version, applicant.privacy_git_hash = (
                    doc.version,
                    doc.git_hash,
                )
        if accepted:
            applicant.consent_ip_address = get_client_ip(self.request) or None
            applicant.consented_at = timezone.now()


class ApplicantEmailForm(forms.Form):
    """The one field an applicant may change after submitting: where the claim link goes.

    Not the details form: the name and consent were given once, and the
    honeypot is the only other thing a bot would fill in.
    """

    email = forms.EmailField(max_length=254, label="Wrong address? Enter the right one")
    fax_number = honeypot_field()

    def __init__(self, data: QueryDict | None = None, *, request: HttpRequest) -> None:
        super().__init__(data)
        self.request = request

    def clean_email(self) -> str:
        return normalise_email(self.cleaned_data["email"])

    def clean(self) -> dict[str, object]:
        cleaned_data: dict[str, object] = super().clean() or {}
        reject_honeypot(self, self.request, HONEYPOT_APPLICATION_MESSAGE)
        return cleaned_data
