"""Signal receivers that keep rule-made registrations in step with learner data."""

from __future__ import annotations

from functools import partial
from uuid import UUID

from django.db import transaction
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from freedom_ls.registration_rules.models import RegistrationRule, RuleRegistration
from freedom_ls.registration_rules.tasks import evaluate_rule_task


def _enqueue_rule(rule_id: UUID, site_id: int) -> None:
    # After commit, so the task never reads the rows this save is still writing.
    transaction.on_commit(partial(evaluate_rule_task.enqueue, str(rule_id), site_id))


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
