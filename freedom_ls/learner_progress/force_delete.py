"""Force delete: erase users and everything that hangs off them, with an audit entry.

The page that asks for confirmation and the delete itself both go through
`build_plan`, so what the page lists is what goes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from django.contrib.admin.sites import AdminSite
from django.contrib.admin.utils import NestedObjects
from django.db import router, transaction
from django.db.models import Model
from django.http import HttpRequest

from freedom_ls.accounts import admin as accounts_admin
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.types import JSONValue
from freedom_ls.audit_log.writer import record_entry
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.learner_management.learner_actions import record_learner_entry
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_progress.models import CourseFormAttempt, CourseProgress


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
    unlinked: dict[type[Model], int] = field(default_factory=dict)

    def counts(self) -> dict[str, int]:
        """Row count per model, keyed by plural verbose name and sorted by it."""
        counts = {
            str(model._meta.verbose_name_plural): len(rows)
            for model, rows in self.objects.items()
        }
        return dict(sorted(counts.items()))

    def unlinked_counts(self) -> dict[str, int]:
        """Rows no foreign key reaches, per plural verbose name, sorted by it."""
        return _by_name(self.unlinked)

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


def _by_name(counts: dict[type[Model], int]) -> dict[str, int]:
    named = {str(model._meta.verbose_name_plural): n for model, n in counts.items()}
    return dict(sorted(named.items()))


def unlinked_rows(users: Sequence[User]) -> dict[type[Model], int]:
    """How many rows no foreign key reaches go with these users, per model.

    Zero counts are dropped. The collectors in `USER_ERASURE_UNLINKED_RECORDS`
    find rows by something other than a foreign key, such as an email address.
    """
    counts: dict[type[Model], int] = {}
    if not users:
        return counts
    for collect_unlinked in accounts_admin.USER_ERASURE_UNLINKED_RECORDS:
        model, count = collect_unlinked(users)
        if count:
            counts[model] = counts.get(model, 0) + count
    return counts


def _collect(roots: Sequence[Model], using: str) -> NestedObjects:
    collector = NestedObjects(using=using)
    # `collect` reads its relations off the first object's model, so roots of
    # different models are collected one model at a time.
    by_model: dict[type[Model], list[Model]] = {}
    for root in roots:
        by_model.setdefault(type(root), []).append(root)
    for model_roots in by_model.values():
        collector.collect(model_roots)
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
    unlinked_for: Sequence[User] = (),
) -> ForceDeletePlan:
    """Collect every row a force delete takes, and the models that stop it.

    Two collections, because collection stops at a PROTECT edge: one from the
    course progress records, one from the targets. Whatever the second reports
    as protected is dropped when the first holds it; the rest blocks. A model
    outside `USER_ERASURE_CASCADE_MODELS` whose admin refuses delete blocks too.
    `unlinked_for` names the users whose unlinked rows are counted; rows no
    foreign key reaches are not in `objects`, and a learner force delete has none.
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
    return ForceDeletePlan(
        objects=objects,
        blocking_models=tuple(sorted(blocking)),
        unlinked=unlinked_rows(unlinked_for),
    )


def learner_progress_roots(learners: Sequence[Learner]) -> list[Model]:
    """The course progress records of these learners, and the form progress
    records those records' course form attempts link.

    Collection from a course progress record stops at the PROTECT edge into
    its learner, so these are collected as roots of their own. The form
    progress ids are read now, before any delete: the course form attempts
    that link them go with the course progress.
    """
    progress = list(CourseProgress._base_manager.filter(learner__in=learners))
    form_progress_ids = CourseFormAttempt._base_manager.filter(
        course_progress__in=progress
    ).values_list("form_progress_id", flat=True)
    return [*progress, *FormProgress._base_manager.filter(pk__in=form_progress_ids)]


def user_progress_roots(users: Sequence[Model]) -> list[Model]:
    """`learner_progress_roots` for every learner row of these users."""
    return learner_progress_roots(list(Learner._base_manager.filter(user__in=users)))


def counts_for(
    target: Model,
    progress_roots: Sequence[Model],
    *,
    request: HttpRequest,
    admin_site: AdminSite,
) -> dict[str, JSONValue]:
    """What a force delete of this one target takes, per model."""
    plan = build_plan(
        targets=[target],
        progress_roots=progress_roots,
        request=request,
        admin_site=admin_site,
    )
    return {**plan.counts()}


def unlinked_counts_for(user: User) -> dict[str, JSONValue]:
    """The rows no foreign key reaches that go with this one user, per model."""
    return {**_by_name(unlinked_rows([user]))}


def force_delete_users(
    users: Sequence[User],
    *,
    actor: User,
    reason: str,
    request: HttpRequest,
    admin_site: AdminSite,
) -> int:
    """Delete the users and their rows in one transaction.

    Each user gets one `user.deleted` entry with no organisation, and each of
    their learners one `learner.removed` entry in that learner's organisation.
    The users are re-read under a lock and the plan rebuilt inside the
    transaction, so a row added since the confirmation page was shown is
    counted, and a model that now blocks stops the delete. Everything reads
    through `_base_manager`: the request's site must not narrow a cascade.
    """
    with transaction.atomic():
        locked = list(
            User._base_manager.filter(pk__in=[u.pk for u in users]).select_for_update()
        )
        learners = list(
            Learner._base_manager.filter(user__in=locked).select_related(
                "user", "organisation"
            )
        )
        plan = build_plan(
            targets=locked,
            progress_roots=learner_progress_roots(learners),
            request=request,
            admin_site=admin_site,
            unlinked_for=locked,
        )
        if not plan.can_run:
            raise ForceDeleteBlockedError(plan.blocking_models)
        for user in locked:
            own_learners = [
                learner for learner in learners if learner.user_id == user.pk
            ]
            record_entry(
                action="user.deleted",
                actor=actor,
                target=user,
                target_label=user.display_name,
                organisation=None,
                subjects=own_learners,
                reason=reason,
                details={
                    "counts": counts_for(
                        user,
                        learner_progress_roots(own_learners),
                        request=request,
                        admin_site=admin_site,
                    ),
                    "unlinked": unlinked_counts_for(user),
                    "organisations": [
                        *sorted({learner.organisation.name for learner in own_learners})
                    ],
                },
            )
            for learner in own_learners:
                record_learner_entry(
                    learner,
                    "learner.removed",
                    actor,
                    reason=reason,
                    details={
                        "counts": counts_for(
                            learner,
                            learner_progress_roots([learner]),
                            request=request,
                            admin_site=admin_site,
                        )
                    },
                )
        # CourseProgress.learner is PROTECT, so the progress records go first.
        CourseProgress._base_manager.filter(learner__in=learners).delete()
        User._base_manager.filter(pk__in=[u.pk for u in locked]).delete()
    return len(locked)
