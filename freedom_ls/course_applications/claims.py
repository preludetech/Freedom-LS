"""Claiming an anonymous application: the signed link and the account it creates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

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
from freedom_ls.course_applications.applicant_email import normalise_email
from freedom_ls.course_applications.erasure import erase_anonymous_applicant
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
    # The application the account holds for the course after the claim: the
    # claimed one, or the one it already held when that one wins.
    application: CourseApplication
    # True when the claimant has no password they can be trusted to know.
    must_set_password: bool


@dataclass(frozen=True)
class AttachResult:
    # The application the account holds for the course after the attach.
    application: CourseApplication
    # True when the account's own unfinished application was deleted to make
    # room for the incoming one.
    discarded_draft: bool


def claim_token(applicant: AnonymousApplicant) -> str:
    return signing.dumps(
        {"a": str(applicant.pk), "v": applicant.claim_link_version},
        salt=CLAIM_TOKEN_SALT,
    )


def claim_url(request: HttpRequest, applicant: AnonymousApplicant) -> str:
    return request.build_absolute_uri(
        reverse("course_applications:claim", kwargs={"token": claim_token(applicant)})
    )


def _token_payload(payload: object) -> tuple[UUID, int] | None:
    """The applicant pk and link version a token names, or None for a shape
    that was never ours.

    A bare pk string is a link signed before versions existed; it reads as
    version 0, so links already in mailboxes keep working until the address
    next changes.
    """
    if isinstance(payload, str):
        pk_text, version = payload, 0
    elif isinstance(payload, dict) and isinstance(payload.get("v"), int):
        pk_text, version = str(payload.get("a", "")), payload["v"]
    else:
        return None
    try:
        return UUID(pk_text), version
    except ValueError:
        return None


def claim_link_max_age() -> timedelta:
    """How long a claim link works. It matches the signup confirmation link, so
    one setting governs both."""
    return timedelta(days=allauth_account_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS)


def claim_link_is_live(applicant: AnonymousApplicant) -> bool:
    """Whether the last link emailed to the applicant still works."""
    sent_at = applicant.claim_email_sent_at
    return sent_at is not None and sent_at > timezone.now() - claim_link_max_age()


def read_claim_token(token: str) -> ClaimLink | None:
    """The applicant a claim token names, and whether the token has expired.

    None for a token that was never ours, or whose applicant this site cannot
    see.
    """
    try:
        payload = signing.loads(
            token, salt=CLAIM_TOKEN_SALT, max_age=claim_link_max_age()
        )
        expired = False
    except signing.SignatureExpired:
        # The signature is good; only its age failed. The applicant is still
        # needed, to offer a fresh link to the same address.
        payload = signing.loads(token, salt=CLAIM_TOKEN_SALT)
        expired = True
    except signing.BadSignature:
        return None
    named = _token_payload(payload)
    if named is None:
        return None
    pk, version = named
    applicant = (
        AnonymousApplicant.objects.filter(pk=pk)
        .select_related("course", "course_application__form_progress")
        .first()
    )
    # A link whose version is behind was sent to an address the applicant has
    # since changed; it is unusable even for a fresh link, which would go to
    # that old address.
    if applicant is None or applicant.claim_link_version != version:
        return None
    return ClaimLink(applicant, expired)


def update_applicant_email(applicant: AnonymousApplicant, email: str) -> bool:
    """Change the address every claim link for this applicant is bound to.

    The version moves on so earlier links stop matching, and the sent stamp
    clears so the pages say truthfully that nothing has reached the new
    address yet. Returns False, and writes nothing, for an address equal to
    the stored one.

    The row is locked and re-read, so two changes at once each move the
    version on from the other's. The stored address, version and stamp are
    copied back onto `applicant`, so a link built from it afterwards matches
    the address it goes to.
    """
    email = normalise_email(email)
    with transaction.atomic():
        stored = AnonymousApplicant.objects.select_for_update().get(pk=applicant.pk)
        changed: bool = email != stored.email
        if changed:
            stored.email = email
            stored.claim_link_version += 1
            stored.claim_email_sent_at = None
            stored.save(
                update_fields=[
                    "email",
                    "claim_link_version",
                    "claim_email_sent_at",
                    "updated_at",
                ]
            )
    applicant.email = stored.email
    applicant.claim_link_version = stored.claim_link_version
    applicant.claim_email_sent_at = stored.claim_email_sent_at
    return changed


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
    request: HttpRequest, application: CourseApplication, *, link_version: int
) -> ClaimOutcome | None:
    """Attach an unverified application to the account that owns its address.

    An address with no account gets a new one. An account that has verified
    the address is attached as it stands: its profile and password are
    untouched, no consent is written and no sign-up is announced, because the
    person already registered. An account that never verified it has the
    address verified by this claim and its password revoked: whoever set that
    password, through signup or by hand, never proved they owned the mailbox,
    and the claimant has just done so, so they choose the password. The
    consent the claimant gave at the details step is written to that account
    too: any consent already on it was given by whoever set the password.

    One transaction, with the applicant row locked, so two clicks on the same
    link converge on one claim. The lock covers one applicant, not the
    address: a signup, or the claim of another application under the same
    address, can take the address between the lookup and the create. The
    account that did is then the owner, and the application goes to it.
    None means nothing changed: the link was already used, the address it
    went to has since changed (`link_version` is the version the link carried,
    checked again under the lock), or the address belongs to an account on
    another site.
    """
    with transaction.atomic():
        applicant = AnonymousApplicant.objects.select_for_update().get(
            pk=application.anonymous_applicant_id
        )
        if (
            applicant.claimed_at is not None
            or applicant.claim_link_version != link_version
        ):
            return None
        owner = resolve_claim_owner(applicant)
        if owner is not None and owner.user.site_id != applicant.site_id:
            return None
        try:
            user = _user_for_claim(applicant, owner)
        except IntegrityError:
            owner = resolve_claim_owner(applicant)
            if owner is None or owner.user.site_id != applicant.site_id:
                return None
            user = _user_for_claim(applicant, owner)
        if user is None:
            return None
        attached = attach_to_user(application, applicant, user)
    if owner is None:
        announce_user_registered(request, user)
        # The attribution receiver listens here; sending the signal keeps its
        # best-effort handling rather than copying it.
        user_signed_up.send(sender=User, request=request, user=user)
    return ClaimOutcome(
        user,
        application=attached.application,
        must_set_password=claim_sets_a_password(owner),
    )


def _user_for_claim(
    applicant: AnonymousApplicant, owner: ClaimOwner | None
) -> User | None:
    """The account the claim attaches to: made for the address, or made the
    claimant's by verifying it.

    Raises IntegrityError when the address gained an account during the
    create. None when another account verified the address between the
    lookup and the write; the link is unusable rather than half-applied.
    """
    if owner is None:
        user = _create_claimed_user(applicant)
        _write_legal_consents(applicant, user)
        return user
    if not owner.verified:
        try:
            _verify_address_by_claim(owner, applicant.email)
        except IntegrityError:
            return None
        _write_legal_consents(applicant, owner.user)
    return owner.user


def attach_to_user(
    application: CourseApplication, applicant: AnonymousApplicant, user: User
) -> AttachResult:
    """Hand an anonymous application, its sitting and its applicant to an account.

    Returns the application the account holds for the course afterwards. An
    account holds one application per course, so when it already holds one,
    one of the two goes: a submitted application beats a draft, and between
    two drafts the incoming one stays, because the applicant has just been
    working on it. A draft the account loses goes with its sitting. An
    incoming application that loses goes with its applicant, as if it had
    never been made; the consent it carried was already written to the
    account by the caller.

    One transaction, with the account's row locked, so two attachments for
    one course cannot both find the account empty: the second waits, then
    finds what the first attached.
    """
    with transaction.atomic():
        # The lookup below locks the held application, which is nothing when
        # the account holds none; the user row is the one lock both see.
        list(User._base_manager.filter(pk=user.pk).select_for_update())
        held: CourseApplication | None = (
            CourseApplication.objects.select_for_update(of=("self",))
            .select_related("form_progress")
            .filter(user=user, course_id=application.course_id)
            .exclude(pk=application.pk)
            .first()
        )
        if held is not None:
            if held.is_submitted:
                # A request already made stands; the incoming one could only
                # repeat or precede it, so it goes with its applicant.
                erase_anonymous_applicant(applicant)
                return AttachResult(held, discarded_draft=False)
            # The account's draft gives way: the applicant has just been
            # working on the incoming one, whether that is further along or a
            # submission.
            _discard_draft(held)
        application.user = user
        application.save(update_fields=["user", "updated_at"])
        if application.form_progress is not None:
            application.form_progress.user = user
            application.form_progress.save(update_fields=["user", "last_updated_time"])
        applicant.user = user
        applicant.claimed_at = timezone.now()
        applicant.save(update_fields=["user", "claimed_at", "updated_at"])
    return AttachResult(application, discarded_draft=held is not None)


def _discard_draft(draft: CourseApplication) -> None:
    """Delete a draft with the sitting it owns.

    The application goes first, because the sitting is RESTRICT. The sitting
    is deleted here rather than by the application's post-delete receiver,
    which leaves a sitting with a user for that user to reach; this one is
    about to have nothing reaching it.
    """
    sitting = draft.form_progress
    draft.delete()
    if sitting is not None:
        sitting.delete()


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
    # A savepoint, so the unique-address refusal the caller handles leaves
    # the claim's transaction usable.
    with transaction.atomic():
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
