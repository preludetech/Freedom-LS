"""Tests for accounts.account_setup."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import cast
from urllib.parse import urlparse

import pytest
import time_machine
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.core import mail
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.account_setup import (
    AccountAlreadySetUp,
    EmailInUseOnAnotherSite,
    SetupEmailRecentlySent,
    is_pending,
    lookup_user,
    match_or_create_user,
    pending_user_q,
    resend_account_setup_email,
    send_account_setup_email,
)
from freedom_ls.accounts.config import config
from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.tests.factories import SiteFactory


def _pending_user() -> User:
    user = cast(User, UserFactory())
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return user


def _self_signup_never_logged_in() -> User:
    return cast(User, UserFactory(last_login=None))


def _admin_made_with_typed_password() -> User:
    return cast(
        User,
        UserFactory(
            password="typed-password-1",  # pragma: allowlist secret
            last_login=None,
        ),
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("make_user", "expected"),
    [
        (_pending_user, True),
        (_self_signup_never_logged_in, False),
        (_admin_made_with_typed_password, False),
    ],
)
def test_is_pending_and_pending_user_q_agree(
    mock_site_context, make_user, expected: bool
) -> None:
    user = make_user()

    assert is_pending(user) is expected
    assert User.objects.filter(pending_user_q(), pk=user.pk).exists() is expected


@pytest.mark.django_db
def test_a_user_who_has_logged_in_is_not_pending(mock_site_context) -> None:
    user = _pending_user()
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])

    assert is_pending(user) is False
    assert not User.objects.filter(pending_user_q(), pk=user.pk).exists()


@pytest.fixture(autouse=True)
def _clear_resend_guard():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_lookup_user_matches_case_insensitively_with_whitespace(
    mock_site_context: Site,
) -> None:
    existing = UserFactory(email="Learner@Example.com")

    assert lookup_user(mock_site_context, "  learner@example.COM ") == existing


@pytest.mark.django_db
def test_lookup_user_returns_none_for_an_unknown_address_and_creates_nothing(
    mock_site_context: Site,
) -> None:
    before = User._base_manager.count()

    found = lookup_user(mock_site_context, "nobody@example.com")

    assert (found, User._base_manager.count()) == (None, before)


@pytest.mark.django_db
def test_lookup_user_raises_for_another_sites_user_carrying_only_the_address(
    mock_site_context: Site,
) -> None:
    other_site = SiteFactory()
    User._base_manager.create(
        site=other_site, email="away@example.com", first_name="Away"
    )

    with pytest.raises(EmailInUseOnAnotherSite) as raised:
        lookup_user(mock_site_context, " away@Example.com ")

    assert raised.value.args == ("away@example.com",)


@pytest.mark.django_db
def test_match_or_create_user_returns_a_new_user_flagged_created(
    mock_site_context: Site,
) -> None:
    user, created = match_or_create_user(mock_site_context, "new@example.com")

    assert (user.email, created) == ("new@example.com", True)


@pytest.mark.django_db
def test_match_or_create_user_matches_case_insensitively_with_whitespace(
    mock_site_context: Site,
) -> None:
    existing = UserFactory(email="Learner@Example.com")

    user, created = match_or_create_user(mock_site_context, "  learner@example.COM ")

    assert (user.pk, created) == (existing.pk, False)


@pytest.mark.django_db
def test_match_or_create_user_leaves_existing_names_alone(
    mock_site_context: Site,
) -> None:
    existing = UserFactory(email="named@example.com", first_name="Ada", last_name="L")

    user, _ = match_or_create_user(
        mock_site_context, "named@example.com", "Other", "Person"
    )

    assert (user.first_name, user.last_name) == (existing.first_name, "L")


@pytest.mark.django_db
def test_match_or_create_user_raises_for_an_address_on_another_site(
    mock_site_context: Site,
) -> None:
    other_site = SiteFactory()
    User._base_manager.create(site=other_site, email="away@example.com")

    with pytest.raises(EmailInUseOnAnotherSite):
        match_or_create_user(mock_site_context, "away@example.com")


@pytest.mark.django_db
def test_match_or_create_user_creates_on_the_passed_site_under_another_sites_request(
    mock_site_context: Site, site_aware_request
) -> None:
    other_site = SiteFactory()
    request = site_aware_request.get("/")
    request.site = other_site

    user, created = match_or_create_user(other_site, "fresh@example.com", "Fay", "B")

    assert (created, user.site_id, user.first_name) == (True, other_site.pk, "Fay")


@pytest.mark.django_db
def test_match_or_create_user_gives_a_new_user_an_unusable_password(
    mock_site_context: Site,
) -> None:
    user, _ = match_or_create_user(mock_site_context, "new@example.com")

    assert is_pending(user)


@pytest.mark.django_db
def test_match_or_create_user_gives_a_new_user_a_verified_primary_address(
    mock_site_context: Site,
) -> None:
    user, _ = match_or_create_user(mock_site_context, "new@example.com")

    address = EmailAddress.objects.get(user=user)
    assert (address.email, address.verified, address.primary) == (
        "new@example.com",
        True,
        True,
    )


def _setup_link() -> str:
    match = re.search(r"https?://\S+/reset/key/\S+", mail.outbox[0].body)
    assert match is not None
    return match.group(0)


def _pending(site: Site, email: str = "setup@example.com") -> User:
    user, _ = match_or_create_user(site, email, "Sam", "Q")
    return user


@pytest.mark.django_db
def test_send_account_setup_email_sends_one_message_after_commit(
    mock_site_context: Site, django_capture_on_commit_callbacks
) -> None:
    user = _pending(mock_site_context)

    with django_capture_on_commit_callbacks(execute=True):
        send_account_setup_email(user, "Acme Academy")

    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_send_account_setup_email_uses_the_site_subject_prefix(
    mock_site_context: Site, django_capture_on_commit_callbacks, settings
) -> None:
    settings.HEADER_TITLE = ""
    user = _pending(mock_site_context)

    with django_capture_on_commit_callbacks(execute=True):
        send_account_setup_email(user, "Acme Academy")

    assert mail.outbox[0].subject.startswith(f"[{mock_site_context.name}] ")


@pytest.mark.django_db
def test_send_account_setup_email_links_on_the_users_site_domain(
    mock_site_context: Site, django_capture_on_commit_callbacks
) -> None:
    user = _pending(mock_site_context)

    with django_capture_on_commit_callbacks(execute=True):
        send_account_setup_email(user, "Acme Academy")

    assert urlparse(_setup_link()).netloc == mock_site_context.domain


@pytest.mark.django_db
def test_send_account_setup_email_names_the_organisation_and_expiry(
    mock_site_context: Site, django_capture_on_commit_callbacks, settings
) -> None:
    settings.PASSWORD_RESET_TIMEOUT = 3 * 86400
    user = _pending(mock_site_context)

    with django_capture_on_commit_callbacks(execute=True):
        send_account_setup_email(user, "Acme Academy")

    body = mail.outbox[0].body
    assert ("Acme Academy" in body, "3 days" in body) == (True, True)


class _RollBack(Exception):  # noqa: N818
    pass


def _send_then_roll_back(user: User) -> None:
    with transaction.atomic():
        send_account_setup_email(user, "Acme Academy")
        raise _RollBack


@pytest.mark.django_db(transaction=True)
def test_send_account_setup_email_sends_nothing_when_the_transaction_rolls_back(
    mock_site_context: Site,
) -> None:
    user = _pending(mock_site_context)

    with pytest.raises(_RollBack):
        _send_then_roll_back(user)

    assert mail.outbox == []


@pytest.mark.django_db(transaction=True)
def test_a_rolled_back_send_leaves_resending_open(
    mock_site_context: Site, django_capture_on_commit_callbacks
) -> None:
    user = _pending(mock_site_context)
    with pytest.raises(_RollBack):
        _send_then_roll_back(user)

    with django_capture_on_commit_callbacks(execute=True):
        resend_account_setup_email(user, "Acme Academy")

    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_send_account_setup_email_raises_for_a_user_who_is_not_pending(
    mock_site_context: Site,
) -> None:
    user = UserFactory()

    with pytest.raises(AccountAlreadySetUp):
        send_account_setup_email(user, "Acme Academy")


@pytest.mark.django_db
def test_resend_inside_the_window_raises_and_sends_nothing(
    mock_site_context: Site, django_capture_on_commit_callbacks
) -> None:
    user = _pending(mock_site_context)
    with django_capture_on_commit_callbacks(execute=True):
        send_account_setup_email(user, "Acme Academy")
    mail.outbox.clear()

    with pytest.raises(SetupEmailRecentlySent):
        resend_account_setup_email(user, "Acme Academy")

    assert mail.outbox == []


@pytest.mark.django_db
def test_resend_after_the_window_sends(
    mock_site_context: Site, django_capture_on_commit_callbacks
) -> None:
    user = _pending(mock_site_context)
    with django_capture_on_commit_callbacks(execute=True):
        send_account_setup_email(user, "Acme Academy")
    mail.outbox.clear()

    with (
        time_machine.travel(
            timezone.now() + timedelta(seconds=config.SETUP_EMAIL_RESEND_SECONDS + 1)
        ),
        django_capture_on_commit_callbacks(execute=True),
    ):
        resend_account_setup_email(user, "Acme Academy")

    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_resend_raises_for_a_user_who_is_not_pending(mock_site_context: Site) -> None:
    user = UserFactory()

    with pytest.raises(AccountAlreadySetUp):
        resend_account_setup_email(user, "Acme Academy")


@pytest.mark.django_db
def test_following_the_setup_link_sets_a_password_and_logs_the_user_in(
    mock_site_context: Site, django_capture_on_commit_callbacks
) -> None:
    user = _pending(mock_site_context)
    with django_capture_on_commit_callbacks(execute=True):
        send_account_setup_email(user, "Acme Academy")
    link = _setup_link()
    client = Client()

    page = client.get(urlparse(link).path, follow=True)
    new_password = "a-long-fresh-passphrase-9"  # pragma: allowlist secret  # noqa: S105
    client.post(
        page.request["PATH_INFO"],
        {"password1": new_password, "password2": new_password},
    )

    user.refresh_from_db()
    assert (
        client.session.get("_auth_user_id") == str(user.pk),
        is_pending(user),
    ) == (True, False)


@pytest.mark.django_db
def test_setting_a_first_password_sends_a_branded_confirmation_email(
    mock_site_context: Site, django_capture_on_commit_callbacks
) -> None:
    user = _pending(mock_site_context)
    with django_capture_on_commit_callbacks(execute=True):
        send_account_setup_email(user, "Acme Academy")
    link = _setup_link()
    client = Client()
    page = client.get(urlparse(link).path, follow=True)
    new_password = "a-long-fresh-passphrase-9"  # pragma: allowlist secret  # noqa: S105

    client.post(
        page.request["PATH_INFO"],
        {"password1": new_password, "password2": new_password},
    )

    assert len(mail.outbox) == 2
    message = mail.outbox[1]
    assert isinstance(message, EmailMultiAlternatives)
    html, mimetype = message.alternatives[0]
    assert isinstance(html, str)
    assert message.subject.endswith("] Your password has been set")
    assert ("Hi Sam," in message.body, "Cheers," in message.body) == (True, True)
    assert (mimetype, "Your password has been set" in html, "Hi Sam," in html) == (
        "text/html",
        True,
        True,
    )


@pytest.mark.django_db
def test_forgot_password_form_sends_a_reset_link_to_a_pending_user(
    mock_site_context: Site, site_aware_request
) -> None:
    _pending(mock_site_context, "forgot@example.com")
    client = Client()

    client.post(reverse("account_reset_password"), {"email": "forgot@example.com"})

    assert len(mail.outbox) == 1
