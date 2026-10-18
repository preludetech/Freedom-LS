"""Rule kinds: the classes that decide which learners a rule matches."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import QuerySet

from freedom_ls.learner_management.models import Learner
from freedom_ls.registration_rules.models import DATE_BOUND_PAIRS, RegistrationRule


@dataclass(frozen=True)
class AttributeConditions:
    """What an attribute rule asks of a learner. Empty sets and None constrain nothing."""

    job_title_ids: frozenset[UUID] = frozenset()
    department_ids: frozenset[UUID] = frozenset()
    location_ids: frozenset[UUID] = frozenset()
    organisation_start_on_or_after: date | None = None
    organisation_start_before: date | None = None
    job_title_start_on_or_after: date | None = None
    job_title_start_before: date | None = None
    department_start_on_or_after: date | None = None
    department_start_before: date | None = None
    location_start_on_or_after: date | None = None
    location_start_before: date | None = None


@dataclass(frozen=True)
class RuleState:
    """A rule as a value, so preview and evaluation run one query over the same input.

    Built from a saved rule or from the admin's validated, unsaved form data.
    """

    site_id: int
    organisation_id: UUID
    course_id: UUID
    is_enabled: bool
    conditions: AttributeConditions

    @classmethod
    def from_rule(cls, rule: RegistrationRule) -> RuleState:
        # Imported here: loader imports this module for its return type.
        from freedom_ls.registration_rules.loader import get_rule_kind

        return cls(
            site_id=rule.site_id,
            organisation_id=rule.organisation_id,
            course_id=rule.course_id,
            is_enabled=rule.is_enabled,
            conditions=get_rule_kind(rule.kind).conditions_from_rule(rule),
        )


class AttributeRuleKind:
    """Matches learners on the HR attributes they hold."""

    def conditions_from_rule(self, rule: RegistrationRule) -> AttributeConditions:
        # A rule with no conditions row constrains nothing, so it matches the
        # whole organisation.
        try:
            stored = rule.attribute_conditions
        except ObjectDoesNotExist:
            return AttributeConditions()
        return AttributeConditions(
            job_title_ids=frozenset(stored.job_titles.values_list("pk", flat=True)),
            department_ids=frozenset(stored.departments.values_list("pk", flat=True)),
            location_ids=frozenset(stored.locations.values_list("pk", flat=True)),
            **{
                field: getattr(stored, field)
                for pair in DATE_BOUND_PAIRS
                for field in pair[:2]
            },
        )

    def matching_learners(self, state: RuleState) -> QuerySet[Learner]:
        # _base_manager and explicit site: a task has no request for the
        # site-aware manager to read.
        if not state.is_enabled:
            return Learner._base_manager.none()
        learners = Learner._base_manager.filter(
            site_id=state.site_id,
            organisation_id=state.organisation_id,
            is_active=True,
        )
        conditions = state.conditions
        for field, ids in (
            ("job_title", conditions.job_title_ids),
            ("department", conditions.department_ids),
            ("location", conditions.location_ids),
        ):
            if ids:
                learners = learners.filter(**{f"hr_attributes__{field}_id__in": ids})
        for on_or_after, before, stored_date in DATE_BOUND_PAIRS:
            lower = getattr(conditions, on_or_after)
            upper = getattr(conditions, before)
            # A null date never satisfies a bound: gte and lt are both false on NULL.
            if lower is not None:
                learners = learners.filter(
                    **{f"hr_attributes__{stored_date}__gte": lower}
                )
            if upper is not None:
                learners = learners.filter(
                    **{f"hr_attributes__{stored_date}__lt": upper}
                )
        return learners.order_by("pk")
