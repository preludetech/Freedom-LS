"""Claiming an anonymous application: the signed link and the account it creates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from allauth.account import app_settings as allauth_account_settings
from allauth.account.models import EmailAddress
from allauth.account.signals import user_signed_up

from django.core import signing
from django.db import transaction
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.allauth_account_adapter import announce_user_registered
from freedom_ls.accounts.models import LegalConsent, User
from freedom_ls.course_applications.models import AnonymousApplicant, CourseApplication

# A namespace for the signature, not a secret.
CLAIM_TOKEN_SALT = "freedom_ls.course_applications.claim"  # noqa: S105


@dataclass(frozen=True)
class ClaimLink:
    applicant: AnonymousApplicant
    expired: bool


@dataclass(frozen=True)
class ClaimOutcome:
    user: User
    user_was_created: bool


def claim_token(applicant: AnonymousApplicant) -> str:
    return signing.dumps(str(applicant.pk), salt=CLAIM_TOKEN_SALT)


def claim_url(request: HttpRequest, applicant: AnonymousApplicant) -> str:
    return request.build_absolute_uri(
        reverse("course_applications:claim", kwargs={"token": claim_token(applicant)})
    )


def read_claim_token(token: str) -> ClaimLink | None:
    """The applicant a claim token names, and whether the token has expired.

    None for a token that was never ours, or whose applicant this site cannot
    see. The expiry matches the signup confirmation link, so one setting
    governs both.
    """
    max_age = timedelta(days=allauth_account_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS)
    try:
        pk = signing.loads(token, salt=CLAIM_TOKEN_SALT, max_age=max_age)
        expired = False
    except signing.SignatureExpired:
        # The signature is good; only its age failed. The applicant is still
        # needed, to offer a fresh link to the same address.
        pk = signing.loads(token, salt=CLAIM_TOKEN_SALT)
        expired = True
    except signing.BadSignature:
        return None
    applicant = (
        AnonymousApplicant.objects.filter(pk=pk)
        .select_related("course", "course_application__form_progress")
        .first()
    )
    return None if applicant is None else ClaimLink(applicant, expired)


def attach_claimed_application(
    request: HttpRequest, application: CourseApplication
) -> ClaimOutcome | None:
    """Attach an unverified application to the account that owns its address.

    One transaction, with the applicant row locked, so two clicks on the same
    link converge on one claim. None means nothing changed: the link was
    already used, or the address belongs to an account this site may not touch.
    """
    with transaction.atomic():
        applicant = AnonymousApplicant.objects.select_for_update().get(
            pk=application.anonymous_applicant_id
        )
        if applicant.claimed_at is not None:
            return None
        # _base_manager: the request's site filter would hide an account on
        # another site, and the globally unique email would then refuse the
        # create with an IntegrityError instead of a quiet refusal.
        if User._base_manager.filter(email__iexact=applicant.email).exists():
            return None
        user = _create_claimed_user(applicant)
        _write_legal_consents(applicant, user)
        _attach(application, applicant, user)
    announce_user_registered(request, user)
    # The attribution receiver listens here; sending the signal keeps its
    # best-effort handling rather than copying it.
    user_signed_up.send(sender=User, request=request, user=user)
    return ClaimOutcome(user, user_was_created=True)


def _attach(
    application: CourseApplication, applicant: AnonymousApplicant, user: User
) -> None:
    application.user = user
    application.save(update_fields=["user", "updated_at"])
    if application.form_progress is not None:
        application.form_progress.user = user
        application.form_progress.save(update_fields=["user", "last_updated_time"])
    applicant.user = user
    applicant.claimed_at = timezone.now()
    applicant.save(update_fields=["user", "claimed_at", "updated_at"])


def _create_claimed_user(applicant: AnonymousApplicant) -> User:
    user = User(
        email=applicant.email,
        first_name=applicant.first_name,
        last_name=applicant.last_name,
    )
    # The applicant chooses a password right after the claim; create_user
    # demands one up front, so the row is built directly.
    user.set_unusable_password()
    user.save()
    # Verified by construction: the claim link only ever went to this address.
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )
    return user


def _write_legal_consents(applicant: AnonymousApplicant, user: User) -> None:
    for doc_type, version, git_hash in (
        ("terms", applicant.terms_version, applicant.terms_git_hash),
        ("privacy", applicant.privacy_version, applicant.privacy_git_hash),
    ):
        if not version:
            continue
        LegalConsent.objects.create(
            user=user,
            document_type=doc_type,
            document_version=version,
            git_hash=git_hash,
            ip_address=applicant.consent_ip_address,
            consent_method="application_details_step",
        )
