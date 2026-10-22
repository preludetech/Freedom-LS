"""Reconciling a rule with the registrations it owns.

The work is split into a read that classifies what would change and a write
that applies it, so a caller can inspect the changes without making them.
Every query names its site: evaluation runs in a task with no request for the
site-aware manager to read.

A registration's is_active is written with save(), under `engine_writes`, so
the progress and webhook receivers run for the engine's changes as they do for
anyone else's. The marker is how the detach receiver tells them apart.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import OuterRef, Q, QuerySet
from django.utils import timezone

from freedom_ls.hr_attributes.models import OrganisationHRSettings
from freedom_ls.learner_management.models import Learner, LearnerCourseRegistration
from freedom_ls.learner_progress.queries import started_course_exists
from freedom_ls.registration_rules.config import config
from freedom_ls.registration_rules.kinds import RuleState
from freedom_ls.registration_rules.loader import get_rule_kind
from freedom_ls.registration_rules.models import RegistrationRule, RuleRegistration

_engine_writing: ContextVar[bool] = ContextVar("engine_writing", default=False)


@contextmanager
def engine_writes() -> Iterator[None]:
    """Mark the saves inside as the engine's own."""
    token = _engine_writing.set(True)
    try:
        yield
    finally:
        _engine_writing.reset(token)


def is_engine_write() -> bool:
    return _engine_writing.get()


@dataclass(frozen=True)
class HandOver:
    learner_id: UUID
    rule_id: UUID
    rule_name: str


@dataclass(frozen=True)
class RuleChanges:
    """What one rule would change for the learners in scope, by learner pk."""

    register: tuple[UUID, ...] = ()
    reactivate: tuple[UUID, ...] = ()
    retract: tuple[UUID, ...] = ()
    hand_over: tuple[HandOver, ...] = ()
    kept_started: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class EvaluationResult:
    registered: tuple[UUID, ...] = ()
    reactivated: tuple[UUID, ...] = ()
    retracted: tuple[UUID, ...] = ()

    def merged_with(self, other: EvaluationResult) -> EvaluationResult:
        return EvaluationResult(
            registered=self.registered + other.registered,
            reactivated=self.reactivated + other.reactivated,
            retracted=self.retracted + other.retracted,
        )


def rules_enabled_for(organisation_id: UUID) -> bool:
    """The organisation's switch. No settings row means off."""
    return OrganisationHRSettings._base_manager.filter(
        organisation_id=organisation_id, registration_rules_enabled=True
    ).exists()


def classify_rule_changes(
    rule: RegistrationRule,
    state: RuleState,
    learner_ids: Sequence[UUID] | None = None,
) -> RuleChanges:
    """Compare the rule's match with the course's registrations. Reads only.

    `state` may differ from the saved rule: a caller can pass unsaved input
    as a state while ownership still comes from the saved rows.
    """
    matching = get_rule_kind(rule.kind).matching_learners(state)
    registrations = LearnerCourseRegistration._base_manager.filter(
        site_id=state.site_id, course_id=state.course_id
    )
    if learner_ids is not None:
        matching = matching.filter(pk__in=learner_ids)
        registrations = registrations.filter(learner_id__in=learner_ids)
    matching_ids = set(matching.values_list("pk", flat=True))
    rows = list(
        registrations.values_list(
            "learner_id",
            "is_active",
            "rule_registration__rule_id",
            "rule_registration__is_retracted",
        )
    )
    registered_ids = {learner_id for learner_id, *_ in rows}
    # Register the matching learners who have no registration row at all. Any
    # existing row, active or not, belongs to someone else unless a rule made it.
    register = sorted(matching_ids - registered_ids)
    # A retracted row owned by a rule whose learner matches again.
    reactivate = sorted(
        learner_id
        for learner_id, is_active, owner_id, is_retracted in rows
        if learner_id in matching_ids and is_retracted
    )
    # Owned by this rule, active, and no longer matching.
    candidates = sorted(
        learner_id
        for learner_id, is_active, owner_id, is_retracted in rows
        if owner_id == rule.pk and is_active and learner_id not in matching_ids
    )
    hand_over = _hand_overs(rule, state, candidates)
    remaining = [learner_id for learner_id in candidates if learner_id not in hand_over]
    started = set(
        Learner._base_manager.filter(site_id=state.site_id, pk__in=remaining)
        .filter(started_course_exists(OuterRef("pk"), state.course_id))
        .values_list("pk", flat=True)
    )
    retract = [learner_id for learner_id in remaining if learner_id not in started]
    return RuleChanges(
        register=tuple(register),
        reactivate=tuple(reactivate),
        retract=tuple(retract),
        hand_over=tuple(
            hand_over[learner_id]
            for learner_id in candidates
            if learner_id in hand_over
        ),
        kept_started=tuple(sorted(started)),
    )


