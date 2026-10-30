"""The deadline policy: which consequences apply to a learner's course record.

Each layer (registration, cohort, organisation, course, site) may set a value or
leave it to inherit; the first layer that sets one wins, and the settings
defaults decide whatever no layer did.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import cast
from uuid import UUID

from freedom_ls.deadlines.config import config
from freedom_ls.deadlines.models import (
    AfterAccessEnded,
    CohortCourseRegistrationDeadlineConfig,
    CohortDeadlineConfig,
    CourseDeadlineConfig,
    DeadlineConfigFields,
    DeadlineSwitch,
    LearnerCourseRegistrationDeadlineConfig,
    OrganisationDeadlineConfig,
    SiteDeadlineConfig,
)
from freedom_ls.learner_management.models import CohortCourseRegistration, Learner
from freedom_ls.learner_progress.models import CourseProgress

SETTINGS_LAYER = "settings"


@dataclass(frozen=True)
class ResolvedDeadlinePolicy:
    mark_overdue: bool
    close_items: bool
    end_course_access: bool
    notify_educators: bool
    grace_window: timedelta
    after_access_ended: str  # an AfterAccessEnded value, never "inherit"
    sources: Mapping[str, str]  # setting name -> name of the layer that decided it


class DeadlinePolicy:
    def resolve(self, course_progress: CourseProgress) -> ResolvedDeadlinePolicy:
        return self.resolve_for([course_progress])[course_progress.pk]

    def resolve_for(
        self, records: Sequence[CourseProgress]
    ) -> dict[UUID, ResolvedDeadlinePolicy]:
        raise NotImplementedError


def _rows_by_owner[RowT: DeadlineConfigFields](
    model: type[RowT],
    owner_field: str,
    owner_ids: Collection[UUID | int],
    site_id: int,
) -> dict[UUID | int, RowT]:
    """One layer table, read for the given owners on one site.

    Uses _base_manager because the resolver also runs outside a request, where the
    thread-local site is unset; the explicit site_id keeps another site's rows out.
    """
    return {
        getattr(row, f"{owner_field}_id"): row
        for row in model._base_manager.filter(
            site_id=site_id, **{f"{owner_field}__in": owner_ids}
        )
    }


Layers = list[tuple[str, DeadlineConfigFields | None]]


class LayeredDeadlinePolicy(DeadlinePolicy):
    # Most specific first; the only place the order is written.
    LAYER_ORDER = (
        "registration",
        "cohort",
        "organisation",
        "course",
        "site",
        "settings",
    )

    def resolve_for(
        self, records: Sequence[CourseProgress]
    ) -> dict[UUID, ResolvedDeadlinePolicy]:
        if not records:
            return {}
        site_id = records[0].site_id
        cohort_registration_ids = {
            r.cohort_registration_id
            for r in records
            if r.cohort_registration_id is not None
        }
        learner_registration_ids = {
            r.learner_registration_id
            for r in records
            if r.learner_registration_id is not None
        }
        # The record carries the course, learner, site and registration ids; the cohort
        # and organisation sit one hop further, read once for all records.
        cohort_of_registration = {
            pk: (cohort_id, organisation_id)
            for pk, cohort_id, organisation_id in CohortCourseRegistration._base_manager.filter(
                site_id=site_id, pk__in=cohort_registration_ids
            ).values_list("pk", "cohort_id", "cohort__organisation_id")
        }
        learner_organisations = dict(
            Learner._base_manager.filter(
                site_id=site_id, pk__in={r.learner_id for r in records}
            ).values_list("pk", "organisation_id")
        )
        site_row = SiteDeadlineConfig._base_manager.filter(site_id=site_id).first()
        course_rows = _rows_by_owner(
            CourseDeadlineConfig, "course", {r.course_id for r in records}, site_id
        )
        organisation_ids = {
            organisation_id for _, organisation_id in cohort_of_registration.values()
        } | set(learner_organisations.values())
        organisation_rows = _rows_by_owner(
            OrganisationDeadlineConfig, "organisation", organisation_ids, site_id
        )
        cohort_rows = _rows_by_owner(
            CohortDeadlineConfig,
            "cohort",
            {cohort_id for cohort_id, _ in cohort_of_registration.values()},
            site_id,
        )
        cohort_registration_rows = _rows_by_owner(
            CohortCourseRegistrationDeadlineConfig,
            "cohort_registration",
            cohort_registration_ids,
            site_id,
        )
        learner_registration_rows = _rows_by_owner(
            LearnerCourseRegistrationDeadlineConfig,
            "learner_registration",
            learner_registration_ids,
            site_id,
        )

        resolved: dict[UUID, ResolvedDeadlinePolicy] = {}
        for record in records:
            registration_row: DeadlineConfigFields | None
            cohort_row: DeadlineConfigFields | None = None
            if record.cohort_registration_id is not None:
                cohort_id, cohort_organisation_id = cohort_of_registration.get(
                    record.cohort_registration_id, (None, None)
                )
                registration_row = cohort_registration_rows.get(
                    record.cohort_registration_id
                )
                cohort_row = cohort_rows.get(cohort_id) if cohort_id else None
                organisation_id = cohort_organisation_id
            else:
                registration_row = (
                    learner_registration_rows.get(record.learner_registration_id)
                    if record.learner_registration_id is not None
                    else None
                )
                organisation_id = learner_organisations.get(record.learner_id)
            rows_by_layer: dict[str, DeadlineConfigFields | None] = {
                "registration": registration_row,
                "cohort": cohort_row,
                "organisation": (
                    organisation_rows.get(organisation_id) if organisation_id else None
                ),
                "course": course_rows.get(record.course_id),
                "site": site_row,
            }
            layers: Layers = [
                (layer, rows_by_layer[layer])
                for layer in self.LAYER_ORDER
                if layer != SETTINGS_LAYER
            ]
            resolved[record.pk] = self._resolve_one(layers)
        return resolved

    def _resolve_one(self, layers: Layers) -> ResolvedDeadlinePolicy:
        defaults = config.DEADLINE_POLICY_DEFAULTS
        sources: dict[str, str] = {}

        def switch(field: str) -> bool:
            for layer, row in layers:
                value = getattr(row, field) if row is not None else None
                if value in (DeadlineSwitch.ON, DeadlineSwitch.OFF):
                    sources[field] = layer
                    return bool(value == DeadlineSwitch.ON)
            sources[field] = SETTINGS_LAYER
            return bool(defaults[field])

        def grace_window() -> timedelta:
            for layer, row in layers:
                value = row.grace_window if row is not None else None
                if value is not None:
                    sources["grace_window"] = layer
                    return value
            sources["grace_window"] = SETTINGS_LAYER
            return cast(timedelta, defaults["grace_window"])

        def after_access_ended() -> str:
            for layer, row in layers:
                value = row.after_access_ended if row is not None else None
                if value is not None and value != AfterAccessEnded.INHERIT:
                    sources["after_access_ended"] = layer
                    return str(value)
            sources["after_access_ended"] = SETTINGS_LAYER
            return str(defaults["after_access_ended"])

        return ResolvedDeadlinePolicy(
            mark_overdue=switch("mark_overdue"),
            close_items=switch("close_items"),
            end_course_access=switch("end_course_access"),
            notify_educators=switch("notify_educators"),
            grace_window=grace_window(),
            after_access_ended=after_access_ended(),
            sources=sources,
        )
