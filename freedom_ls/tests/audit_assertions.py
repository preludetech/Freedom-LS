"""Assertions on the audit log, shared by every app's writer tests."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from django.contrib.contenttypes.models import ContentType
from django.db.models import Model

from freedom_ls.accounts.models import User
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.audit_log.types import JSONValue
from freedom_ls.audit_log.writer import subject_key
from freedom_ls.organisations.models import Organisation


def assert_entry(
    *,
    action: str,
    actor: User | None,
    target: Model,
    target_label: str,
    organisation: Organisation | None,
    subjects: Iterable[Model] = (),
    details: Mapping[str, JSONValue] | None = None,
    reason: str = "",
) -> AuditLogEntry:
    """Assert the log holds exactly one entry and that it carries these values.

    `subjects` lists the subjects beyond the target, which is always first.
    """
    entry = AuditLogEntry.unscoped.get()
    assert entry.action == action
    assert entry.actor == actor
    assert entry.actor_label == (actor.display_name if actor else "")
    assert entry.target_content_type == ContentType.objects.get_for_model(target)
    assert entry.target_object_id == str(target.pk)
    assert entry.target_label == target_label
    assert entry.organisation == organisation
    assert entry.subjects == [subject_key(target), *(subject_key(s) for s in subjects)]
    assert entry.details == dict(details or {})
    assert entry.reason == reason
    return entry