def _hand_overs(
    rule: RegistrationRule, state: RuleState, learner_ids: Sequence[UUID]
) -> dict[UUID, HandOver]:
    """Which other enabled rule on the course takes each learner this rule lets go of.

    Rules of every organisation are tried: a learner who moved is matched only
    by their new organisation's rules, which may take the registration over.
    Rules are tried in name order so two runs hand the same learner to the
    same rule.
    """
    others = (
        RegistrationRule._base_manager.filter(
            site_id=state.site_id,
            course_id=state.course_id,
            is_enabled=True,
        )
        .exclude(pk=rule.pk)
        .order_by("name", "pk")
    )
    remaining = set(learner_ids)
    taken: dict[UUID, HandOver] = {}
    switches: dict[UUID, bool] = {}
    for other in others:
        if not remaining:
            break
        if other.organisation_id not in switches:
            switches[other.organisation_id] = rules_enabled_for(other.organisation_id)
        if not switches[other.organisation_id]:
            continue
        matched = get_rule_kind(other.kind).matching_learners(
            RuleState.from_rule(other)
        )
        for learner_id in matched.filter(pk__in=remaining).values_list("pk", flat=True):
            taken[learner_id] = HandOver(learner_id, other.pk, other.name)
            remaining.discard(learner_id)
    return taken


def apply_rule_changes(
    rule: RegistrationRule, changes: RuleChanges
) -> EvaluationResult:
    """Write the changes, in learner-pk order, with explicit site ids throughout."""
    registered: list[UUID] = []
    for learner_id in changes.register:
        try:
            # A savepoint per row: a learner registered by someone else between
            # the read and this write hits the unique constraint, and only this
            # row rolls back. Theirs stands; a rule never takes over a row.
            with transaction.atomic():
                registration = LearnerCourseRegistration(
                    site_id=rule.site_id,
                    learner_id=learner_id,
                    course_id=rule.course_id,
                    is_active=True,
                    self_registered=False,
                )
                # Not bulk_create: the progress record and the
                # course.registered announcement hang off post_save.
                registration.save()
                RuleRegistration._base_manager.create(
                    site_id=rule.site_id,
                    registration=registration,
                    rule=rule,
                    rule_name=rule.name,
                )
        except IntegrityError:
            continue
        registered.append(learner_id)

    # Reactivate. post_save announces course.registered again and notifies
    # nobody: a reactivation is news to integrators, not to the learner.
    _set_is_active(
        LearnerCourseRegistration._base_manager.filter(
            site_id=rule.site_id,
            course_id=rule.course_id,
            learner_id__in=changes.reactivate,
            rule_registration__is_retracted=True,
        ),
        True,
    )
    RuleRegistration._base_manager.filter(
        site_id=rule.site_id,
        registration__course_id=rule.course_id,
        registration__learner_id__in=changes.reactivate,
        is_retracted=True,
    ).update(rule=rule, rule_name=rule.name, is_retracted=False)

    for hand_over in changes.hand_over:
        RuleRegistration._base_manager.filter(
            site_id=rule.site_id,
            registration__course_id=rule.course_id,
            registration__learner_id=hand_over.learner_id,
            rule=rule,
        ).update(rule_id=hand_over.rule_id, rule_name=hand_over.rule_name)

    # Retract: the started check is re-run here, inside the batch's
    # transaction, so a learner who opened the course since the classifying
    # read keeps it.
    retracted = _set_is_active(
        LearnerCourseRegistration._base_manager.filter(
            site_id=rule.site_id,
            course_id=rule.course_id,
            learner_id__in=changes.retract,
            rule_registration__rule=rule,
            is_active=True,
        ).filter(~started_course_exists(OuterRef("learner_id"), rule.course_id)),
        False,
    )
    RuleRegistration._base_manager.filter(
        site_id=rule.site_id,
        registration__in=[registration.pk for registration in retracted],
    ).update(is_retracted=True)
    return EvaluationResult(
        registered=tuple(registered),
        reactivated=changes.reactivate,
        retracted=tuple(sorted(registration.learner_id for registration in retracted)),
    )


