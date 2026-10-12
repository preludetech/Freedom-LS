"""Erasing an anonymous applicant and everything they left behind."""

from __future__ import annotations

from freedom_ls.course_applications.models import AnonymousApplicant


def erase_anonymous_applicant(applicant: AnonymousApplicant) -> None:
    """Erase an applicant and everything they left behind.

    The application cascades from the applicant, and the application's own
    post-delete receiver removes the user-less sitting, which takes the
    answers and, through the file row's post_delete receiver, the stored
    files.

    A claimed applicant is refused: its application belongs to a user now, and
    erasing it here would take a verified person's application away while
    leaving their account standing.
    """
    if applicant.claimed_at is not None:
        raise ValueError(
            f"{applicant} has been claimed; delete the user to erase their records."
        )
    applicant.delete()
