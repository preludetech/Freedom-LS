"""Signal receivers for the referral tracking app.

Connected by `ReferralTrackingConfig.ready()`. A receiver in a module nothing
imports is never connected, and fails silently rather than loudly.
"""

from __future__ import annotations

from allauth.account.signals import user_signed_up

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.http import HttpRequest
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.accounts.utils import get_client_ip
from freedom_ls.referral_tracking.best_effort import best_effort_write
from freedom_ls.referral_tracking.capture import record_signup_attribution
from freedom_ls.referral_tracking.conversions import (
    flush_cookie_touches,
    record_conversion,
)
from freedom_ls.referral_tracking.models import (
    ConversionKind,
    SignupAttribution,
    TouchSource,
)

SIGNUP_CONVERSION_LABEL = "Account signup"


@receiver(user_signed_up)
def record_attribution_on_signup(
    sender: type[User],
    request: HttpRequest,
    user: User,
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
    attribution: SignupAttribution | None = None
    with best_effort_write():
        attribution = record_signup_attribution(
            request=request, user=user, client_ip=ip or None
        )
    flush_cookie_touches(request=request, user=user, source=TouchSource.SIGNUP_FLUSH)
    record_conversion(
        user=user,
        kind=ConversionKind.ACCOUNT_SIGNUP,
        target=user,
        occurred_at=attribution.signed_up_at if attribution else timezone.now(),
        target_label=SIGNUP_CONVERSION_LABEL,
    )


@receiver(user_logged_in)
def flush_cookie_touches_on_login(
    sender: type[User],
    request: HttpRequest | None,
    user: User,
    **kwargs: object,
) -> None:
    """Move the attribution cookie's touches onto the account that just logged in.

    A login made outside a request passes `None`; there is no cookie to read
    then. A touch the signup already flushed is found, not written again.
    """
    flush_cookie_touches(request=request, user=user, source=TouchSource.LOGIN_FLUSH)
