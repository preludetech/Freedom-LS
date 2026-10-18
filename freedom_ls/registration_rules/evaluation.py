"""Reconciling a rule with the registrations it owns.

The work is split into a read that classifies what would change and a write
that applies it, so a caller can inspect the changes without making them.
Every query names its site: evaluation runs in a task with no request for the
site-aware manager to read.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import OuterRef
from django.utils import timezone

from freedom_ls.hr_attributes.models import OrganisationHRSettings
from freedom_ls.learner_management.models import Learner, LearnerCourseRegistration
from freedom_ls.learner_progress.queries import started_course_exists
from freedom_ls.registration_rules.config import config
from freedom_ls.registration_rules.kinds import RuleState
from freedom_ls.registration_rules.loader import get_rule_kind
from freedom_ls.registration_rules.models import RegistrationRule, RuleRegistration


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

    Rules are tried in name order so two runs hand the same learner to the
    same rule.
    """
    others = (
        RegistrationRule._base_manager.filter(
            site_id=state.site_id,
            organisation_id=state.organisation_id,
            course_id=state.course_id,
            is_enabled=True,
        )
        .exclude(pk=rule.pk)
        .order_by("name", "pk")
    )
    remaining = set(learner_ids)
    taken: dict[UUID, HandOver] = {}
    for other in others:
        if not remaining:
            break
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
                # save(), not bulk_create: the progress record and the
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

    # Reactivate: update(), never save(), so the detach receiver can tell the
    # engine's writes from anyone else's. No post_save means no second
    # course.registered: the learner was told the first time.
    LearnerCourseRegistration._base_manager.filter(
        site_id=rule.site_id,
        course_id=rule.course_id,
        learner_id__in=changes.reactivate,
        rule_registration__is_retracted=True,
    ).update(is_active=True)
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

    # Retract: the started check sits inside the UPDATE, so a learner who
    # opens the course between the read above and this write keeps it.
    to_retract = LearnerCourseRegistration._base_manager.filter(
        site_id=rule.site_id,
        course_id=rule.course_id,
        learner_id__in=changes.retract,
        is_active=True,
        rule_registration__rule=rule,
    ).filter(~started_course_exists(OuterRef("learner_id"), rule.course_id))
    retracted = list(to_retract.values_list("learner_id", "pk"))
    retracted_pks = [pk for _, pk in retracted]
    LearnerCourseRegistration._base_manager.filter(
        site_id=rule.site_id, pk__in=retracted_pks
    ).update(is_active=False)
    RuleRegistration._base_manager.filter(
        site_id=rule.site_id,
        registration__in=retracted_pks,
        registration__is_active=False,
    ).update(is_retracted=True)
    return EvaluationResult(
        registered=tuple(registered),
        reactivated=changes.reactivate,
        retracted=tuple(sorted(learner_id for learner_id, _ in retracted)),
    )


def evaluate_rule(rule_id: UUID, site_id: int) -> EvaluationResult:
    """Reconcile one rule against everyone it matches or owns."""
    rule = RegistrationRule._base_manager.filter(pk=rule_id, site_id=site_id).first()
    if rule is None or not rules_enabled_for(rule.organisation_id):
        return EvaluationResult()
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
                RegistrationRule._base_manager.select_for_update()
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
        last_evaluated_at=timezone.now()
    )
    return result
