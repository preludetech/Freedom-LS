"""The actions on a single course's page."""

from __future__ import annotations

from typing import cast

from django.db.models import Model, QuerySet
from django.http import HttpResponse

from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.events import COHORT_CHANGED, REGISTRATION_CHANGED
from freedom_ls.educator_interface.panels.common.actions import EducatorReasonMixin
from freedom_ls.educator_interface.panels.common.course_page import (
    CoursePageActionMixin,
    scoped,
)
from freedom_ls.educator_interface.panels.common.registration_actions import (
    CHANGE_COHORT_REGISTRATION,
    CohortRegistrationDeactivation,
)
from freedom_ls.learner_management.models import Cohort, CohortCourseRegistration
from freedom_ls.learner_management.queries import cohorts_visible_to
from freedom_ls.panel_framework.actions import changed_response
from freedom_ls.panel_framework.context import PanelContext

__all__ = ["DeactivateCourseCohortRegistrationAction"]


class DeactivateCourseCohortRegistrationAction(
    EducatorReasonMixin, CoursePageActionMixin, CohortRegistrationDeactivation
):
    """Deactivates one of the course's active cohort registrations from its
    Overview tab, where the action renders per row, never as a footer button."""

    def registration_scope(
        self, ctx: PanelContext
    ) -> QuerySet[CohortCourseRegistration]:
        request = scoped(ctx)
        return CohortCourseRegistration.objects.filter(
            course=cast(Course, ctx.instance),
            cohort__in=cohorts_visible_to(
                request.user,
                request.organisation,
                capability=CHANGE_COHORT_REGISTRATION,
            ),
        )

    def subject_of(self, row: Model) -> Cohort:
        return cast(CohortCourseRegistration, row).cohort

    def success_response(
        self, ctx: PanelContext, registration: CohortCourseRegistration
    ) -> HttpResponse:
        return changed_response(
            {
                REGISTRATION_CHANGED: [str(registration.pk)],
                COHORT_CHANGED: [str(registration.cohort_id)],
            }
        )
