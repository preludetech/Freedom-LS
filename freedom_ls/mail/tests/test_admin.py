"""Tests for the read-only OutboundEmail admin."""

from __future__ import annotations

import pytest

from django.core.mail import EmailMessage
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.mail.factories import OutboundEmailFactory
from freedom_ls.mail.models import OutboundEmail
from freedom_ls.mail.serialisation import serialise_message

BODY_MARKER = "zebra-crossing-body-marker"
BODY_REMOVED_NOTICE = "The body was removed."

pytestmark = pytest.mark.django_db


def changelist_url() -> str:
    return reverse("admin:freedom_ls_mail_outboundemail_changelist")


def detail_url(email: OutboundEmail) -> str:
    return reverse("admin:freedom_ls_mail_outboundemail_change", args=[email.pk])


def email_with_body_marker() -> OutboundEmail:
    """Create a pending row whose stored body is BODY_MARKER."""
    message = EmailMessage(
        subject="Welcome aboard",
        body=BODY_MARKER,
        from_email="noreply@example.test",
        to=["learner@example.test"],
    )
    OutboundEmailFactory(payload=serialise_message(message))
    return OutboundEmail.objects.get()


@pytest.fixture
def superuser_client(mock_site_context: object) -> Client:
    client = Client()
    client.force_login(UserFactory(superuser=True))
    return client


@pytest.fixture
def staff_client(mock_site_context: object) -> Client:
    client = Client()
    client.force_login(UserFactory(staff=True))
    return client


def test_staff_user_gets_403_from_changelist(staff_client: Client) -> None:
    response = staff_client.get(changelist_url())

    assert response.status_code == 403


def test_staff_user_gets_403_from_detail_page(staff_client: Client) -> None:
    email = OutboundEmailFactory()

    response = staff_client.get(detail_url(email))

    assert response.status_code == 403


def test_admin_index_hides_module_from_staff_user(staff_client: Client) -> None:
    response = staff_client.get(reverse("admin:index"))

    assert changelist_url() not in response.content.decode()


def test_superuser_gets_200_from_changelist(superuser_client: Client) -> None:
    response = superuser_client.get(changelist_url())

    assert response.status_code == 200


def test_superuser_gets_200_from_detail_page(superuser_client: Client) -> None:
    email = OutboundEmailFactory()

    response = superuser_client.get(detail_url(email))

    assert response.status_code == 200


def test_changelist_does_not_show_body(superuser_client: Client) -> None:
    email_with_body_marker()

    response = superuser_client.get(changelist_url())

    assert BODY_MARKER not in response.content.decode()


def test_detail_page_does_not_show_body(superuser_client: Client) -> None:
    email = email_with_body_marker()

    response = superuser_client.get(detail_url(email))

    assert BODY_MARKER not in response.content.decode()


def test_detail_page_of_scrubbed_row_shows_body_removed_notice(
    superuser_client: Client,
) -> None:
    email = OutboundEmailFactory(sent=True)

    response = superuser_client.get(detail_url(email))

    assert BODY_REMOVED_NOTICE in response.content.decode()


def test_detail_page_of_unscrubbed_row_omits_body_removed_notice(
    superuser_client: Client,
) -> None:
    email = OutboundEmailFactory()

    response = superuser_client.get(detail_url(email))

    assert BODY_REMOVED_NOTICE not in response.content.decode()


@pytest.mark.parametrize(
    "term",
    ["findme@example.test", "Distinctive subject line", "<findme-id@example.test>"],
    ids=["recipient", "subject", "message_id"],
)
def test_search_finds_row(superuser_client: Client, term: str) -> None:
    OutboundEmailFactory(
        recipients=["findme@example.test"],
        subject="Distinctive subject line",
        message_id="<findme-id@example.test>",
    )
    OutboundEmailFactory(subject="Other")

    response = superuser_client.get(changelist_url(), {"q": term})

    assert [row.subject for row in response.context["cl"].result_list] == [
        "Distinctive subject line"
    ]


def test_add_url_is_refused_for_superuser(superuser_client: Client) -> None:
    response = superuser_client.get(reverse("admin:freedom_ls_mail_outboundemail_add"))

    assert response.status_code == 403


def test_delete_post_is_refused_for_superuser(superuser_client: Client) -> None:
    email = OutboundEmailFactory()

    response = superuser_client.post(
        reverse("admin:freedom_ls_mail_outboundemail_delete", args=[email.pk]),
        {"post": "yes"},
    )

    assert response.status_code == 403
    assert OutboundEmail.objects.filter(pk=email.pk).exists()
