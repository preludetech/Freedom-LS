"""Erasing an anonymous applicant and everything they left behind."""

from __future__ import annotations

from django.db.models import QuerySet

from freedom_ls.accounts.models import User
from freedom_ls.course_applications.models import AnonymousApplicant


def unclaimed_applicants_with_address(user: User) -> QuerySet[AnonymousApplicant]:
    """The unclaimed applicants who applied with this user's email address.

    The cascade from a user only reaches applicants a claim linked to the
    account. Ones the same address applied with and never claimed are tied to
    the person by nothing but that address, so they are found by it, on the
    user's own site. _base_manager: inside a request the default manager
    filters on the request's site, not the user's.
    """
    return AnonymousApplicant._base_manager.filter(
        site_id=user.site_id, email=user.email.lower(), user__isnull=True
    )


def erase_anonymous_applicant(applicant: AnonymousApplicant) -> None:
    """Erase an applicant and everything they left behind.

    The application cascades from the applicant, and the application's own
    post-delete receiver removes the user-less sitting, which takes the
    answers and, through the file row's post_delete receiver, the stored
    files.

    A claimed applicant is refused: its application belongs to a user now, and
    erasing it here would take a verified person's application away while
    leaving their account standing. Erasing those records means erasing the
    account.
    """
    if applicant.claimed_at is not None:
        raise ValueError(
            f"{applicant} has been claimed; its records belong to a user account now."
        )
    applicant.delete()
