"""The one way an audit log entry is written."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from uuid import UUID

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db.models import Model

from freedom_ls.accounts.models import User
from freedom_ls.audit_log.actions import SUMMARY_ACTIONS, validate_action
from freedom_ls.audit_log.models import REASON_LENGTH, AuditLogEntry
from freedom_ls.audit_log.types import JSONValue
from freedom_ls.organisations.models import Organisation
from freedom_ls.site_aware_models.models import SiteAwareModelBase, site_of

RUN_ROWS_KEPT = 50
RUN_LABEL_LENGTH = 255


def subject_key(obj: Model) -> str:
    return f"{obj._meta.app_label}.{obj._meta.model_name}:{obj.pk}"


def _site_for(target: Model) -> Site:
    if not isinstance(target, Site | SiteAwareModelBase):
        raise TypeError(f"{type(target).__name__} has no site; pass `site` explicitly.")
    return site_of(target)


def record_entry(
    *,
    action: str,
    actor: User | None,
    target: Model,
    target_label: str,
    organisation: Organisation | None,
    subjects: Iterable[Model] = (),
    reason: str = "",
    details: Mapping[str, JSONValue] | None = None,
    run_id: UUID | None = None,
    site: Site | None = None,
) -> AuditLogEntry:
    """Write one entry. Opens no transaction: the caller's decides whether the
    row survives, so a rolled-back change leaves no entry. Raises ValueError
    for an unknown action or a reason longer than REASON_LENGTH, so a caller
    that skipped ReasonForm fails before the insert rather than in it."""
    validate_action(action)
    reason = reason.strip()
    if len(reason) > REASON_LENGTH:
        raise ValueError(f"reason is longer than {REASON_LENGTH} characters.")
    return AuditLogEntry.unscoped.create(
        # Explicit, never from the request: this also runs in commands and
        # background tasks, and a site role's entry belongs to the role's site
        # rather than the actor's.
        site=site or _site_for(target),
        organisation=organisation,
        actor=actor,
        actor_label=actor.display_name if actor else "",
        action=action,
        target_content_type=ContentType.objects.get_for_model(target),
        target_object_id=str(target.pk),
        target_label=target_label,
        subjects=[subject_key(target), *(subject_key(s) for s in subjects)],
        reason=reason,
        details=dict(details or {}),
        run_id=run_id,
    )


def record_run_summary(
    *,
    action: str,
    run_id: UUID,
    organisation: Organisation,
    actor: User | None,
    counts: Mapping[str, int],
    reason: str = "",
    rows: Sequence[tuple[str, str]] = (),
    bulk_action: str | None = None,
) -> AuditLogEntry:
    """The one summary entry of a bulk run, sharing `run_id` with the run's
    per-object entries. `counts` holds changed, skipped and failed; `rows` are
    the skipped or failed rows as (label, outcome), cut to RUN_ROWS_KEPT with
    `truncated` saying so and each label cut to RUN_LABEL_LENGTH. Nothing else
    reaches `details`, so a caller cannot store raw import cells in the log."""
    if action not in SUMMARY_ACTIONS:
        valid = ", ".join(sorted(SUMMARY_ACTIONS))
        raise ValueError(f"{action!r} is not a summary action. Valid codes: {valid}")
    kept: list[JSONValue] = [
        {"label": label[:RUN_LABEL_LENGTH], "outcome": outcome}
        for label, outcome in rows[:RUN_ROWS_KEPT]
    ]
    details: dict[str, JSONValue] = {
        "counts": {
            "changed": counts["changed"],
            "skipped": counts["skipped"],
            "failed": counts["failed"],
        },
        "rows": kept,
        "truncated": len(rows) > RUN_ROWS_KEPT,
    }
    if bulk_action is not None:
        details["bulk_action"] = bulk_action
    return record_entry(
        action=action,
        actor=actor,
        target=organisation,
        target_label=organisation.name,
        organisation=organisation,
        reason=reason,
        details=details,
        run_id=run_id,
    )
