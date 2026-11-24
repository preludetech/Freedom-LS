"""Registration actions shared by every page that lists course registrations.

Each dialog lives here once. A page supplies only which registrations it may
reach and how it refreshes."""

from __future__ import annotations

from typing import cast

from django.db.models import QuerySet
from django.http import HttpResponse
from django.shortcuts import render

from freedom_ls.accounts.models import User
from freedom_ls.educator_interface.events import LEARNER_CHANGED, REGISTRATION_CHANGED
from freedom_ls.educator_interface.panels.common.actions import (
    inactive_cohort_response,
)
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.learner_management.learner_actions import (
    deactivate_registration,
    register_for_course,
)
from freedom_ls.learner_management.models import (
    CohortCourseRegistration,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    COURSE_NOT_OPEN_MESSAGE,
    CourseNotOpenError,
    cohort_learner_count,
    cohorts_visible_to,
    is_course_available_to_organisation,
    members_keeping_access,
    other_grants_for,
)
from freedom_ls.learner_management.utils import deactivate_cohort_registration
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.panel_framework.actions import (
    ConfirmAction,
    changed_response,
    count_noun,
    join_prose,
)
from freedom_ls.panel_framework.context import PanelContext

__all__ = [
    "ADD_COHORT_REGISTRATION",
    "ADD_LEARNER_REGISTRATION",
    "CHANGE_COHORT_REGISTRATION",
    "CHANGE_LEARNER_REGISTRATION",
    "KEEPING_NAMES_SHOWN",
    "CohortRegistrationDeactivation",
    "LearnerRegistrationDeactivation",
    "LearnerRegistrationReactivation",
    "registration_changed_response",
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


def registration_changed_response(learner: Learner) -> HttpResponse:
    """The 204 every learner registration change answers with: both events,
    and the modal closed."""
    ids = [str(learner.pk)]
    return changed_response({REGISTRATION_CHANGED: ids, LEARNER_CHANGED: ids})


class LearnerRegistrationDeactivation(ConfirmAction):
    """Deactivates one active individual course registration, after
    confirmation. The registration travels as a `registration` parameter and
    carries its own learner and course, so the same dialog serves any page
    that lists them. A subclass narrows the rows it may reach."""

    label = "Deactivate"
    action_name = "deactivate_registration"
    renders_in_footer = False
    capability = CHANGE_LEARNER_REGISTRATION
    loading_text = "Deactivating…"
    template_name = "educator_interface/modal/deactivate_registration_confirmation.html"
    row_param = "registration"

    def registration_scope(
        self, ctx: PanelContext
    ) -> QuerySet[LearnerCourseRegistration]:
        raise NotImplementedError

    def get_row_queryset(
        self, ctx: PanelContext
    ) -> QuerySet[LearnerCourseRegistration]:
        return (
            self.registration_scope(ctx)
            .filter(is_active=True)
            .select_related("learner__user", "course")
        )

    def _registration(self, ctx: PanelContext) -> LearnerCourseRegistration:
        return cast(LearnerCourseRegistration, self.get_row_object(ctx))

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        registration = self._registration(ctx)
        learner = registration.learner
        request = cast(OrganisationScopedRequest, ctx.request)
        granting = other_grants_for(learner, registration.course)
        # A cohort the educator cannot see is never named.
        visible_ids = set(
            cohorts_visible_to(request.user, request.organisation).values_list(
                "pk", flat=True
            )
        )
        return {
            "learner": learner,
            "registration": registration,
            "course": registration.course,
            "keeping_cohorts": join_prose(
                [cohort.name for cohort in granting if cohort.pk in visible_ids]
            ),
            "keeps_access": bool(granting),
            "on_default_organisation": (
                learner.organisation_id == get_default_organisation(learner.site).pk
            ),
        }

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        registration = self._registration(ctx)
        deactivate_registration(
            registration.learner,
            registration.course,
            actor=cast("User", ctx.request.user),
            reason=ctx.reason,
        )
        return registration_changed_response(registration.learner)


class LearnerRegistrationReactivation(ConfirmAction):
    """Reactivates one inactive individual course registration, after
    confirmation. Like deactivating, the registration travels as a
    `registration` parameter and carries its own learner and course."""

    label = "Reactivate"
    action_name = "reactivate_registration"
    renders_in_footer = False
    capability = CHANGE_LEARNER_REGISTRATION
    loading_text = "Reactivating…"
    template_name = "educator_interface/modal/reactivate_registration_confirmation.html"
    row_param = "registration"

    def registration_scope(
        self, ctx: PanelContext
    ) -> QuerySet[LearnerCourseRegistration]:
        raise NotImplementedError

    def get_row_queryset(
        self, ctx: PanelContext
    ) -> QuerySet[LearnerCourseRegistration]:
        return (
            self.registration_scope(ctx)
            .filter(is_active=False)
            .select_related("learner__user", "course")
        )

    def _registration(self, ctx: PanelContext) -> LearnerCourseRegistration:
        return cast(LearnerCourseRegistration, self.get_row_object(ctx))

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        registration = self._registration(ctx)
        return {
            "learner": registration.learner,
            "registration": registration,
            "course": registration.course,
        }

    def _refused(self, ctx: PanelContext, message: str) -> HttpResponse:
        context = self.get_context_data(ctx)
        context["refusal"] = message
        return render(ctx.request, self.template_name, context, status=422)

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        registration = self._registration(ctx)
        learner = registration.learner
        course = registration.course
        # The write gate accepts every public course, but an educator registers
        # only for courses available to the organisation.
        if not is_course_available_to_organisation(course, learner.organisation):
            return self._refused(ctx, COURSE_NOT_OPEN_MESSAGE)
        try:
            register_for_course(learner, course, actor=cast("User", ctx.request.user))
        except CourseNotOpenError as error:
            # The course may have gained organisations since the registration
            # was made, leaving it closed to this learner's organisation.
            return self._refused(ctx, str(error))
        return registration_changed_response(learner)
