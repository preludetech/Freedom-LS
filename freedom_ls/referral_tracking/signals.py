"""Signal receivers for the referral tracking app.

Connected by `ReferralTrackingConfig.ready()`. A receiver in a module nothing
imports is never connected, and fails silently rather than loudly.
"""

from __future__ import annotations

from allauth.account.signals import user_signed_up

from django.contrib.auth.base_user import AbstractBaseUser
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
    """
    ip = get_client_ip(request)
    record_signup_attribution(request=request, user=user, client_ip=ip or None)
