"""The one way an audit log entry is written."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from uuid import UUID

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db.models import Model

from freedom_ls.accounts.models import User
from freedom_ls.audit_log.actions import validate_action
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.audit_log.types import JSONValue
from freedom_ls.organisations.models import Organisation
from freedom_ls.site_aware_models.models import SiteAwareModelBase, site_of


def subject_key(obj: Model) -> str:
    return f"{obj._meta.app_label}.{obj._meta.model_name}:{obj.pk}"


def organisation_of(target: Model) -> Organisation | None:
    """The organisation an audited target belongs to: the target itself when
    it is one, none for a Site, else the target's `organisation` when it has
    one. The learner-management models that carry one cannot be named here
    without a dependency cycle, so they are recognised by that attribute."""
    if isinstance(target, Organisation):
        return target
    if isinstance(target, Site):
        return None
    organisation = getattr(target, "organisation", None)
    return organisation if isinstance(organisation, Organisation) else None


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
    row survives, so a rolled-back change leaves no entry."""
    validate_action(action)
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
        reason=reason.strip(),
        details=dict(details or {}),
        run_id=run_id,
    )
