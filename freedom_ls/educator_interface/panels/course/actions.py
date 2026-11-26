"""The actions on a single course's page."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from django import forms
from django.db.models import Model, QuerySet
from django.http import HttpResponse

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.events import COHORT_CHANGED, REGISTRATION_CHANGED
from freedom_ls.educator_interface.forms import (
    CohortPickerForm,
    SingleLearnerPickerForm,
)
from freedom_ls.educator_interface.panels.common.actions import (
    EducatorReasonMixin,
    _empty_message,
    _picker_title,
)
from freedom_ls.educator_interface.panels.common.course_page import (
    CoursePageActionMixin,
    scoped,
)
from freedom_ls.educator_interface.panels.common.registration_actions import (
    ADD_COHORT_REGISTRATION,
    ADD_LEARNER_REGISTRATION,
    CHANGE_COHORT_REGISTRATION,
    CHANGE_LEARNER_REGISTRATION,
    CohortRegistrationDeactivation,
    LearnerRegistrationDeactivation,
    LearnerRegistrationReactivation,
    registration_changed_response,
)
from freedom_ls.learner_management.learner_actions import register_for_course
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    COURSE_NOT_OPEN_MESSAGE,
    CourseNotOpenError,
    cohorts_visible_to,
    learners_permitted_for,
)
from freedom_ls.learner_management.utils import register_cohort_for_course
from freedom_ls.panel_framework.actions import FormPanelAction, changed_response
from freedom_ls.panel_framework.context import PanelContext

__all__ = [
    "CourseRegisterAction",
    "DeactivateCourseCohortRegistrationAction",
    "DeactivateCourseLearnerRegistrationAction",
    "ReactivateCourseLearnerRegistrationAction",
    "RegisterCohortOnCourseAction",
    "RegisterLearnerOnCourseAction",
]


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


def _course_learner_registrations(
    ctx: PanelContext,
) -> QuerySet[LearnerCourseRegistration]:
    """The course's direct registrations for learners the user may change
    registrations of."""
    request = scoped(ctx)
    return LearnerCourseRegistration.objects.filter(
        course=cast(Course, ctx.instance),
        learner__in=learners_permitted_for(
            request.user, request.organisation, CHANGE_LEARNER_REGISTRATION
        ),
    )


class DeactivateCourseLearnerRegistrationAction(
    EducatorReasonMixin, CoursePageActionMixin, LearnerRegistrationDeactivation
):
    """Deactivates one of the course's active direct registrations from its
    Overview tab, where the action renders per row, never as a footer
    button."""

    def registration_scope(
        self, ctx: PanelContext
    ) -> QuerySet[LearnerCourseRegistration]:
        return _course_learner_registrations(ctx)

    def subject_of(self, row: Model) -> Learner:
        return cast(LearnerCourseRegistration, row).learner


class ReactivateCourseLearnerRegistrationAction(
    CoursePageActionMixin, LearnerRegistrationReactivation
):
    """Reactivates one of the course's inactive direct registrations from its
    Overview tab, where the action renders per row. It is offered only while
    the course is open to the organisation in view, since a reactivation
    elsewhere always fails."""

    def is_offered(self, ctx: PanelContext) -> bool:
        return self.course_open_here(ctx)

    def registration_scope(
        self, ctx: PanelContext
    ) -> QuerySet[LearnerCourseRegistration]:
        return _course_learner_registrations(ctx)

    def subject_of(self, row: Model) -> Learner:
        return cast(LearnerCourseRegistration, row).learner


class CourseRegisterAction(CoursePageActionMixin, FormPanelAction):
    """A Register dialog on the course page. It is offered only while the
    course is open to the organisation in view and is not retired."""

    def is_offered(self, ctx: PanelContext) -> bool:
        return not cast(Course, ctx.instance).is_retired and self.course_open_here(ctx)

    def register_or_refuse(
        self,
        ctx: PanelContext,
        form: forms.BaseForm,
        register: Callable[[], object],
        success: Callable[[], HttpResponse],
    ) -> HttpResponse:
        """Runs the registration service. A course not open to the
        organisation in view, or one the service finds closed to it,
        re-renders the dialog with that as a form error and writes nothing.
        The page check comes first because the service accepts another
        organisation's public course, which this page may not register for."""
        if not self.course_open_here(ctx):
            form.add_error(None, COURSE_NOT_OPEN_MESSAGE)
            return self.form_invalid(ctx, form)
        try:
            register()
        except CourseNotOpenError as error:
            form.add_error(None, str(error))
            return self.form_invalid(ctx, form)
        return success()


