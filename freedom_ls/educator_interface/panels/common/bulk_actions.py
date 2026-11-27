"""The educator bulk-action base and the course picker the course registration actions share."""

from __future__ import annotations

from typing import cast

from panel_framework.bulk_actions import (
    PermittedBulkAction,
    RecordedBulkAction,
)
from panel_framework.bulk_runs import run_summary
from panel_framework.models import BulkActionRun

from django import forms
from django.db.models import Model, QuerySet
from django.http import HttpRequest, QueryDict
from django.shortcuts import get_object_or_404

from freedom_ls.accounts.models import User
from freedom_ls.comms.notify import mark_notifications_read, raise_notification
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.forms import CoursePickerForm, course_target
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.learner_management.queries import can_on_any, registerable_courses
from freedom_ls.organisations.models import Organisation

__all__ = [
    "CoursePickerMixin",
    "EducatorBulkAction",
]


class EducatorBulkAction(PermittedBulkAction[User]):
    """A bulk action over the rows of an educator-interface table, scoped to
    the organisation the request was made under.

    Each object is changed with the same capability and service its
    single-object action uses.
    """

    def has_permission(self, request: HttpRequest) -> bool:
        scoped = cast("OrganisationScopedRequest", request)
        return can_on_any(scoped.user, scoped.organisation, self.capability)

    def scope_for_request(self, request: HttpRequest) -> Model | None:
        return cast("OrganisationScopedRequest", request).organisation

    def objects_for_keys(self, scope: Model | None, keys: list[str]) -> QuerySet:
        # Narrowed to the run's organisation, so a key from another one can
        # never be reached through a stored run.
        return self.noun_model._base_manager.filter(
            organisation=cast(Organisation, scope), pk__in=keys
        )

    def on_finished(self, run: BulkActionRun) -> None:
        raise_notification(
            user=run.requested_by,
            category="bulk_action.finished",
            target=run,
            site_id=run.site_id,
            data={"summary": run_summary(run)},
        )

    def on_result_shown(self, request: HttpRequest, run: BulkActionRun) -> None:
        mark_notifications_read(
            user=cast("User", request.user), target=run, site_id=run.site_id
        )


class CoursePickerMixin(RecordedBulkAction):
    """The course picker the course registration actions share: its form,
    and the picked course as a run stores it and reads it back. Declared on
    RecordedBulkAction so the overrides type-check; list it before the
    action in the bases."""

    form_class = CoursePickerForm

    def get_form(self, request: HttpRequest, data: QueryDict | None) -> forms.Form:
        organisation = cast("OrganisationScopedRequest", request).organisation
        return CoursePickerForm(
            data,
            queryset=registerable_courses(organisation),
            organisation=organisation,
        )

    def target_json(self, cleaned_data: dict[str, object]) -> dict[str, str]:
        return {"course": str(cast(Course, cleaned_data["course"]).pk)}

    def resolve_target(
        self, scope: Model | None, target: dict[str, str]
    ) -> dict[str, object]:
        organisation = cast(Organisation, scope)
        course = get_object_or_404(
            registerable_courses(organisation).prefetch_related("organisations"),
            pk=target["course"],
        )
        return course_target(course, organisation)
