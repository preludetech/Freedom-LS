"""Claiming an anonymous application: the signed link and the account it creates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from allauth.account import app_settings as allauth_account_settings
from allauth.account.models import EmailAddress
from allauth.account.signals import user_signed_up

from django.core import signing
from django.db import IntegrityError, transaction
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
class ClaimOwner:
    """The account an applicant's address already belongs to.

    `verified` is whether that account has proven it owns the address. An
    account that has not (an allauth signup nobody confirmed, or an account an
    operator created by hand) still owns the address for login purposes, but
    the claim is the first proof that the mailbox is really theirs.
    """

    user: User
    verified: bool


def claim_sets_a_password(owner: ClaimOwner | None) -> bool:
    """Whether the claimant will choose a password once the claim goes through.

    True for an address with no account, for one that never verified the
    address (its password was set by somebody who never proved they owned the
    mailbox, so the claim revokes it) and for one with no usable password (an
    earlier claim that never reached the set-password page).
    """
    return owner is None or not owner.verified or not owner.user.has_usable_password()


@dataclass(frozen=True)
class ClaimOutcome:
    user: User
    # True when the claimant has no password they can be trusted to know.
    must_set_password: bool


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


def resolve_claim_owner(applicant: AnonymousApplicant) -> ClaimOwner | None:
    """The account that already holds the applicant's address, on any site.

    Ownership is a verified allauth address or the address an account logs in
    with. An unverified secondary address is neither: anyone can add one to
    their account, so it must not hand them someone else's application.

    _base_manager, because the request's site filter would hide an account on
    another site, and the globally unique email would then refuse the create
    with an IntegrityError instead of a quiet refusal.
    """
    # iexact throughout: an operator can store an address with capitals, and
    # the applicant's copy is always lowercased.
    verified = (
        EmailAddress.objects.filter(email__iexact=applicant.email, verified=True)
        .select_related("user")
        .first()
    )
    if verified is not None:
        return ClaimOwner(verified.user, verified=True)
    login_owner = User._base_manager.filter(email__iexact=applicant.email).first()
    if login_owner is None:
        return None
    return ClaimOwner(login_owner, verified=False)


def attach_claimed_application(
    request: HttpRequest, application: CourseApplication
) -> ClaimOutcome | None:
    """Attach an unverified application to the account that owns its address.

    An address with no account gets a new one. An account that has verified
    the address is attached as it stands: its profile and password are
    untouched, no consent is written and no sign-up is announced, because the
    person already registered. An account that never verified it has the
    address verified by this claim and its password revoked: whoever set that
    password, through signup or by hand, never proved they owned the mailbox,
    and the claimant has just done so, so they choose the password.

    One transaction, with the applicant row locked, so two clicks on the same
    link converge on one claim. None means nothing changed: the link was
    already used, or the address belongs to an account on another site.
    """
    with transaction.atomic():
        applicant = AnonymousApplicant.objects.select_for_update().get(
            pk=application.anonymous_applicant_id
        )
        if applicant.claimed_at is not None:
            return None
        owner = resolve_claim_owner(applicant)
        if owner is not None and owner.user.site_id != applicant.site_id:
            return None
        if owner is None:
            user = _create_claimed_user(applicant)
            _write_legal_consents(applicant, user)
        else:
            user = owner.user
            if not owner.verified:
                try:
                    _verify_address_by_claim(owner, applicant.email)
                except IntegrityError:
                    # Another account verified this address between the lookup
                    # and the write; the link is unusable rather than half-applied.
                    return None
        attach_to_user(application, applicant, user)
    if owner is None:
        announce_user_registered(request, user)
        # The attribution receiver listens here; sending the signal keeps its
        # best-effort handling rather than copying it.
        user_signed_up.send(sender=User, request=request, user=user)
    return ClaimOutcome(user, must_set_password=claim_sets_a_password(owner))


def attach_to_user(
    application: CourseApplication, applicant: AnonymousApplicant, user: User
) -> None:
    """Hand an anonymous application, its sitting and its applicant to an account."""
    application.user = user
    application.save(update_fields=["user", "updated_at"])
    if application.form_progress is not None:
        application.form_progress.user = user
        application.form_progress.save(update_fields=["user", "last_updated_time"])
    applicant.user = user
    applicant.claimed_at = timezone.now()
    applicant.save(update_fields=["user", "claimed_at", "updated_at"])


def _verify_address_by_claim(owner: ClaimOwner, email: str) -> None:
    """Mark an unverified address verified on the strength of the claim link.

    The row is matched case-insensitively and kept as spelled, so an account
    an operator created with capitals in the address ends up with one row,
    not two. The password is revoked whatever created the account: nobody who
    set it proved they owned the mailbox.
    """
    with transaction.atomic():
        address = EmailAddress.objects.filter(
            user=owner.user, email__iexact=email
        ).first()
        if address is None:
            address = EmailAddress.objects.create(
                user=owner.user, email=email, verified=True
            )
        else:
            address.verified = True
            address.save(update_fields=["verified"])
    address.set_as_primary(conditional=True)
    owner.user.set_unusable_password()
    owner.user.save(update_fields=["password"])


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
