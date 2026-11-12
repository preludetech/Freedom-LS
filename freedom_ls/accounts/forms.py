from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from allauth.account.forms import SignupForm
from allauth.core import context as allauth_context

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from freedom_ls.site_aware_models.models import get_cached_site

from .images import encode_profile_picture
from .validators import validate_profile_picture

if TYPE_CHECKING:
    from django_stubs_ext import StrPromise

    from .legal_docs import LegalDoc
    from .models import SiteSignupPolicy
    from .models import User as UserModel

User = get_user_model()

logger = logging.getLogger(__name__)


class UserForm(forms.ModelForm):
    profile_picture = forms.FileField(
        required=False,
        label="Profile picture",
        help_text=(
            "JPEG, PNG or WebP, up to 10 MB. Square pictures work best; "
            "others are cropped to the centre."
        ),
        # Not ClearableFileInput: it would print the stored key and a
        # signed link beside the input.
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "profile_picture"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Without a picture there is nothing to remove, so the checkbox is
        # not rendered and a forged value is ignored.
        if self.instance.profile_picture:
            self.fields["remove_profile_picture"] = forms.BooleanField(
                required=False, label="Remove profile picture"
            )

    def clean(self) -> dict[str, object] | None:
        cleaned_data: dict[str, object] | None = super().clean()
        if cleaned_data is None:
            return cleaned_data
        # A file that failed validation is absent from cleaned_data; putting
        # a value back would blank the instance of an invalid form. A new
        # file wins over the tick. False is what a model FileField reads as
        # "clear this field".
        if (
            cleaned_data.get("remove_profile_picture")
            and "profile_picture" in cleaned_data
            and not isinstance(cleaned_data["profile_picture"], ContentFile)
        ):
            cleaned_data["profile_picture"] = False
        return cleaned_data

    def clean_profile_picture(self) -> File | None:
        upload = self.cleaned_data.get("profile_picture")
        if not isinstance(upload, UploadedFile):
            # No new file: the field hands back what the user already has.
            return upload
        encoded = encode_profile_picture(validate_profile_picture(upload))
        # Storage only ever receives the re-encoded WebP. The name is a
        # placeholder; the upload_to callable picks the key.
        return ContentFile(encoded, name="profile_picture.webp")

    def save(self, commit: bool = True) -> UserModel:
        if not commit:
            # The superseded file is deleted when this save commits, so an
            # unsaved form has nothing to hang that on.
            raise ValueError("UserForm.save() does not support commit=False.")
        superseded = self._stored_profile_picture_name()
        user: UserModel = super().save()
        if superseded and superseded != user.profile_picture.name:
            storage = user.profile_picture.storage
            # Deferred to commit: a save that rolls back keeps the row
            # pointing at the old file, so the old file has to survive.
            transaction.on_commit(lambda: storage.delete(superseded))
        return user

    def _stored_profile_picture_name(self) -> str:
        """The picture name the database holds now.

        Read from the database, not the instance: validation has already
        written the new file onto the instance by the time save() runs.
        Through the base manager, because `objects` filters to the
        request's site.
        """
        stored = (
            User._base_manager.filter(pk=self.instance.pk)
            .values_list("profile_picture", flat=True)
            .first()
        )
        return stored or ""


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


HONEYPOT_SIGNUP_MESSAGE = _(
    "We couldn't process this sign-up. If you used autofill or a password manager, "
    "please try typing your details in by hand."
)


def tripped_honeypot(form: forms.BaseForm) -> bool:
    """Whether the submission filled the field only a bot can see."""
    return bool(form.cleaned_data.get("fax_number"))


def honeypot_field() -> forms.CharField:
    """The honeypot: bots fill it, people never see it. The name must not be one
    that browsers or password managers autofill, or real people get rejected."""
    return forms.CharField(
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


def _log_honeypot_trip(request: HttpRequest | None) -> None:
    """Log the site and client IP, never the submitted values."""
    from .utils import get_client_ip

    if request is None:
        logger.warning("Signup honeypot tripped outside a request")
        return
    site_obj = get_cached_site(request)
    domain = site_obj.domain if isinstance(site_obj, Site) else "unknown"
    logger.warning(
        "Signup honeypot tripped on site %s from IP %s",
        domain,
        get_client_ip(request),
    )


def reject_honeypot(
    form: forms.BaseForm, request: HttpRequest | None, message: StrPromise
) -> None:
    """Refuse a submission whose honeypot is filled, logging the site and IP, never the values."""
    if not tripped_honeypot(form):
        return
    _log_honeypot_trip(request)
    # Don't say which check failed, but give a person a way forward.
    form.add_error(None, message)


def apply_signup_name_policy(
    form: forms.BaseForm, policy: SiteSignupPolicy | None
) -> None:
    """Make first_name optional when the site's policy does not require a name."""
    from .utils import get_effective_require_name

    if not get_effective_require_name(policy):
        form.fields["first_name"].required = False
        form.fields["first_name"].label = _("First name (optional)")


def add_consent_fields(
    form: forms.BaseForm, request: HttpRequest | None, policy: SiteSignupPolicy | None
) -> None:
    """Add the Terms / Privacy clickwrap checkboxes the site's policy asks for.

    Per-site policy takes precedence; without one, ``config.REQUIRE_TERMS_ACCEPTANCE``
    applies so operators can flip consent on for every site without a row per
    site. A checkbox is only added when its document resolves, so the label
    never links to a missing page. Does nothing without a request.
    """
    from .legal_docs import has_legal_doc
    from .utils import get_effective_require_terms_acceptance

    if request is None or not get_effective_require_terms_acceptance(policy):
        return
    site = get_cached_site(request)
    if not isinstance(site, Site):
        return

    if has_legal_doc(site, "terms"):
        form.fields["accept_terms"] = forms.BooleanField(
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
        form.fields["accept_privacy"] = forms.BooleanField(
            required=True,
            label=_("I accept the Privacy Policy"),
        )
    else:
        logger.warning(
            "Site %s has require_terms_acceptance=True but no privacy "
            "doc; skipping accept_privacy checkbox",
            site.domain,
        )


CONSENT_PAIRS: tuple[tuple[str, str], ...] = (
    ("terms", "accept_terms"),
    ("privacy", "accept_privacy"),
)


def accepted_legal_docs(
    site: Site, cleaned_data: Mapping[str, object]
) -> list[tuple[str, LegalDoc]]:
    """The documents this submission consented to, with the version it saw."""
    from .legal_docs import get_legal_doc

    accepted: list[tuple[str, LegalDoc]] = []
    for doc_type, field_name in CONSENT_PAIRS:
        if not cleaned_data.get(field_name):
            continue
        doc = get_legal_doc(site, doc_type)
        if doc is not None:
            accepted.append((doc_type, doc))
    return accepted


class SiteAwareSignupForm(SignupForm):
    """allauth signup form extended for FLS:

    - Adjusts whether ``first_name`` is required based on the site's policy.
    - Adds T&C and Privacy Policy clickwrap checkboxes when the site requires
      explicit consent and the relevant docs resolve.
    - Records LegalConsent rows in ``custom_signup``.
    """

    first_name = forms.CharField(max_length=200, required=True)
    last_name = forms.CharField(max_length=200, required=False)

    fax_number = honeypot_field()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # Local imports to avoid circulars at module import time.
        from .utils import (
            get_effective_require_terms_acceptance,
            get_signup_policy_for_request,
        )

        request = _get_request_or_none()
        policy = get_signup_policy_for_request(request) if request is not None else None

        # Name handling. Per-site policy takes precedence; without one, fall
        # back to config.REQUIRE_NAME.
        apply_signup_name_policy(self, policy)

        add_consent_fields(self, request, policy)

        if get_effective_require_terms_acceptance(policy) and request is None:
            # Out-of-request construction (e.g. management command). Refuse to
            # silently skip the checkboxes — fail closed.
            raise RuntimeError(
                "SiteAwareSignupForm cannot determine the current site/policy "
                "outside of a request when require_terms_acceptance is in play. "
                "This form is only intended for use from the signup HTTP view."
            )

    def clean(self) -> dict[str, object]:
        cleaned_data: dict[str, object] = super().clean()
        reject_honeypot(self, _get_request_or_none(), HONEYPOT_SIGNUP_MESSAGE)
        return cleaned_data

    def custom_signup(self, request, user) -> None:
        """allauth hook called after the user is created.

        Records LegalConsent rows for the consents that were submitted.
        The writes are wrapped in a transaction so a partial DB failure (one
        consent saved, the other 500s) does not leave asymmetric state.
        """
        from .models import LegalConsent
        from .utils import get_client_ip

        site_obj = get_cached_site(request)
        if not isinstance(site_obj, Site):
            return

        ip = get_client_ip(request)

        with transaction.atomic():
            for doc_type, doc in accepted_legal_docs(site_obj, self.cleaned_data):
                LegalConsent.objects.create(
                    user=user,
                    document_type=doc_type,
                    document_version=doc.version,
                    git_hash=doc.git_hash,
                    ip_address=ip or None,
                    consent_method="signup_checkbox",
                )
