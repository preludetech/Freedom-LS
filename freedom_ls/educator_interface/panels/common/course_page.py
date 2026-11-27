"""What every action on the course page shares.

A course belongs to no cohort or learner, and `can()` has no rule for a
course, so nothing on this page asks it about the course itself."""

from __future__ import annotations

from typing import cast

from panel_framework.actions import PanelAction
from panel_framework.context import PanelContext

from django.db.models import Model

from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.models import Cohort, Learner
from freedom_ls.learner_management.queries import (
    can_on_any,
    is_course_available_to_organisation,
)

__all__ = ["CoursePageActionMixin", "scoped"]


def scoped(ctx: PanelContext) -> OrganisationScopedRequest:
    return cast(OrganisationScopedRequest, ctx.request)


class CoursePageActionMixin(PanelAction):
    """An action on the course page. Its capability is asked about the
    organisation in view until a request names a row, then about the row's
    own cohort or learner, because can() has no rule for a course. List it
    after any reason mixin and before the action it guards."""

    def subject_of(self, row: Model) -> Cohort | Learner:
        """The cohort or learner a row of this action belongs to."""
        raise NotImplementedError

    def row_subject(self, ctx: PanelContext) -> Cohort | Learner | None:
        if self.row_param is None:
            return None
        params = ctx.request.POST if ctx.request.method == "POST" else ctx.request.GET
        if self.row_param not in params:
            return None
        return self.subject_of(self.get_row_object(ctx))

    def course_open_here(self, ctx: PanelContext) -> bool:
        """Whether the course is available to the organisation in view, which
        a registration made from this page needs."""
        return is_course_available_to_organisation(
            cast(Course, ctx.instance), scoped(ctx).organisation
        )

    def permission_object(self, ctx: PanelContext) -> Model | None:
        return scoped(ctx).organisation

    def has_permission(self, ctx: PanelContext) -> bool:
        capability = self.get_capability(ctx)
        if capability is None:
            return True
        request = scoped(ctx)
        subject = self.row_subject(ctx)
        if subject is None:
            return can_on_any(request.user, request.organisation, capability)
        return can(request.user, capability, subject)
