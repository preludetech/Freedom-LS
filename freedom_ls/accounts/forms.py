from __future__ import annotations

import logging
from typing import Any

from allauth.account.forms import SignupForm
from allauth.core import context as allauth_context

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from freedom_ls.site_aware_models.models import get_cached_site

User = get_user_model()

logger = logging.getLogger(__name__)


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        # TODO: allow the user to upload a profile picture

        fields = ["first_name", "last_name"]


def _get_request_or_none():
    """Return the active request from allauth's context, or None."""
    try:
        return allauth_context.request
    except LookupError:
        return None


class HoneypotInput(forms.TextInput):
    """A text input that people never see and bots fill in.

    Reports itself as hidden so it lands in `form.hidden_fields`, which the
    signup template renders inside a `hidden` wrapper. Autofill skips inputs
    that can't take focus. Still `type="text"`: bots skip `type="hidden"`.
    """

    @property
    def is_hidden(self) -> bool:
        return True


class HoneypotFormMixin(forms.Form):
    """A field people never see and bots fill in.

    The name must not be one that browsers or password managers autofill, or
    real people get rejected. A trip logs the site and client IP, never the
    submitted values, and the error names no check: it only gives a person a
    way forward. The log reads allauth's request context, which
    AccountMiddleware sets for every view.
    """

    honeypot_context_label = "Signup"
    honeypot_error_message = _(
        "We couldn't process this sign-up. If you used autofill or a password "
        "manager, please try typing your details in by hand."
    )

    fax_number = forms.CharField(
        required=False,
        widget=HoneypotInput(
            attrs={
                "tabindex": "-1",
                "autocomplete": "off",
                "aria-hidden": "true",
            }
        ),
        label=_("Leave this field empty"),
    )

    def clean(self) -> dict[str, object]:
        super().clean()
        if self.cleaned_data.get("fax_number"):
            self._log_honeypot_trip()
            self.add_error(None, self.honeypot_error_message)
        return self.cleaned_data

    def _log_honeypot_trip(self) -> None:
        """Log the site and client IP, never the submitted values."""
        from .utils import get_client_ip

        request = _get_request_or_none()
        if request is None:
            logger.warning(
                "%s honeypot tripped outside a request", self.honeypot_context_label
            )
            return
        site_obj = get_cached_site(request)
        domain = site_obj.domain if isinstance(site_obj, Site) else "unknown"
        logger.warning(
            "%s honeypot tripped on site %s from IP %s",
            self.honeypot_context_label,
            domain,
            get_client_ip(request),
        )


class SiteAwareSignupForm(HoneypotFormMixin, SignupForm):
    """allauth signup form extended for FLS:

    - Adjusts whether ``first_name`` is required based on the site's policy.
    - Adds T&C and Privacy Policy clickwrap checkboxes when the site requires
      explicit consent and the relevant docs resolve.
    - Records LegalConsent rows in ``custom_signup``.
    """

    first_name = forms.CharField(max_length=200, required=True)
    last_name = forms.CharField(max_length=200, required=False)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # Local imports to avoid circulars at module import time.
        from .legal_docs import has_legal_doc
        from .utils import (
            get_effective_require_name,
            get_effective_require_terms_acceptance,
            get_signup_policy_for_request,
        )

        request = _get_request_or_none()
        site: Site | None
        site_obj = get_cached_site(request) if request is not None else None
        site = site_obj if isinstance(site_obj, Site) else None

        policy = get_signup_policy_for_request(request) if request is not None else None

        # Name handling. Per-site policy takes precedence; without one, fall
        # back to config.REQUIRE_NAME.
        if not get_effective_require_name(policy):
            self.fields["first_name"].required = False
            self.fields["first_name"].label = _("First name (optional)")

        # Terms / Privacy clickwrap. Per-site policy takes precedence; without
        # one, fall back to config.REQUIRE_TERMS_ACCEPTANCE so operators can
        # flip consent on for every site without creating a row per site.
        require_terms = get_effective_require_terms_acceptance(policy)

        if require_terms and request is not None and site is not None:
            if has_legal_doc(site, "terms"):
                self.fields["accept_terms"] = forms.BooleanField(
                    required=True,
                    label=_("I accept the Terms and Conditions"),
                )
            else:
                logger.warning(
                    "Site %s has require_terms_acceptance=True but no terms doc; "
                    "skipping accept_terms checkbox",
                    site.domain,
                )

            if has_legal_doc(site, "privacy"):
                self.fields["accept_privacy"] = forms.BooleanField(
                    required=True,
                    label=_("I accept the Privacy Policy"),
                )
            else:
                logger.warning(
                    "Site %s has require_terms_acceptance=True but no privacy "
                    "doc; skipping accept_privacy checkbox",
                    site.domain,
                )
        elif require_terms and request is None:
            # Out-of-request construction (e.g. management command). Refuse to
            # silently skip the checkboxes — fail closed.
            raise RuntimeError(
                "SiteAwareSignupForm cannot determine the current site/policy "
                "outside of a request when require_terms_acceptance is in play. "
                "This form is only intended for use from the signup HTTP view."
            )

    def custom_signup(self, request, user) -> None:
        """allauth hook called after the user is created.

        Records LegalConsent rows for the consents that were submitted.
        The writes are wrapped in a transaction so a partial DB failure (one
        consent saved, the other 500s) does not leave asymmetric state.
        """
        from .legal_docs import get_legal_doc
        from .models import LegalConsent
        from .utils import get_client_ip

        site_obj = get_cached_site(request)
        if not isinstance(site_obj, Site):
            return

        ip = get_client_ip(request)

        consent_pairs: list[tuple[str, str]] = [
            ("terms", "accept_terms"),
            ("privacy", "accept_privacy"),
        ]

        with transaction.atomic():
            for doc_type, accepted_field in consent_pairs:
                if not self.cleaned_data.get(accepted_field):
                    continue
                doc = get_legal_doc(site_obj, doc_type)
                if doc is None:
                    # Defensive: the form would not have asked.
                    continue
                LegalConsent.objects.create(
                    user=user,
                    document_type=doc_type,
                    document_version=doc.version,
                    git_hash=doc.git_hash,
                    ip_address=ip or None,
                    consent_method="signup_checkbox",
                )
