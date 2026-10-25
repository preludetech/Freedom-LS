"""Signal receivers that keep rule-made registrations in step with learner data."""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from django.db import models, transaction
from django.db.models import Exists, OuterRef, ProtectedError, QuerySet
from django.db.models.signals import (
    m2m_changed,
    post_delete,
    post_save,
    pre_delete,
    pre_save,
)
from django.dispatch import Signal, receiver
from django.tasks import Task
from django.utils import timezone

from freedom_ls.course_recommendations.models import RecommendedCourse
from freedom_ls.hr_attributes.models import (
    Department,
    JobTitle,
    LearnerHRAttributes,
    Location,
    OrganisationHRSettings,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import user_id_of_learner
from freedom_ls.registration_rules.evaluation import is_engine_write, switched_on
from freedom_ls.registration_rules.models import (
    AttributeRuleConditions,
    RegistrationRule,
    RuleRecommendation,
    RuleRegistration,
    rules_naming,
)
from freedom_ls.registration_rules.tasks import (
    evaluate_learner_task,
    evaluate_organisation_task,
    evaluate_rule_task,
)


@dataclass(frozen=True)
class _Enqueue:
    """An on-commit callback that compares equal to another for the same task and args."""

    task: Task[[str, int], None]
    args: tuple[str, int]

    def __call__(self) -> None:
        self.task.enqueue(*self.args)


def _enqueue_once(callback: _Enqueue) -> None:
    """Enqueue after commit, once per transaction.

    After commit, so the task never reads the rows this save is still writing.
    Once, because one admin save fires the rule, its conditions and each
    picker's add, remove and clear, and every one asks for the same run. A
    rolled-back savepoint drops its callbacks, so nothing stale blocks a later one.
    """
    pending = transaction.get_connection().run_on_commit
    if any(func == callback for _, func, _ in pending):
        return
    transaction.on_commit(callback)


def _enqueue_rule(rule_id: UUID, site_id: int) -> None:
    _enqueue_once(_Enqueue(evaluate_rule_task, (str(rule_id), site_id)))


def _rule_changed(rule_id: UUID, site_id: int) -> None:
    """A change to the rule's conditions, from the admin or anywhere else.

    Moves updated_at, so the change counts as unapplied until a run starts
    after it, then queues that run.
    """
    RegistrationRule._base_manager.filter(pk=rule_id, site_id=site_id).update(
        updated_at=timezone.now()
    )
    _enqueue_rule(rule_id, site_id)


def _enqueue_learner(learner_id: UUID, site_id: int) -> None:
    _enqueue_once(_Enqueue(evaluate_learner_task, (str(learner_id), site_id)))


def _learner_needs_evaluation(
    learner_id: UUID, organisation_id: UUID, site_id: int, *, user_id: int
) -> bool:
    """Whether any rule could register, retract or recommend to this learner.

    True when their organisation has rules and its switch on, or when a rule
    already owns one of their registrations or holds one of their
    recommendations (a learner who moved away, possibly from another
    organisation's rule).
    """
    if RegistrationRule._base_manager.filter(
        site_id=site_id,
        organisation_id=organisation_id,
        organisation__hr_settings__registration_rules_enabled=True,
    ).exists():
        return True
    if RuleRegistration._base_manager.filter(
        site_id=site_id, registration__learner_id=learner_id
    ).exists():
        return True
    return RuleRecommendation._base_manager.filter(
        site_id=site_id, recommendation__user_id=user_id
    ).exists()


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


def held_only_by(
    site_id: int, rule_ids: Collection[UUID]
) -> QuerySet[RecommendedCourse]:
    """The recommendations one of these rules holds and no rule outside them does.

    Explicit site: pre_delete runs with whatever request is ambient, or none.
    Two Exists rather than a join, so a recommendation several of the rules
    hold comes back once and the queryset can be deleted.
    """
    links = RuleRecommendation._base_manager.filter(
        site_id=site_id, recommendation=OuterRef("pk")
    )
    return RecommendedCourse._base_manager.filter(
        Exists(links.filter(rule_id__in=rule_ids)), site_id=site_id
    ).exclude(Exists(links.exclude(rule_id__in=rule_ids)))


def _rules_deleted_with(instance: RegistrationRule, origin: object) -> set[UUID]:
    """Every rule the delete that reached `instance` covers: the queryset a
    bulk delete started from, else the rule alone. Nothing cascades into a
    rule, so the origin is always one of the two."""
    if isinstance(origin, QuerySet) and origin.model is RegistrationRule:
        return set(origin.values_list("pk", flat=True))
    return {instance.pk}


@receiver(pre_delete, sender=RegistrationRule)
def delete_unheld_recommendations_before_delete(
    sender: type[RegistrationRule],
    instance: RegistrationRule,
    origin: object = None,
    **kwargs: object,
) -> None:
    """Delete the recommendations no rule outside this delete holds, before the
    CASCADE leaves them with no RuleRecommendation and looking staff-made.

    Every rule of a bulk delete still holds its rows when the first pre_delete
    runs, so "held by this rule alone" would keep a recommendation two of the
    deleted rules share. The first rule's pre_delete removes it instead, and the
    other rule's finds nothing left to remove.
    """
    held_only_by(instance.site_id, _rules_deleted_with(instance, origin)).filter(
        rule_recommendations__rule=instance
    ).delete()


@receiver(pre_save, sender=LearnerCourseRegistration)
def detach_rule_on_foreign_is_active_change(
    sender: type[LearnerCourseRegistration],
    instance: LearnerCourseRegistration,
    raw: bool = False,
    update_fields: frozenset[str] | None = None,
    **kwargs: object,
) -> None:
    """A deactivation or reactivation the engine did not make ends the rule's ownership.

    The engine marks its own saves, so any other save that flips the loaded
    value is someone else's decision: staff in the admin, or the learner
    registering again. A save that does not write is_active decides nothing,
    whatever a stale instance holds.
    """
    if raw or instance._state.adding or is_engine_write():
        return
    if update_fields is not None and "is_active" not in update_fields:
        return
    stored = instance.loaded_is_active
    if stored is None:
        # Loaded with is_active deferred.
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
    _rule_changed(instance.rule_id, instance.site_id)


def _evaluate_rule_on_m2m_change(
    sender: type[models.Model],
    instance: models.Model,
    action: str,
    reverse: bool,
    pk_set: set[UUID] | None,
    **kwargs: object,
) -> None:
    """Queue an evaluation when a picker's selection changes, from either side."""
    if not reverse:
        if action in {"post_add", "post_remove", "post_clear"}:
            conditions = cast(AttributeRuleConditions, instance)
            _rule_changed(conditions.rule_id, conditions.site_id)
        return
    # Reverse side: an entry's conditions set changed. A clear names no pks
    # afterwards, so the rules it will widen are read before it happens.
    changed: models.QuerySet[AttributeRuleConditions]
    if action == "pre_clear":
        entry = cast(JobTitle | Department | Location, instance)
        changed = entry.registration_rule_conditions.all()
    elif action in {"post_add", "post_remove"} and pk_set is not None:
        changed = AttributeRuleConditions._base_manager.filter(pk__in=pk_set)
    else:
        return
    for rule_id, site_id in changed.values_list("rule_id", "site_id"):
        _rule_changed(rule_id, site_id)


for _field in (
    AttributeRuleConditions.job_titles,
    AttributeRuleConditions.departments,
    AttributeRuleConditions.locations,
):
    m2m_changed.connect(_evaluate_rule_on_m2m_change, sender=_field.through)


@receiver(pre_delete, sender=JobTitle)
@receiver(pre_delete, sender=Department)
@receiver(pre_delete, sender=Location)
def protect_entry_a_rule_names(
    sender: type[JobTitle | Department | Location],
    instance: JobTitle | Department | Location,
    **kwargs: object,
) -> None:
    """Refuse to delete an entry a rule names.

    The delete would cascade to the picker's through row with no m2m_changed,
    and an emptied picker constrains nothing, so the rule would silently widen
    to the whole organisation. Deactivating the entry is the way to retire it.
    """
    rules = list(rules_naming(instance))
    if rules:
        raise ProtectedError(
            f"{instance} is named by registration rules and cannot be deleted.",
            set(rules),
        )


@receiver(post_save, sender=Learner)
def evaluate_learner_on_save(
    sender: type[Learner],
    instance: Learner,
    raw: bool = False,
    update_fields: frozenset[str] | None = None,
    **kwargs: object,
) -> None:
    """Queue an evaluation of a learner save that a rule could act on.

    Creation, an organisation change and an is_active change are all saves,
    and evaluation reconciles state, so a run that finds nothing to do is
    harmless. An organisation that does not use rules gets no runs at all,
    and a save that writes neither field costs no query.
    """
    if raw:
        return
    if update_fields is not None and update_fields.isdisjoint(
        {"organisation", "is_active"}
    ):
        return
    if _learner_needs_evaluation(
        instance.pk,
        instance.organisation_id,
        instance.site_id,
        user_id=instance.user_id,
    ):
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

    A learner delete cascades here; with the learner gone there is nothing to
    evaluate, and a task that still runs finds no learner and returns.
    """
    if raw:
        return
    learner = (
        Learner._base_manager.filter(pk=instance.learner_id)
        .values_list("organisation_id", "user_id")
        .first()
    )
    if learner is not None and _learner_needs_evaluation(
        instance.learner_id, learner[0], instance.site_id, user_id=learner[1]
    ):
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
    _enqueue_once(
        _Enqueue(
            evaluate_organisation_task,
            (str(instance.organisation_id), instance.site_id),
        )
    )


def _recommend_rules_on(
    site_id: int, course_ids: Iterable[UUID]
) -> list[RegistrationRule]:
    """Enabled recommend rules on these courses whose organisation's switch is on."""
    return list(
        switched_on(
            RegistrationRule._base_manager.filter(
                site_id=site_id,
                course_id__in=course_ids,
                is_enabled=True,
                outcome=RegistrationRule.Outcome.RECOMMEND,
            ).order_by("pk")
        )
    )


def _re_recommend_user(site_id: int, user_id: int, course_ids: Iterable[UUID]) -> None:
    """One evaluate_learner per active Learner of the user in a rule's organisation."""
    rules = _recommend_rules_on(site_id, course_ids)
    for learner_id in Learner._base_manager.filter(
        site_id=site_id,
        user_id=user_id,
        is_active=True,
        organisation_id__in={rule.organisation_id for rule in rules},
    ).values_list("pk", flat=True):
        _enqueue_learner(learner_id, site_id)


def _re_recommend_cohort(site_id: int, course_ids: Iterable[UUID]) -> None:
    """A cohort-wide change: one run per rule, not one task per member."""
    for rule in _recommend_rules_on(site_id, course_ids):
        _enqueue_rule(rule.pk, site_id)


def _courses_of_cohort(cohort_id: UUID) -> list[UUID]:
    return list(
        CohortCourseRegistration._base_manager.filter(cohort_id=cohort_id)
        .values_list("course_id", flat=True)
        .distinct()
    )


@receiver(post_save, sender=LearnerCourseRegistration)
@receiver(pre_delete, sender=LearnerCourseRegistration)
def re_recommend_on_registration_withdrawn(
    sender: type[LearnerCourseRegistration],
    instance: LearnerCourseRegistration,
    signal: Signal,
    raw: bool = False,
    update_fields: frozenset[str] | None = None,
    **kwargs: object,
) -> None:
    """A registration that no longer grants its course puts the recommendation back."""
    if raw or (signal is post_save and not instance.flipped_off(update_fields)):
        return
    _re_recommend_user(
        instance.site_id, user_id_of_learner(instance.learner_id), [instance.course_id]
    )


@receiver(pre_delete, sender=CohortMembership)
def re_recommend_on_membership_deleted(
    sender: type[CohortMembership],
    instance: CohortMembership,
    **kwargs: object,
) -> None:
    """A member who leaves a cohort loses the courses it held for them."""
    _re_recommend_user(
        instance.site_id,
        user_id_of_learner(instance.learner_id),
        _courses_of_cohort(instance.cohort_id),
    )


@receiver(post_save, sender=Learner)
@receiver(pre_delete, sender=Learner)
def re_recommend_on_learner_withdrawn(
    sender: type[Learner],
    instance: Learner,
    signal: Signal,
    raw: bool = False,
    update_fields: frozenset[str] | None = None,
    **kwargs: object,
) -> None:
    """A Learner that goes away takes its registrations with it.

    The courses are read before a delete cascades. A deleted Learner also
    leaves a user with possibly no Learner to evaluate, so every rule that
    holds one of the user's recommendations runs itself.
    """
    deleting = signal is pre_delete
    if raw or not (deleting or instance.flipped_off(update_fields)):
        return
    course_ids = set(
        LearnerCourseRegistration._base_manager.filter(
            learner_id=instance.pk, is_active=True
        ).values_list("course_id", flat=True)
    ) | set(
        CohortCourseRegistration._base_manager.filter(
            cohort__cohortmembership__learner_id=instance.pk, is_active=True
        ).values_list("course_id", flat=True)
    )
    _re_recommend_user(instance.site_id, instance.user_id, course_ids)
    if deleting:
        for rule_id in RegistrationRule._base_manager.filter(
            site_id=instance.site_id,
            rule_recommendations__recommendation__user_id=instance.user_id,
        ).values_list("pk", flat=True):
            _enqueue_rule(rule_id, instance.site_id)


@receiver(post_save, sender=CohortCourseRegistration)
@receiver(pre_delete, sender=CohortCourseRegistration)
def re_recommend_on_cohort_registration_withdrawn(
    sender: type[CohortCourseRegistration],
    instance: CohortCourseRegistration,
    signal: Signal,
    raw: bool = False,
    update_fields: frozenset[str] | None = None,
    **kwargs: object,
) -> None:
    """A cohort that no longer holds a course puts it back in front of its members."""
    if raw or (signal is post_save and not instance.flipped_off(update_fields)):
        return
    _re_recommend_cohort(instance.site_id, [instance.course_id])


@receiver(post_save, sender=Cohort)
def re_recommend_on_cohort_deactivated(
    sender: type[Cohort],
    instance: Cohort,
    raw: bool = False,
    update_fields: frozenset[str] | None = None,
    **kwargs: object,
) -> None:
    """Deactivating a cohort withdraws every course it holds from its members."""
    if raw or not instance.flipped_off(update_fields):
        return
    _re_recommend_cohort(instance.site_id, _courses_of_cohort(instance.pk))
