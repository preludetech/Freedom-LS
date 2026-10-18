"""Account setup state for users created by staff."""

from __future__ import annotations

from allauth.account import app_settings as allauth_account_settings
from allauth.account.adapter import get_adapter
from allauth.account.forms import default_token_generator
from allauth.account.models import EmailAddress
from allauth.account.utils import user_pk_to_url_str

from django.conf import settings
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.urls import reverse

from freedom_ls.accounts.config import config
from freedom_ls.accounts.models import User, UserManager


class EmailInUseOnAnotherSite(Exception):  # noqa: N818
    """The address belongs to a user on a different site."""


class AccountAlreadySetUp(Exception):  # noqa: N818
    """The user has already logged in or set a password."""


class SetupEmailRecentlySent(Exception):  # noqa: N818
    """A setup email went out inside the resend window."""


def pending_user_q(prefix: str = "") -> Q:
    """Q matching users who have never logged in and cannot: staff-created
    accounts whose setup link is still the only way in."""
    return Q(
        **{
            f"{prefix}last_login__isnull": True,
            f"{prefix}password__startswith": UNUSABLE_PASSWORD_PREFIX,
        }
    )


def is_pending(user: User) -> bool:
    return user.last_login is None and not user.has_usable_password()


def match_or_create_user(
    site: Site, email: str, first_name: str = "", last_name: str = ""
) -> tuple[User, bool]:
    """Find the user for an address, or make a pending one on `site`.

    The lookup spans every site on purpose: an address is unique across the
    installation, so a match on another site must be refused, not duplicated.
    Names are only used for a new user; an existing user keeps their own.
    """
    address = UserManager.normalize_email(email.strip())
    existing = User._base_manager.filter(email__iexact=address).first()
    if existing is not None:
        if existing.site_id != site.pk:
            raise EmailInUseOnAnotherSite(address)
        return existing, False
    user = User(site=site, email=address, first_name=first_name, last_name=last_name)
    user.set_unusable_password()
    user.save()
    EmailAddress.objects.create(user=user, email=address, verified=True, primary=True)
    return user, True


def _guard_key(user: User) -> str:
    return f"account-setup-email:{user.pk}"


def _send(user: User, organisation_name: str) -> None:
    timeout = settings.PASSWORD_RESET_TIMEOUT
    path = reverse(
        "account_reset_password_from_key",
        kwargs={
            "uidb36": user_pk_to_url_str(user),
            "key": default_token_generator.make_token(user),
        },
    )
    context = {
        "user": user,
        "organisation_name": organisation_name,
        "setup_url": f"{allauth_account_settings.DEFAULT_HTTP_PROTOCOL}://{user.site.domain}{path}",
        "expires_in_days": max(1, timeout // 86400),
    }
    transaction.on_commit(
        lambda: get_adapter().send_mail(
            "account/email/account_setup", user.email, context
        )
    )


def send_account_setup_email(user: User, organisation_name: str) -> None:
    """Email a pending user a link that sets their password and logs them in.

    Sent on commit, with no request in scope. Starts the resend window on
    commit too, so a rolled-back send never blocks a resend.
    """
    if not is_pending(user):
        raise AccountAlreadySetUp(user.email)
    transaction.on_commit(
        lambda: cache.set(_guard_key(user), 1, config.SETUP_EMAIL_RESEND_SECONDS)
    )
    _send(user, organisation_name)


def resend_account_setup_email(user: User, organisation_name: str) -> None:
    """Send the setup email again, unless one went out inside the resend window."""
    if not is_pending(user):
        raise AccountAlreadySetUp(user.email)
    if not cache.add(_guard_key(user), 1, config.SETUP_EMAIL_RESEND_SECONDS):
        raise SetupEmailRecentlySent(user.email)
    _send(user, organisation_name)
