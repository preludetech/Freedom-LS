"""Tests for the read-only OutboundEmail admin."""

from __future__ import annotations

import pytest

from django.contrib import admin
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.messages import get_messages
from django.core.mail import EmailMessage
from django.test import Client, RequestFactory
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.mail.admin import OutboundEmailAdmin, resend_blocker
from freedom_ls.mail.factories import OutboundEmailFactory
from freedom_ls.mail.models import OutboundEmail
from freedom_ls.mail.serialisation import serialise_message

BODY_MARKER = "zebra-crossing-body-marker"
BODY_REMOVED_NOTICE = "The body was removed."

Status = OutboundEmail.Status

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


def test_changelist_lists_row_subject_and_recipient(superuser_client: Client) -> None:
    OutboundEmailFactory(
        subject="Listed subject line", recipients=["listed@example.test"]
    )

    response = superuser_client.get(changelist_url())

    content = response.content.decode()
    assert "Listed subject line" in content
    assert "listed@example.test" in content


def test_detail_page_renders_fields_read_only(superuser_client: Client) -> None:
    email = OutboundEmailFactory(subject="Read only subject")

    response = superuser_client.get(detail_url(email))

    content = response.content.decode()
    assert "Read only subject" in content
    assert 'name="subject"' not in content
    assert 'name="_save"' not in content


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


def resend_selected(client: Client, *emails: OutboundEmail) -> object:
    return client.post(
        changelist_url(),
        {
            "action": "resend_selected",
            "_selected_action": [str(email.pk) for email in emails],
        },
        follow=True,
    )


def message_texts(response: object) -> list[str]:
    return [str(message) for message in get_messages(response.wsgi_request)]


@pytest.mark.parametrize(
    ("traits", "expected"),
    [
        ({}, "in flight"),
        ({"sending": True}, "in flight"),
        ({"failed": True}, "in flight"),
        ({"sent": True}, "already sent"),
        ({"permanent_failure": True}, None),
        ({"dead_letter": True}, None),
        ({"dead_letter": True, "scrubbed": True}, "body removed"),
    ],
    ids=[
        "pending",
        "sending",
        "failed",
        "sent",
        "permanent_failure",
        "dead_letter",
        "scrubbed_dead_letter",
    ],
)
def test_resend_blocker_reason_per_row_state(
    traits: dict[str, bool], expected: str | None
) -> None:
    email = OutboundEmailFactory.build(**traits)

    assert resend_blocker(email) == expected


def test_resend_puts_failed_rows_back_to_pending_with_fresh_ladder(
    superuser_client: Client, database_task_backend: None
) -> None:
    permanent = OutboundEmailFactory(permanent_failure=True)
    dead = OutboundEmailFactory(dead_letter=True)

    resend_selected(superuser_client, permanent, dead)

    permanent.refresh_from_db()
    dead.refresh_from_db()
    assert [permanent.status, dead.status] == [Status.PENDING, Status.PENDING]
    assert [permanent.attempt_count, dead.attempt_count] == [0, 0]
    assert permanent.next_attempt_at > permanent.last_attempt_at


def test_resend_enqueues_one_task_per_row_on_commit(
    superuser_client: Client,
    database_task_backend: None,
    django_capture_on_commit_callbacks,
) -> None:
    from django_tasks_db.models import DBTaskResult

    permanent = OutboundEmailFactory(permanent_failure=True)
    dead = OutboundEmailFactory(dead_letter=True)

    with django_capture_on_commit_callbacks(execute=True):
        resend_selected(superuser_client, permanent, dead)

    queued = [row.args_kwargs for row in DBTaskResult.objects.all()]
    assert sorted(queued, key=str) == sorted(
        [
            {"args": [str(permanent.pk)], "kwargs": {}},
            {"args": [str(dead.pk)], "kwargs": {}},
        ],
        key=str,
    )


def test_resend_writes_one_log_entry_per_row(
    superuser_client: Client, database_task_backend: None
) -> None:
    permanent = OutboundEmailFactory(permanent_failure=True)
    dead = OutboundEmailFactory(dead_letter=True)

    resend_selected(superuser_client, permanent, dead)

    entries = LogEntry.objects.filter(action_flag=CHANGE)
    assert sorted(entry.object_id for entry in entries) == sorted(
        [str(permanent.pk), str(dead.pk)]
    )


def test_resend_reports_how_many_were_queued(
    superuser_client: Client, database_task_backend: None
) -> None:
    permanent = OutboundEmailFactory(permanent_failure=True)
    dead = OutboundEmailFactory(dead_letter=True)

    response = resend_selected(superuser_client, permanent, dead)

    assert message_texts(response) == ["2 emails queued to send again."]


def test_resend_skips_rows_that_cannot_be_resent_and_says_why(
    superuser_client: Client,
    database_task_backend: None,
    django_capture_on_commit_callbacks,
) -> None:
    from django_tasks_db.models import DBTaskResult

    sent = OutboundEmailFactory(sent=True)
    sending = OutboundEmailFactory(sending=True)
    scrubbed = OutboundEmailFactory(dead_letter=True, scrubbed=True)

    with django_capture_on_commit_callbacks(execute=True):
        response = resend_selected(superuser_client, sent, sending, scrubbed)

    assert DBTaskResult.objects.count() == 0
    assert message_texts(response) == [
        "3 emails skipped: 1 already sent, 1 body removed, 1 in flight."
    ]


def test_resend_of_mixed_selection_queues_only_resendable_row(
    superuser_client: Client,
    database_task_backend: None,
    django_capture_on_commit_callbacks,
) -> None:
    from django_tasks_db.models import DBTaskResult

    dead = OutboundEmailFactory(dead_letter=True)
    sent = OutboundEmailFactory(sent=True)

    with django_capture_on_commit_callbacks(execute=True):
        response = resend_selected(superuser_client, dead, sent)

    assert [row.args_kwargs for row in DBTaskResult.objects.all()] == [
        {"args": [str(dead.pk)], "kwargs": {}}
    ]
    assert message_texts(response) == [
        "1 email queued to send again.",
        "1 email skipped: 1 already sent.",
    ]


def test_resend_post_by_non_superuser_changes_nothing(
    staff_client: Client, database_task_backend: None
) -> None:
    dead = OutboundEmailFactory(dead_letter=True)

    resend_selected(staff_client, dead)

    dead.refresh_from_db()
    assert dead.status == Status.DEAD_LETTER


def test_resend_action_not_offered_to_staff_user_without_superuser(
    mock_site_context: object,
) -> None:
    request = RequestFactory().get(changelist_url())
    request.user = UserFactory(staff=True)
    model_admin = OutboundEmailAdmin(OutboundEmail, admin.site)

    assert "resend_selected" not in model_admin.get_actions(request)


def test_resend_post_without_csrf_token_is_refused(
    superuser_client: Client, database_task_backend: None
) -> None:
    dead = OutboundEmailFactory(dead_letter=True)
    client = Client(enforce_csrf_checks=True)
    client.force_login(UserFactory(superuser=True))

    response = client.post(
        changelist_url(),
        {"action": "resend_selected", "_selected_action": [str(dead.pk)]},
    )

    dead.refresh_from_db()
    assert response.status_code == 403
    assert dead.status == Status.DEAD_LETTER
