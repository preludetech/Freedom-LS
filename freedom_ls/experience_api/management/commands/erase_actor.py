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

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction

from freedom_ls.experience_api.models import ActorErasure, Event


class Command(BaseCommand):
    help = "Anonymise every event for a user and write an audit row."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--user-id", type=int, required=True)
        parser.add_argument("--confirm", action="store_true")
        parser.add_argument("--admin-user-id", type=int, default=None)

    def handle(self, *args, **options) -> None:
        user_id: int = options["user_id"]
        confirm: bool = options["confirm"]
        admin_user_id: int | None = options["admin_user_id"]

        if not confirm:
            raise CommandError(
                "Refusing to run without --confirm. Rerun with --confirm to "
                "perform the irreversible erasure operation."
            )

        strict = getattr(settings, "EXPERIENCE_API_STRICT_VALIDATION", False)
        if strict and admin_user_id is None:
            raise CommandError(
                "EXPERIENCE_API_STRICT_VALIDATION=True — --admin-user-id is "
                "required so the audit trail records who authorised the "
                "erasure."
            )
        if not strict and admin_user_id is None:
            self.stderr.write(
                "WARNING: running without --admin-user-id; the audit row "
                "will have a null invoking_admin_user_id. "
                "Strongly recommended in production.\n"
            )

        self._check_blockers(user_id)
        self._check_erasure_connection()

        self._perform_erasure(user_id, admin_user_id)

    # ------------------------------------------------------------------
    # Blockers

    def _check_blockers(self, user_id: int) -> None:
        # Blocker dotted paths come from Django settings (operator-controlled,
        # never user-controlled). The callable check guards against a
        # misconfigured entry pointing at a non-callable attribute.
        blockers = getattr(settings, "EXPERIENCE_API_ERASURE_BLOCKERS", []) or []
        for dotted in blockers:
            module_path, _, attr = dotted.rpartition(".")
            if not module_path or not attr:
                raise CommandError(
                    f"Invalid EXPERIENCE_API_ERASURE_BLOCKERS entry: {dotted!r}"
                )
            # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import -- settings-controlled path (see docstring).
            module = importlib.import_module(module_path)
            func = getattr(module, attr, None)
            if not callable(func):
                raise CommandError(
                    f"EXPERIENCE_API_ERASURE_BLOCKERS entry {dotted!r} did "
                    f"not resolve to a callable."
                )
            if func(user_id):
                raise CommandError(
                    f"Erasure refused: blocker {dotted!r} returned True for "
                    f"user {user_id}."
                )

    # ------------------------------------------------------------------
    # Erasure DB connection

    def _check_erasure_connection(self) -> None:
        cfg = settings.DATABASES.get("erasure")
        if not cfg:
            raise CommandError(
                "DATABASES['erasure'] not configured. See "
                "docs/deployment-security-checklist.md."
            )
        # The connection credentials are read from the settings so tests can
        # override them via ``settings.DATABASES`` (a fall-back to the default
        # pguser is hardcoded for local dev). Production deployments must set
        # FLS_ERASURE_DB_USER / FLS_ERASURE_DB_PASSWORD explicitly —
        # settings_prod.py fails at load-time if those env vars are missing.
        if not cfg.get("USER") or not cfg.get("PASSWORD"):
            raise CommandError(
                "DATABASES['erasure'] USER/PASSWORD are empty. Set "
                "FLS_ERASURE_DB_USER and FLS_ERASURE_DB_PASSWORD env vars."
            )

    # ------------------------------------------------------------------
    # Perform the erasure.

    def _perform_erasure(self, user_id: int, admin_user_id: int | None) -> None:
        token = secrets.token_hex(8)
        erased_email = f"erased-{token}@example.invalid"
        erased_name = f"Erased actor {token}"
        os_user = getpass.getuser()
        hostname = socket.gethostname()

        connection = connections["erasure"]
        ifi_suffix = f"|{user_id}"

        # Count first (read is allowed on the default connection too).
        event_count = Event._base_manager.filter(actor_user_id=user_id).count()
        event_count += (
            Event._base_manager.filter(actor_ifi__endswith=ifi_suffix)
            .exclude(actor_user_id=user_id)
            .count()
        )

        with transaction.atomic(using="erasure"):
            with connection.cursor() as cursor:
                # Find the IDs to update. The query runs via the erasure
                # connection for consistency within the transaction.
                cursor.execute(
                    "SELECT id, statement FROM experience_api_event "
                    "WHERE actor_user_id = %s OR actor_ifi LIKE %s",
                    [user_id, f"%{ifi_suffix}"],
                )
                rows = cursor.fetchall()

                # Tombstone the JSONB statement.actor block.
                tombstone = {
                    "account": {"name": f"erased-{token}"},
                    "name": erased_name,
                }
                for row_id, _statement_json in rows:
                    cursor.execute(
                        "UPDATE experience_api_event "
                        "SET actor_email = %s, "
                        "    actor_display_name = %s, "
                        "    actor_user_id = NULL, "
                        "    statement = jsonb_set("
                        "      statement, '{actor}', %s::jsonb, true"
                        "    ) "
                        "WHERE id = %s",
                        [
                            erased_email,
                            erased_name,
                            json.dumps(tombstone),
                            row_id,
                        ],
                    )

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

        self.stdout.write(
            f"Erasure complete: {event_count} events anonymised for user "
            f"{user_id}. Token: {token}.\n"
        )
