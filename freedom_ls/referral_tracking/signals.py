"""Signal receivers for the referral tracking app.

Connected by `ReferralTrackingConfig.ready()`. A receiver in a module nothing
imports is never connected, and fails silently rather than loudly.
"""

from __future__ import annotations

import sentry_sdk
from allauth.account.signals import user_signed_up

from django.contrib.auth.base_user import AbstractBaseUser
from django.db import DatabaseError, transaction
from django.dispatch import receiver
from django.http import HttpRequest

from freedom_ls.accounts.utils import get_client_ip
from freedom_ls.referral_tracking.capture import record_signup_attribution


@receiver(user_signed_up)
def record_attribution_on_signup(
    sender: type[AbstractBaseUser],
    request: HttpRequest,
    user: AbstractBaseUser,
    **kwargs: object,
) -> None:
    """Write the SignupAttribution row once allauth has finished the signup.

    `user_signed_up` fires after the signup form has saved the user and its
    consents, so an attribution failure cannot roll back consents that were
    already recorded. Accounts created any other way, by admin, management
    command or data import, never pass through here and get no row.

    The row is best-effort. allauth sends this signal before it logs the
    user in or sends the verification mail, so a failed write that
    propagated would leave a committed account the visitor can neither use
    nor re-register. The failure is reported to Sentry and the signup goes
    on without a row. The savepoint keeps a failed INSERT from poisoning
    whatever transaction the caller is in.
    """
    ip = get_client_ip(request)
    try:
        with transaction.atomic():
            record_signup_attribution(request=request, user=user, client_ip=ip or None)
    except DatabaseError as exc:
        sentry_sdk.capture_exception(exc)
