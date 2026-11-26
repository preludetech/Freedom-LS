"""Force delete: erase users and everything that hangs off them, with an audit entry.

The page that asks for confirmation and the delete itself both go through
`build_plan`, so what the page lists is what goes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from django.contrib.admin.sites import AdminSite
from django.contrib.admin.utils import NestedObjects
from django.db import router, transaction
from django.db.models import Model
from django.http import HttpRequest

from freedom_ls.accounts import admin as accounts_admin
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.types import JSONValue
from freedom_ls.audit_log.writer import record_entry
from freedom_ls.learner_progress.models import CourseProgress


@dataclass(frozen=True)
class ForceDeleteRows:
    """One model's rows in a plan, named for the page that lists them."""

    name: str
    count: int
    labels: tuple[str, ...]


@dataclass(frozen=True)
class ForceDeletePlan:
    objects: dict[type[Model], set[Model]]
    blocking_models: tuple[str, ...]

    def counts(self) -> dict[str, int]:
        """Row count per model, keyed by plural verbose name and sorted by it."""
        counts = {
            str(model._meta.verbose_name_plural): len(rows)
            for model, rows in self.objects.items()
        }
        return dict(sorted(counts.items()))

    def listing(self) -> list[ForceDeleteRows]:
        """Every model's rows, sorted by model name, for the page to list."""
        rows_by_name = {
            str(model._meta.verbose_name_plural): rows
            for model, rows in self.objects.items()
        }
        return [
            ForceDeleteRows(
                name=name,
                count=len(rows),
                labels=tuple(sorted(str(row) for row in rows)),
            )
            for name, rows in sorted(rows_by_name.items())
        ]

    @property
    def can_run(self) -> bool:
        return not self.blocking_models


class ForceDeleteBlockedError(Exception):
    def __init__(self, blocking_models: tuple[str, ...]) -> None:
        super().__init__(", ".join(blocking_models))
        self.blocking_models = blocking_models


def _collect(roots: Sequence[Model], using: str) -> NestedObjects:
    collector = NestedObjects(using=using)
    collector.collect(roots)
    return collector


def _admin_refuses_delete(
    model: type[Model], rows: set[Model], request: HttpRequest, admin_site: AdminSite
) -> bool:
    if not admin_site.is_registered(model):
        return False
    model_admin = admin_site._registry[model]
    return any(not model_admin.has_delete_permission(request, row) for row in rows)


def build_plan(
    *,
    targets: Sequence[Model],
    progress_roots: Sequence[Model],
    request: HttpRequest,
    admin_site: AdminSite,
) -> ForceDeletePlan:
    """Collect every row a force delete takes, and the models that stop it.

    Two collections, because collection stops at a PROTECT edge: one from the
    course progress records, one from the targets. Whatever the second reports
    as protected is dropped when the first holds it; the rest blocks. A model
    outside `USER_ERASURE_CASCADE_MODELS` whose admin refuses delete blocks too.
    """
    # The view returns 404 before this for an empty selection.
    using = router.db_for_write(type(targets[0]))
    progress = _collect(progress_roots, using)
    target = _collect(targets, using)

    objects: dict[type[Model], set[Model]] = {}
    for collector in (progress, target):
        for rows in collector.model_objs.values():
            for row in rows:
                objects.setdefault(row._meta.model, set()).add(row)

    held = {row for rows in progress.model_objs.values() for row in rows}
    leftover = [row for row in target.protected if row not in held]
    leftover.extend(progress.protected)

    blocking = {str(type(row)._meta.verbose_name) for row in leftover}
    target_model = type(targets[0])
    for model, rows in objects.items():
        if model is target_model or model in accounts_admin.USER_ERASURE_CASCADE_MODELS:
            continue
        if _admin_refuses_delete(model, rows, request, admin_site):
            blocking.add(str(model._meta.verbose_name))
    return ForceDeletePlan(objects=objects, blocking_models=tuple(sorted(blocking)))


def force_delete_users(
    users: Sequence[User],
    *,
    actor: User,
    reason: str,
    request: HttpRequest,
    admin_site: AdminSite,
) -> int:
    """Delete the users and their rows in one transaction, one entry per user.

    The users are re-read under a lock and the plan rebuilt inside the
    transaction, so a row added since the confirmation page was shown is
    counted, and a model that now blocks stops the delete. Everything reads
    through `_base_manager`: the request's site must not narrow a cascade.
    """
    with transaction.atomic():
        locked = list(
            User._base_manager.filter(pk__in=[u.pk for u in users]).select_for_update()
        )
        progress = CourseProgress._base_manager.filter(learner__user__in=locked)
        plan = build_plan(
            targets=locked,
            progress_roots=list(progress),
            request=request,
            admin_site=admin_site,
        )
        if not plan.can_run:
            raise ForceDeleteBlockedError(plan.blocking_models)
        for user in locked:
            own_progress = list(CourseProgress._base_manager.filter(learner__user=user))
            counts: dict[str, JSONValue] = {
                **build_plan(
                    targets=[user],
                    progress_roots=own_progress,
                    request=request,
                    admin_site=admin_site,
                ).counts()
            }
            record_entry(
                action="user.deleted",
                actor=actor,
                target=user,
                target_label=user.display_name,
                organisation=None,
                reason=reason,
                details={"counts": counts},
            )
        # CourseProgress.learner is PROTECT, so the progress records go first.
        progress.delete()
        User._base_manager.filter(pk__in=[u.pk for u in locked]).delete()
    return len(locked)
