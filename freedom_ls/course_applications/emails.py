"""Emails sent to anonymous applicants."""

from __future__ import annotations

from allauth.account.adapter import get_adapter
from allauth.core import ratelimit

from django.http import HttpRequest

from freedom_ls.course_applications.applicant_email import email_rate_limit_key
from freedom_ls.course_applications.claims import claim_url
from freedom_ls.course_applications.models import AnonymousApplicant
from freedom_ls.site_aware_models.models import site_display_name_for_request


def send_application_claim_email(
    request: HttpRequest, applicant: AnonymousApplicant
) -> None:
    """Email the applicant the link that attaches their application to an account.

    The same email goes to every applicant, whether or not the address already
    has an account, so nothing about the send depends on what the mailbox
    owner will find out when they follow it. Once the per-address limit is
    hit the send is skipped and the caller's page is unchanged; a different
    response would say which addresses are busy.
    """
    allowed: bool = ratelimit.consume(
        request,
        action="application_claim_email",
        key=email_rate_limit_key(applicant.site, applicant.email),
    )
    if not allowed:
        return
    get_adapter(request).send_mail(
        "course_applications/email/application_claim",
        applicant.email,
        {
            "course": applicant.course,
            "claim_url": claim_url(request, applicant),
            "site_name": site_display_name_for_request(request),
        },
    )