def _set_is_active(
    registrations: QuerySet[LearnerCourseRegistration], is_active: bool
) -> list[LearnerCourseRegistration]:
    """Save the flip row by row, as the engine, and return the rows written."""
    written = list(registrations.order_by("learner_id"))
    with engine_writes():
        for registration in written:
            registration.is_active = is_active
            registration.save(update_fields=["is_active"])
    return written


def evaluate_rule(rule_id: UUID, site_id: int) -> EvaluationResult:
    """Reconcile one rule against everyone it matches or owns."""
    rule = RegistrationRule._base_manager.filter(pk=rule_id, site_id=site_id).first()
    if rule is None or not rules_enabled_for(rule.organisation_id):
        return EvaluationResult()
    # The run's start, not its end: an edit made while it runs is not applied
    # by it, and must still read as unapplied afterwards.
    started_at = timezone.now()
    state = RuleState.from_rule(rule)
    in_scope = sorted(
        set(
            get_rule_kind(rule.kind)
            .matching_learners(state)
            .values_list("pk", flat=True)
        )
        | set(
            Learner._base_manager.filter(
                site_id=site_id,
                learnercourseregistration__rule_registration__rule_id=rule_id,
            ).values_list("pk", flat=True)
        )
    )
    result = EvaluationResult()
    for batch in itertools.batched(
        in_scope, config.REGISTRATION_RULE_BATCH_SIZE, strict=False
    ):
        # One transaction per batch, re-reading the rule under a row lock, so a
        # rule disabled or a switch turned off mid-run takes effect at the next
        # batch rather than after the whole organisation.
        with transaction.atomic():
            rule = (
                RegistrationRule._base_manager.select_for_update(no_key=True)
                .filter(pk=rule_id, site_id=site_id)
                .first()
            )
            if rule is None or not rules_enabled_for(rule.organisation_id):
                return result
            changes = classify_rule_changes(
                rule, RuleState.from_rule(rule), learner_ids=list(batch)
            )
            result = result.merged_with(apply_rule_changes(rule, changes))
    # update(), not save(): a finished run is not an edit of the rule.
    RegistrationRule._base_manager.filter(pk=rule_id, site_id=site_id).update(
        last_evaluated_at=started_at
    )
    return result


def evaluate_learner(learner_id: UUID, site_id: int) -> EvaluationResult:
    """Reconcile one learner against the rules that match or own them.

    Locks only the Learner row; evaluate_rule locks only the rule. Both locks
    are no-key, so the key-share lock a foreign key check takes on the other
    run's row does not wait: registering this learner under a locked rule, or
    a batch learner under this lock, goes through.
    """
    result = EvaluationResult()
    with transaction.atomic():
        learner = (
            Learner._base_manager.select_for_update(no_key=True)
            .filter(pk=learner_id, site_id=site_id)
            .first()
        )
        if learner is None:
            return result
        rules = (
            RegistrationRule._base_manager.filter(site_id=site_id)
            .filter(
                Q(organisation_id=learner.organisation_id, is_enabled=True)
                | Q(rule_registrations__registration__learner_id=learner_id)
            )
            .distinct()
            .order_by("pk")
        )
        # One switch read per organisation: a learner who moved still holds
        # the old organisation's rows, and that organisation has its own switch.
        switches: dict[UUID, bool] = {}
        for rule in rules:
            if rule.organisation_id not in switches:
                switches[rule.organisation_id] = rules_enabled_for(rule.organisation_id)
            if not switches[rule.organisation_id]:
                continue
            changes = classify_rule_changes(
                rule, RuleState.from_rule(rule), learner_ids=[learner_id]
            )
            result = result.merged_with(apply_rule_changes(rule, changes))
    return result


def evaluate_organisation(organisation_id: UUID, site_id: int) -> EvaluationResult:
    """Every rule of the organisation, disabled ones included, so their registrations catch up."""
    result = EvaluationResult()
    for rule_id in (
        RegistrationRule._base_manager.filter(
            organisation_id=organisation_id, site_id=site_id
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    ):
        result = result.merged_with(evaluate_rule(rule_id, site_id))
    return result
