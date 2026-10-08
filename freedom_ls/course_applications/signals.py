"""Receivers that claim a browser's applications when its visitor signs in."""

from __future__ import annotations

import sentry_sdk

from django.db import DatabaseError
from django.http import HttpRequest

from freedom_ls.accounts.models import User
from freedom_ls.course_applications.claims import (
    claim_unclaimed_applications,
    unclaimed_application_ids,
)


def claim_on_login(
    sender: type[User], request: HttpRequest, user: User, **kwargs: object
) -> None:
    """Claim this browser's applications on login without ever failing the login.

    A database error is reported to Sentry and the application stays
    unclaimed, so the landing page can retry.
    """
    if not unclaimed_application_ids(request):
        return
    try:
        claim_unclaimed_applications(request, user)
    except DatabaseError as exc:
        sentry_sdk.capture_exception(exc)
