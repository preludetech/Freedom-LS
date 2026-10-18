"""Rule kinds: the classes that decide which learners a rule matches."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from django.db.models import QuerySet

from freedom_ls.learner_management.models import Learner
from freedom_ls.registration_rules.models import RegistrationRule

#: (on-or-after bound, before bound, the LearnerHRAttributes date they test).
DATE_BOUND_PAIRS: tuple[tuple[str, str, str], ...] = (
    (
        "organisation_start_on_or_after",
        "organisation_start_before",
        "organisation_start_date",
    ),
    ("job_title_start_on_or_after", "job_title_start_before", "job_title_start_date"),
    (
        "department_start_on_or_after",
        "department_start_before",
        "department_start_date",
    ),
    ("location_start_on_or_after", "location_start_before", "location_start_date"),
)


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
        return AttributeConditions()

    def matching_learners(self, state: RuleState) -> QuerySet[Learner]:
        # _base_manager and explicit site: a task has no request for the
        # site-aware manager to read.
        if not state.is_enabled:
            return Learner._base_manager.none()
        return Learner._base_manager.filter(
            site_id=state.site_id,
            organisation_id=state.organisation_id,
            is_active=True,
        ).order_by("pk")
