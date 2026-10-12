"""Erasing an anonymous applicant and everything they left behind."""

from __future__ import annotations

from django.db import transaction

from freedom_ls.course_applications.anonymous_session import application_of
from freedom_ls.course_applications.models import AnonymousApplicant
from freedom_ls.form_engine.models import FormProgress


def erase_anonymous_applicant(applicant: AnonymousApplicant) -> None:
    """Erase an applicant and everything they left behind.

    The application cascades from the applicant. The sitting does not: the
    application names it with RESTRICT, so it is removed by hand once the
    application is gone, which takes the answers and, through the file row's
    post_delete receiver, the stored files.

    A claimed applicant is refused: its application belongs to a user now, and
    erasing it here would take a verified person's application away while
    leaving their account standing.
    """
    if applicant.claimed_at is not None:
        raise ValueError(
            f"{applicant} has been claimed; delete the user to erase their records."
        )
    application = application_of(applicant)
    form_progress_id = application.form_progress_id if application is not None else None
    with transaction.atomic():
        applicant.delete()
        if form_progress_id is not None:
            FormProgress.objects.filter(pk=form_progress_id).delete()
