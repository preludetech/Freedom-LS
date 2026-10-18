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
from django.utils import timezone

from freedom_ls.hr_attributes.models import OrganisationHRSettings
from freedom_ls.learner_management.models import Learner, LearnerCourseRegistration
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
    registered_ids = set(registrations.values_list("learner_id", flat=True))
    # Register the matching learners who have no registration row at all. Any
    # existing row, active or not, belongs to someone else and is never touched.
    register = sorted(matching_ids - registered_ids)
    return RuleChanges(register=tuple(register))


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
    return EvaluationResult(registered=tuple(registered))


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
