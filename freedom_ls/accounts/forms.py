from __future__ import annotations

import logging
from typing import Any

from allauth.account.forms import ResetPasswordKeyForm, SignupForm, UserTokenForm
from allauth.account.models import EmailAddress
from allauth.account.utils import url_str_to_user_pk
from allauth.core import context as allauth_context

from django import forms
from django.contrib.sites.models import Site
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext_lazy as _

from freedom_ls.site_aware_models.models import get_cached_site

from .models import User
from .utils import is_safe_next_url

logger = logging.getLogger(__name__)

# Session key an in-flight enrolment `next` is stashed under during signup, so
# it survives the existing-email/enumeration branch (which never reaches
# SignupView.get_success_url()) and can be resumed on the next login. Shared
# with AccountAdapter.get_login_redirect_url, which consumes it.
SIGNUP_NEXT_SESSION_KEY = "signup_enrolment_next"


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


class SiteAwareSignupForm(SignupForm):
    """allauth signup form extended for FLS:

    - Adjusts whether ``first_name`` is required based on the site's policy.
    - Adds T&C and Privacy Policy clickwrap checkboxes when the site requires
      explicit consent and the relevant docs resolve.
    - Records LegalConsent rows in ``custom_signup``.
    """

    first_name = forms.CharField(max_length=200, required=True)
    last_name = forms.CharField(max_length=200, required=False)

    # Honeypot — should remain empty. Real users never see / type into it.
    _hp = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "style": "position:absolute; left:-9999px;",
                "tabindex": "-1",
                "autocomplete": "off",
                "aria-hidden": "true",
            }
        ),
        label="",
    )

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

    def try_save(self, request: HttpRequest) -> tuple[User | None, HttpResponse | None]:
        """Stash a validated enrolment destination before the new-vs-existing branch.

        `try_save` is allauth's common entry point for both the genuine-new-
        account save and the existing-email/enumeration branch, so writing
        the session key here — before either branch runs — cannot reveal to
        the requester which one was taken (both branches write identically).
        The stash is consumed by `AccountAdapter.get_login_redirect_url` once
        the user next authenticates in this session.
        """
        candidate = is_safe_next_url(
            request, request.POST.get("next") or request.GET.get("next")
        )
        if candidate:
            request.session[SIGNUP_NEXT_SESSION_KEY] = candidate
        else:
            # An earlier CTA signup may have stashed a destination and then
            # been abandoned; a later, next-less signup/login in the same
            # session must not inherit it and land on that stale course.
            request.session.pop(SIGNUP_NEXT_SESSION_KEY, None)
        result: tuple[User | None, HttpResponse | None] = super().try_save(request)
        return result

    def clean__hp(self) -> str:
        value = self.cleaned_data.get("_hp", "")
        if value:
            # Generic message — do not reveal which field tripped.
            raise forms.ValidationError(_("Submission could not be processed."))
        return str(value)

    def custom_signup(self, request, user) -> None:
        """allauth hook called after the user is created.

        Records LegalConsent rows for the consents that were submitted.
        Wrapped in a transaction so a partial DB failure (one consent saved,
        the other 500s) does not leave asymmetric state.
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


class SiteAwareResetPasswordKeyForm(ResetPasswordKeyForm):
    """On a completed keyed password reset, mark the reset address verified.

    Completing a keyed reset proves control of the inbox the link was
    delivered to. With `ACCOUNT_LOGIN_ON_PASSWORD_RESET` enabled, allauth
    immediately tries to log the user in after `save()`, and that login runs
    the mandatory email-verification stage — so without this, an unverified
    account that resets its password would immediately be bounced back into
    verification instead of being logged in.
    """

    def save(self) -> None:
        super().save()  # Resets the password — unchanged allauth behaviour.
        user = self.user
        if user is None:
            return
        # This project's User.email is globally unique, so the reset target
        # is unambiguous. Deliberately not forcing "primary": True here — the
        # user may already have a different primary address, and forcing this
        # one to primary on create could violate allauth's unique_primary_email
        # constraint (mirrors allauth's own sync_email_address, which also
        # does not force primary).
        address, _created = EmailAddress.objects.get_or_create(
            user=user,
            email__iexact=user.email,
            defaults={"email": user.email, "verified": True},
        )
        if not address.verified:
            address.set_verified(commit=True)


class SiteUnscopedUserTokenForm(UserTokenForm):
    """Resolve a password-reset key's user without the site-scoped manager.

    A reset key only proves control of the inbox it was emailed to -- it says
    nothing about which Site the request that later opens the link resolves
    to. The stock `_get_user` resolves via `User.objects.get(pk=...)`, which
    goes through this project's site-scoped `UserManager` and raises
    `DoesNotExist` (turning a genuinely valid link into
    `invalid_password_reset`) whenever the current request's Site differs
    from the user's `site` FK. `_base_manager` is the plain `Manager` Django
    auto-provides (no `base_manager_name` is set on the model), so it applies
    no site filtering -- this bypass is scoped to exactly reset-key
    resolution; `User.objects`/`_default_manager` are untouched and stay
    site-scoped everywhere else.
    """

    def _get_user(self, uidb36: str) -> User | None:
        try:
            pk = url_str_to_user_pk(uidb36)
            return User._base_manager.get(pk=pk)
        except (ValueError, User.DoesNotExist):
            return None
