"""Registration actions shared by every page that lists course registrations.

Each dialog lives here once. A page supplies only which registrations it may
reach and how it refreshes."""

from __future__ import annotations

from typing import cast

from django.db.models import QuerySet
from django.http import HttpResponse

from freedom_ls.accounts.models import User
from freedom_ls.educator_interface.panels.common.actions import (
    inactive_cohort_response,
)
from freedom_ls.learner_management.models import CohortCourseRegistration, Learner
from freedom_ls.learner_management.queries import (
    cohort_learner_count,
    members_keeping_access,
)
from freedom_ls.learner_management.utils import deactivate_cohort_registration
from freedom_ls.panel_framework.actions import ConfirmAction, count_noun, join_prose
from freedom_ls.panel_framework.context import PanelContext

__all__ = [
    "ADD_COHORT_REGISTRATION",
    "ADD_LEARNER_REGISTRATION",
    "CHANGE_COHORT_REGISTRATION",
    "CHANGE_LEARNER_REGISTRATION",
    "KEEPING_NAMES_SHOWN",
    "CohortRegistrationDeactivation",
]

ADD_COHORT_REGISTRATION = "freedom_ls_learner_management.add_cohortcourseregistration"
CHANGE_COHORT_REGISTRATION = (
    "freedom_ls_learner_management.change_cohortcourseregistration"
)
ADD_LEARNER_REGISTRATION = "freedom_ls_learner_management.add_learnercourseregistration"
CHANGE_LEARNER_REGISTRATION = (
    "freedom_ls_learner_management.change_learnercourseregistration"
)

KEEPING_NAMES_SHOWN = 10


class CohortRegistrationDeactivation(ConfirmAction):
    """Deactivates one active cohort course registration, after
    confirmation. The registration travels as a `registration` parameter
    and carries its own cohort and course, so the same dialog serves any
    page that lists registrations. A subclass narrows the rows it may reach
    and says how the page refreshes."""

    label = "Deactivate"
    action_name = "deactivate_cohort_registration"
    renders_in_footer = False
    capability = CHANGE_COHORT_REGISTRATION
    loading_text = "Deactivating…"
    template_name = (
        "educator_interface/modal/deactivate_cohort_registration_confirmation.html"
    )
    row_param = "registration"

    def registration_scope(
        self, ctx: PanelContext
    ) -> QuerySet[CohortCourseRegistration]:
        raise NotImplementedError

    def success_response(
        self, ctx: PanelContext, registration: CohortCourseRegistration
    ) -> HttpResponse:
        raise NotImplementedError

    def get_row_queryset(self, ctx: PanelContext) -> QuerySet[CohortCourseRegistration]:
        return (
            self.registration_scope(ctx)
            .filter(is_active=True)
            .select_related("cohort", "course")
        )

    def _registration(self, ctx: PanelContext) -> CohortCourseRegistration:
        return cast(CohortCourseRegistration, self.get_row_object(ctx))

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        registration = self._registration(ctx)
        cohort = registration.cohort
        keeping = list(members_keeping_access(registration))
        member_count = cohort_learner_count(cohort)
        names = [learner.user.display_name for learner in keeping[:KEEPING_NAMES_SHOWN]]
        if len(keeping) > KEEPING_NAMES_SHOWN:
            names.append(f"{len(keeping) - KEEPING_NAMES_SHOWN} more")
        return {
            "cohort": cohort,
            "registration": registration,
            "course": registration.course,
            "losing_count": member_count - len(keeping),
            "losing_phrase": count_noun(Learner, member_count - len(keeping)),
            "keeping_names": join_prose(names),
        }

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        registration = self._registration(ctx)
        if not registration.cohort.is_active:
            return inactive_cohort_response(
                ctx, registration.cohort, "deactivate one of its course registrations"
            )
        deactivate_cohort_registration(
            registration, actor=cast("User", ctx.request.user), reason=ctx.reason
        )
        return self.success_response(ctx, registration)
