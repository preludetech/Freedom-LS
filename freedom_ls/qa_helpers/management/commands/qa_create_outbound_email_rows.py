"""Seed one OutboundEmail row per delivery state for the sent-email admin QA.

Deletes any earlier ``QA Row ...`` / ``Findable subject QA`` rows first, so a
re-run leaves exactly one row per letter. Rows E (sending) and F (failed, due)
are stamped relative to now, so re-run this right before testing them.

Also ensures the superuser ``demodev@email.com`` and the staff non-superuser
``staff-qa@example.test`` can log in; each password is the email address
(DemoDev-only convention).

Usage:
    uv run python manage.py qa_create_outbound_email_rows
    uv run python manage.py qa_create_outbound_email_rows --site-name DemoDev
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.core.mail import EmailMessage
from django.db.models import Q
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.mail.factories import OutboundEmailFactory
from freedom_ls.mail.models import OutboundEmail
from freedom_ls.mail.serialisation import SerialisedMessage, serialise_message

BODY_MARKER = "QA-SECRET-BODY-TOKEN"
SUBJECT_PREFIX = "QA Row "
FINDABLE_SUBJECT = "Findable subject QA"
LONG_ERROR = (
    "smtplib.SMTPServerDisconnected: Connection unexpectedly closed while "
    "sending DATA to mail.example.test:587 after 30 seconds; the remote host "
    "dropped the session mid-transfer and did not return a status code, so the "
    "message was left undelivered and will need an operator to decide whether "
    "to resend it or leave it in the dead letter queue for good."
)
ERROR_550 = "smtplib.SMTPRecipientsRefused: (550, b'5.1.1 mailbox unavailable')"

STAFF_EMAIL = "staff-qa@example.test"
SUPERUSER_EMAIL = "demodev@email.com"


@dataclass
class RowSpec:
    letter: str
    subject: str
    traits: dict[str, bool]
    with_payload: bool
    recipients: list[str] | None = None
    overrides: dict[str, object] = field(default_factory=dict)
    created_days_ago: int | None = None


def _payload(subject: str, recipients: list[str]) -> SerialisedMessage:
    message = EmailMessage(
        subject=subject,
        body=f"QA body for '{subject}'. {BODY_MARKER}",
        from_email="noreply@example.test",
        to=recipients,
    )
    return serialise_message(message)


def _row_specs() -> list[RowSpec]:
    now = timezone.now()
    return [
        RowSpec(
            "A",
            "QA Row A dead_letter",
            {"dead_letter": True},
            True,
            overrides={
                "attempt_count": 6,
                "last_error": LONG_ERROR,
                "last_attempt_at": now - timedelta(hours=1),
            },
        ),
        RowSpec(
            "B",
            "QA Row B permanent_failure",
            {"permanent_failure": True},
            True,
            overrides={"last_error": ERROR_550},
        ),
        RowSpec(
            "C",
            "QA Row C dead_letter scrubbed",
            {"dead_letter": True, "scrubbed": True},
            False,
        ),
        RowSpec("D", "QA Row D sent", {"sent": True}, False),
        RowSpec(
            "E",
            "QA Row E sending",
            {"sending": True},
            True,
            overrides={"last_attempt_at": now - timedelta(minutes=1)},
        ),
        RowSpec(
            "F",
            "QA Row F failed",
            {"failed": True},
            True,
            overrides={
                "attempt_count": 2,
                "next_attempt_at": now - timedelta(minutes=30),
            },
        ),
        RowSpec(
            "G",
            "QA Row G sent old",
            {"sent": True},
            False,
            overrides={
                "last_attempt_at": now - timedelta(days=40),
                "sent_at": now - timedelta(days=40),
                "scrubbed_at": now - timedelta(days=40),
            },
            created_days_ago=40,
        ),
        RowSpec(
            "H",
            FINDABLE_SUBJECT,
            {"permanent_failure": True},
            True,
            recipients=["search-me@example.test"],
        ),
    ]


def _delete_previous_rows() -> None:
    previous = OutboundEmail.objects.filter(
        Q(subject__startswith=SUBJECT_PREFIX) | Q(subject=FINDABLE_SUBJECT)
    )
    for row in previous:
        click.echo(f"  removing {row.pk} [{row.status}] {row.subject!r}")
    deleted, per_model = previous.delete()
    click.echo(f"  deleted {deleted}: {per_model}")


def _create_row(spec: RowSpec) -> OutboundEmail:
    recipients = spec.recipients or [f"qa-row-{spec.letter.lower()}@example.test"]
    kwargs: dict[str, object] = {
        "subject": spec.subject,
        "recipients": recipients,
        **spec.traits,
        **spec.overrides,
    }
    if spec.with_payload:
        kwargs["payload"] = _payload(spec.subject, recipients)
    row = cast(OutboundEmail, OutboundEmailFactory(**kwargs))
    if spec.created_days_ago is not None:
        # created_at is auto_now_add, so it is only settable after the insert.
        OutboundEmail.objects.filter(pk=row.pk).update(
            created_at=timezone.now() - timedelta(days=spec.created_days_ago)
        )
    return row


def _ensure_login_user(site: Site, email: str, *, superuser: bool) -> User:
    user: User | None = User.objects.filter(email=email).first()
    if user is None:
        user = cast(User, UserFactory(email=email, password=email, site=site))
    user.is_active = True
    user.is_staff = True
    user.is_superuser = superuser
    user.set_password(email)
    user.save(update_fields=["is_active", "is_staff", "is_superuser", "password"])
    EmailAddress.objects.update_or_create(
        user=user, email=user.email, defaults={"verified": True, "primary": True}
    )
    return user


@click.command()
@click.option("--site-name", default="DemoDev", help="Site the users belong to.")
def command(site_name: str) -> None:
    site = Site.objects.get(name=site_name)
    click.secho("Removing earlier QA OutboundEmail rows", fg="yellow")
    _delete_previous_rows()

    click.secho("Created OutboundEmail rows", fg="green")
    for spec in _row_specs():
        row = _create_row(spec)
        click.echo(f"  Row {spec.letter}: {row.pk} [{row.status}] {row.subject!r}")

    for email, superuser in ((SUPERUSER_EMAIL, True), (STAFF_EMAIL, False)):
        user = _ensure_login_user(site, email, superuser=superuser)
        click.echo(
            f"  user {user.email} (pk {user.pk}, site {user.site_id}) "
            f"staff={user.is_staff} superuser={user.is_superuser} password={email}"
        )
