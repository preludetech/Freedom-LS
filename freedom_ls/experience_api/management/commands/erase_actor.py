"""``erase_actor`` management command.

Anonymises every Event row for a given user and writes a single
:class:`~freedom_ls.experience_api.models.ActorErasure` audit row.

This is the **one** mutation path that succeeds against already-persisted
Event rows. It opens a separate Django DB connection (``DATABASES['erasure']``)
whose login user is a member of ``fls_erasure_role`` — the role that
migration 0002 grants ``UPDATE`` on ``experience_api_event``. The
application role has its ``UPDATE`` / ``DELETE`` grants revoked; everyone
(including the erasure role) is forbidden from mutating or deleting
``experience_api_actorerasure``.

The blocker mechanism is configurable via the
``EXPERIENCE_API_ERASURE_BLOCKERS`` setting — a list of dotted paths to
callables ``(user_id: int) -> bool``. The portable default is empty; FLS
appends ``student_management.xapi_erasure.has_active_registrations`` via
the per-env settings files.
"""

from __future__ import annotations

import getpass
import importlib
import json
import secrets
import socket

import djclick as click

from django.conf import settings
from django.db import connections, transaction

from freedom_ls.experience_api.models import ActorErasure


def _check_blockers(user_id: int) -> None:
    # Blocker dotted paths come from Django settings (operator-controlled,
    # never user-controlled). The callable check guards against a
    # misconfigured entry pointing at a non-callable attribute.
    blockers = getattr(settings, "EXPERIENCE_API_ERASURE_BLOCKERS", []) or []
    for dotted in blockers:
        module_path, _, attr = dotted.rpartition(".")
        if not module_path or not attr:
            raise click.ClickException(
                f"Invalid EXPERIENCE_API_ERASURE_BLOCKERS entry: {dotted!r}"
            )
        # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import -- settings-controlled path (see docstring).
        module = importlib.import_module(module_path)
        func = getattr(module, attr, None)
        if not callable(func):
            raise click.ClickException(
                f"EXPERIENCE_API_ERASURE_BLOCKERS entry {dotted!r} did "
                f"not resolve to a callable."
            )
        if func(user_id):
            raise click.ClickException(
                f"Erasure refused: blocker {dotted!r} returned True for user {user_id}."
            )


def _check_erasure_connection() -> None:
    cfg = settings.DATABASES.get("erasure")
    if not cfg:
        raise click.ClickException(
            "DATABASES['erasure'] not configured. See "
            "docs/deployment-security-checklist.md."
        )
    # The connection credentials are read from the settings so tests can
    # override them via ``settings.DATABASES`` (a fall-back to the default
    # pguser is hardcoded for local dev). Production deployments must set
    # FLS_ERASURE_DB_USER / FLS_ERASURE_DB_PASSWORD explicitly —
    # settings_prod.py fails at load-time if those env vars are missing.
    if not cfg.get("USER") or not cfg.get("PASSWORD"):
        raise click.ClickException(
            "DATABASES['erasure'] USER/PASSWORD are empty. Set "
            "FLS_ERASURE_DB_USER and FLS_ERASURE_DB_PASSWORD env vars."
        )


def _perform_erasure(user_id: int, admin_user_id: int | None) -> int:
    token = secrets.token_hex(8)
    erased_email = f"erased-{token}@example.invalid"
    erased_name = f"Erased actor {token}"
    os_user = getpass.getuser()
    hostname = socket.gethostname()

    connection = connections["erasure"]
    ifi_suffix = f"|{user_id}"

    tombstone = {
        "account": {"name": f"erased-{token}"},
        "name": erased_name,
    }

    with transaction.atomic(using="erasure"):
        with connection.cursor() as cursor:
            # Single bulk UPDATE — anonymises every matching row in one
            # round-trip. cursor.rowcount gives the authoritative count
            # inside the same transaction, so the audit row can't drift.
            cursor.execute(
                "UPDATE experience_api_event "
                "SET actor_email = %s, "
                "    actor_display_name = %s, "
                "    actor_user_id = NULL, "
                "    statement = jsonb_set("
                "      statement, '{actor}', %s::jsonb, true"
                "    ) "
                "WHERE actor_user_id = %s OR actor_ifi LIKE %s",
                [
                    erased_email,
                    erased_name,
                    json.dumps(tombstone),
                    user_id,
                    f"%{ifi_suffix}",
                ],
            )
            event_count: int = cursor.rowcount

        # Write the audit row. The erasure role has no UPDATE/DELETE
        # grants on actor_erasure — only INSERT — so this row is
        # likewise append-only.
        ActorErasure.objects.using("erasure").create(
            target_user_id=user_id,
            erased_token=token,
            event_count=event_count,
            invoking_os_user=os_user,
            invoking_hostname=hostname,
            invoking_admin_user_id=admin_user_id,
        )

    return event_count


@click.command()
@click.option("--user-id", type=int, default=None)
@click.option("--confirm", is_flag=True, default=False)
@click.option("--admin-user-id", type=int, default=None)
def command(user_id: int | None, confirm: bool, admin_user_id: int | None) -> None:
    """Anonymise every event for a user and write an audit row."""
    if user_id is None:
        raise click.ClickException("--user-id is required.")
    if not confirm:
        raise click.ClickException(
            "Refusing to run without --confirm. Rerun with --confirm to "
            "perform the irreversible erasure operation."
        )

    strict = getattr(settings, "EXPERIENCE_API_STRICT_VALIDATION", False)
    if strict and admin_user_id is None:
        raise click.ClickException(
            "EXPERIENCE_API_STRICT_VALIDATION=True — --admin-user-id is "
            "required so the audit trail records who authorised the "
            "erasure."
        )
    if not strict and admin_user_id is None:
        click.echo(
            "WARNING: running without --admin-user-id; the audit row "
            "will have a null invoking_admin_user_id. "
            "Strongly recommended in production.",
            err=True,
        )

    _check_blockers(user_id)
    _check_erasure_connection()
    event_count = _perform_erasure(user_id, admin_user_id)

    click.echo(f"Erasure complete: {event_count} events anonymised for user {user_id}.")
