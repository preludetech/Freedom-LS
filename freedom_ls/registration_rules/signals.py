"""Signal receivers that keep rule-made registrations in step with learner data."""

from __future__ import annotations

from functools import partial
from typing import cast
from uuid import UUID

from django.db import models, transaction
from django.db.models.signals import (
    m2m_changed,
    post_delete,
    post_save,
    pre_delete,
    pre_save,
)
from django.dispatch import receiver

from freedom_ls.hr_attributes.models import (
    LearnerHRAttributes,
    OrganisationHRSettings,
)
from freedom_ls.learner_management.models import Learner, LearnerCourseRegistration
from freedom_ls.registration_rules.models import (
    AttributeRuleConditions,
    RegistrationRule,
    RuleRegistration,
)
from freedom_ls.registration_rules.tasks import (
    evaluate_learner_task,
    evaluate_organisation_task,
    evaluate_rule_task,
)


def _enqueue_rule(rule_id: UUID, site_id: int) -> None:
    # After commit, so the task never reads the rows this save is still writing.
    transaction.on_commit(partial(evaluate_rule_task.enqueue, str(rule_id), site_id))


def _enqueue_learner(learner_id: UUID, site_id: int) -> None:
    transaction.on_commit(
        partial(evaluate_learner_task.enqueue, str(learner_id), site_id)
    )


@receiver(post_save, sender=RegistrationRule)
def evaluate_rule_on_save(
    sender: type[RegistrationRule],
    instance: RegistrationRule,
    raw: bool = False,
    **kwargs: object,
) -> None:
    """Queue an evaluation of every rule save, so a change is applied."""
    if raw:
        # loaddata writes exactly the rows in the fixture and runs nothing.
        return
    _enqueue_rule(instance.pk, instance.site_id)


@receiver(pre_delete, sender=RegistrationRule)
def snapshot_rule_name_before_delete(
    sender: type[RegistrationRule], instance: RegistrationRule, **kwargs: object
) -> None:
    """Keep the rule's name on its registrations after the rule is gone."""
    # SET_NULL is about to clear rule; the name is what the registration
    # admin still shows afterwards.
    RuleRegistration._base_manager.filter(
        rule=instance, site_id=instance.site_id
    ).update(rule_name=instance.name)


@receiver(pre_save, sender=LearnerCourseRegistration)
def detach_rule_on_foreign_is_active_change(
    sender: type[LearnerCourseRegistration],
    instance: LearnerCourseRegistration,
    raw: bool = False,
    **kwargs: object,
) -> None:
    """A deactivation or reactivation the engine did not make ends the rule's ownership.

    The engine only ever changes is_active with QuerySet.update(), which never
    reaches here, so any save that flips the stored value is someone else's
    decision: staff in the admin, or the learner registering again.
    """
    if raw or instance._state.adding:
        return
    stored = (
        LearnerCourseRegistration._base_manager.filter(pk=instance.pk)
        .values_list("is_active", flat=True)
        .first()
    )
    if stored is None or stored == instance.is_active:
        return
    RuleRegistration._base_manager.filter(registration_id=instance.pk).delete()


@receiver(post_save, sender=AttributeRuleConditions)
def evaluate_rule_on_conditions_save(
    sender: type[AttributeRuleConditions],
    instance: AttributeRuleConditions,
    raw: bool = False,
    **kwargs: object,
) -> None:
    """Queue an evaluation when a rule's conditions are saved."""
    if raw:
        return
    _enqueue_rule(instance.rule_id, instance.site_id)


def _evaluate_rule_on_m2m_change(
    sender: type[models.Model],
    instance: models.Model,
    action: str,
    reverse: bool,
    pk_set: set[UUID] | None,
    **kwargs: object,
) -> None:
    """Queue an evaluation when a picker's selection changes, from either side."""
    if action not in {"post_add", "post_remove", "post_clear"}:
        return
    if not reverse:
        conditions = cast(AttributeRuleConditions, instance)
        _enqueue_rule(conditions.rule_id, conditions.site_id)
        return
    # Reverse side: an entry's conditions set changed and pk_set holds
    # conditions pks. post_clear gives no pk_set, so there is nothing to
    # enqueue for; no admin or import takes that path.
    if pk_set is None:
        return
    for rule_id, site_id in AttributeRuleConditions._base_manager.filter(
        pk__in=pk_set
    ).values_list("rule_id", "site_id"):
        _enqueue_rule(rule_id, site_id)


for _field in (
    AttributeRuleConditions.job_titles,
    AttributeRuleConditions.departments,
    AttributeRuleConditions.locations,
):
    m2m_changed.connect(_evaluate_rule_on_m2m_change, sender=_field.through)


@receiver(post_save, sender=Learner)
def evaluate_learner_on_save(
    sender: type[Learner], instance: Learner, raw: bool = False, **kwargs: object
) -> None:
    """Queue an evaluation of every learner save.

    Creation, an organisation change and an is_active change are all saves,
    and evaluation reconciles state, so a run that finds nothing to do is harmless.
    """
    if raw:
        return
    _enqueue_learner(instance.pk, instance.site_id)


@receiver(post_save, sender=LearnerHRAttributes)
@receiver(post_delete, sender=LearnerHRAttributes)
def evaluate_learner_on_attributes_change(
    sender: type[LearnerHRAttributes],
    instance: LearnerHRAttributes,
    raw: bool = False,
    **kwargs: object,
) -> None:
    """Queue an evaluation of the learner whose attributes were saved or deleted.

    A learner delete cascades here; the task then finds no learner and returns.
    """
    if raw:
        return
    _enqueue_learner(instance.learner_id, instance.site_id)


@receiver(post_save, sender=OrganisationHRSettings)
def evaluate_organisation_on_switch_save(
    sender: type[OrganisationHRSettings],
    instance: OrganisationHRSettings,
    raw: bool = False,
    **kwargs: object,
) -> None:
    """Queue an evaluation of the whole organisation when its switch is on.

    A switch left off changes nothing, and turning it off needs no run: the
    engine already does nothing for an organisation whose switch is off.
    """
    if raw or not instance.registration_rules_enabled:
        return
    transaction.on_commit(
        partial(
            evaluate_organisation_task.enqueue,
            str(instance.organisation_id),
            instance.site_id,
        )
    )
