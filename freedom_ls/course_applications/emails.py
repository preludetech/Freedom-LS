"""Emails sent to anonymous applicants."""

from __future__ import annotations

from allauth.account.adapter import get_adapter
from allauth.core import ratelimit

from django.http import HttpRequest
from django.utils import timezone

from freedom_ls.course_applications.applicant_email import email_rate_limit_key
from freedom_ls.course_applications.claims import claim_url
from freedom_ls.course_applications.models import AnonymousApplicant
from freedom_ls.mail.backends import QueuedEmailNotSentError
from freedom_ls.site_aware_models.models import site_display_name_for_request


def send_application_claim_email(
    request: HttpRequest, applicant: AnonymousApplicant, *, is_submitted: bool
) -> bool:
    """Email the applicant the link that attaches their application to an account.

    The same email goes to every applicant, whether or not the address already
    has an account, so nothing about the send depends on what the mailbox
    owner will find out when they follow it. False means no email went out:
    the per-address limit was hit, or the mail backend refused the message.
    The applicant is stamped only for a send that went out, so the status
    page can say the email did not and offer to send it again.

    The wording follows `is_submitted`, which the caller knows from the
    application it holds. The email holds only the course title, site name and
    link: an address typed by any visitor can receive it, so nothing the
    applicant entered goes into it.
    """
    allowed: bool = ratelimit.consume(
        request,
        action="application_claim_email",
        key=email_rate_limit_key(applicant.site, applicant.email),
    )
    if not allowed:
        return False
    try:
        get_adapter(request).send_mail(
            "course_applications/email/application_claim",
            applicant.email,
            {
                "course": applicant.course,
                "claim_url": claim_url(request, applicant),
                "site_name": site_display_name_for_request(request),
                # The shared greeting reads `user`, which the request context
                # would otherwise fill with whoever is signed in to this browser.
                "user": None,
                "is_submitted": is_submitted,
            },
        )
    # SMTP errors are OSErrors; the queued backend raises its own when the
    # upstream send fails inline. The application is already stored, so a
    # refused email is reported, not a crash.
    except (OSError, QueuedEmailNotSentError):
        return False
    applicant.claim_email_sent_at = timezone.now()
    applicant.save(update_fields=["claim_email_sent_at", "updated_at"])
    return True