class RegisterCohortOnCourseAction(CourseRegisterAction):
    """Registers a cohort for the course on the page. Registering a cohort
    whose registration is inactive reactivates it."""

    label = "Register"
    action_name = "register_cohort"
    capability = ADD_COHORT_REGISTRATION
    form_class = CohortPickerForm
    refresh_on_change = ("cohort",)
    submit_buttons = [
        {"label": "Register", "variant": "primary", "loading_text": "Registering…"}
    ]

    def _cohorts(self, ctx: PanelContext) -> QuerySet[Cohort]:
        request = scoped(ctx)
        registered = CohortCourseRegistration.objects.filter(
            course=cast(Course, ctx.instance), is_active=True
        ).values("cohort_id")
        return (
            cohorts_visible_to(
                request.user,
                request.organisation,
                capability=ADD_COHORT_REGISTRATION,
            )
            .filter(is_active=True)
            .exclude(pk__in=registered)
            .order_by("name")
        )

    def get_form_kwargs(self, ctx: PanelContext) -> dict[str, object]:
        return {**super().get_form_kwargs(ctx), "queryset": self._cohorts(ctx)}

    def get_form_title(self, ctx: PanelContext, form: forms.BaseForm) -> str:
        label = cast(Course, ctx.instance).label_for(scoped(ctx).organisation)

        def chosen(cohort: Cohort) -> str:
            return f"Register {cohort.name} for {label}"

        return _picker_title(
            form, "cohort", unchosen=f"Register a cohort for {label}", chosen=chosen
        )

    def get_empty_message(self, ctx: PanelContext, form: forms.BaseForm) -> str | None:
        return _empty_message(
            form, "cohort", "Every cohort you can register already has this course."
        )

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        cohort = cast(Cohort, form.cleaned_data["cohort"])
        course = cast(Course, ctx.instance)
        return self.register_or_refuse(
            ctx,
            form,
            lambda: register_cohort_for_course(
                cohort, course, actor=cast(User, ctx.request.user)
            ),
            lambda: changed_response(
                {
                    REGISTRATION_CHANGED: [
                        str(
                            CohortCourseRegistration.objects.get(
                                cohort=cohort, course=course
                            ).pk
                        )
                    ],
                    COHORT_CHANGED: [str(cohort.pk)],
                }
            ),
        )


class RegisterLearnerOnCourseAction(CourseRegisterAction):
    """Registers one learner directly for the course on the page. Registering
    a learner whose registration is inactive reactivates it."""

    label = "Register"
    action_name = "register_learner"
    capability = ADD_LEARNER_REGISTRATION
    form_class = SingleLearnerPickerForm
    refresh_on_change = ("learner",)
    submit_buttons = [
        {"label": "Register", "variant": "primary", "loading_text": "Registering…"}
    ]

    def _learners(self, ctx: PanelContext) -> QuerySet[Learner]:
        request = scoped(ctx)
        registered = LearnerCourseRegistration.objects.filter(
            course=cast(Course, ctx.instance), is_active=True
        ).values("learner_id")
        return (
            learners_permitted_for(
                request.user, request.organisation, ADD_LEARNER_REGISTRATION
            )
            .filter(is_active=True)
            .exclude(pk__in=registered)
            .select_related("user")
        )

    def get_form_kwargs(self, ctx: PanelContext) -> dict[str, object]:
        return {**super().get_form_kwargs(ctx), "queryset": self._learners(ctx)}

    def get_form_title(self, ctx: PanelContext, form: forms.BaseForm) -> str:
        label = cast(Course, ctx.instance).label_for(scoped(ctx).organisation)

        def chosen(learner: Learner) -> str:
            return f"Register {learner.user.display_name} for {label}"

        return _picker_title(
            form, "learner", unchosen=f"Register a learner for {label}", chosen=chosen
        )

    def get_empty_message(self, ctx: PanelContext, form: forms.BaseForm) -> str | None:
        return _empty_message(
            form, "learner", "Every learner you can register already has this course."
        )

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        learner = cast(Learner, form.cleaned_data["learner"])
        course = cast(Course, ctx.instance)
        return self.register_or_refuse(
            ctx,
            form,
            lambda: register_for_course(
                learner, course, actor=cast(User, ctx.request.user)
            ),
            lambda: registration_changed_response(learner),
        )
