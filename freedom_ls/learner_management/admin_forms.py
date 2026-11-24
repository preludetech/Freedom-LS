"""Admin pickers for a learner, a learner's registration or a cohort's registration.

The Learner and registration models have no admin of their own, so a picker cannot look one up
through a raw-ID popup or an autocomplete. Staff type the learner's email instead, and the form
finds the row on the current site.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar, Self, cast

from unfold.widgets import UnfoldAdminEmailInputWidget, UnfoldAdminSelectWidget

from django import forms
from django.db import models
from django.http import HttpRequest

from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.models import (
    CohortCourseRegistration,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.organisations.models import Organisation
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin

NO_LEARNER = "No learner on this site has this email."
SEVERAL_ORGANISATIONS = (
    "This email belongs to a learner in more than one organisation. Pick one."
)
NOT_REGISTERED = "This learner is not registered for this course."


class SiteChoiceField(forms.ModelChoiceField):
    """A select whose queryset is made again for each form, under the request's site.

    A site-aware manager filters by site when the queryset is made, so one made when the form
    class is defined would belong to no site. Each form deep-copies its fields, so the copy is
    where the queryset is made."""

    def __init__(
        self,
        make_queryset: Callable[[], models.QuerySet],
        *,
        required: bool = True,
        help_text: str = "",
    ) -> None:
        super().__init__(
            queryset=make_queryset().none(),
            required=required,
            widget=UnfoldAdminSelectWidget,
            help_text=help_text,
        )
        self.make_queryset = make_queryset

    def __deepcopy__(self, memo: dict[int, object]) -> Self:
        field = super().__deepcopy__(memo)
        field.queryset = self.make_queryset()
        return field


def _organisations() -> models.QuerySet[Organisation]:
    return Organisation.objects.order_by("name")


def _courses() -> models.QuerySet[Course]:
    return Course.objects.order_by("title")


class LearnerPickerForm(forms.ModelForm):
    """Picks the learner a config row belongs to by the learner's email.

    The row's foreign key, named by `learner_field`, is not a form field. `clean` sets it on the
    instance and checks that no other row already holds that learner."""

    learner_field: ClassVar[str] = "learner"

    learner_email = forms.EmailField(
        label="Learner email", widget=UnfoldAdminEmailInputWidget
    )
    organisation = SiteChoiceField(
        _organisations,
        required=False,
        help_text="Needed only when the email belongs to learners in more than one "
        "organisation.",
    )

    def get_initial_for_field(self, field: forms.Field, field_name: str) -> object:
        """On an existing row, the picker fields show the learner it belongs to."""
        if not self.instance._state.adding and field_name not in self.initial:
            picked = self._initial_from(getattr(self.instance, self.learner_field))
            if field_name in picked:
                return picked[field_name]
        initial: object = super().get_initial_for_field(field, field_name)
        return initial

    def _initial_from(self, target: models.Model) -> dict[str, object]:
        learner = cast(Learner, target)
        return {
            "learner_email": learner.user.email,
            "organisation": learner.organisation_id,
        }

    def _learners(self, email: str, organisation: Organisation | None) -> list[Learner]:
        learners = Learner.objects.select_related("user", "organisation").filter(
            user__email__iexact=email
        )
        if organisation is not None:
            learners = learners.filter(organisation=organisation)
        return list(learners[:2])

    def _matches(
        self, email: str, organisation: Organisation | None
    ) -> list[models.Model] | None:
        """The rows the email picks, at most two. None when a field error was added."""
        return list(self._learners(email, organisation))

    def clean(self) -> dict[str, object]:
        cleaned: dict[str, object] = super().clean() or {}
        email = cleaned.get("learner_email")
        if not isinstance(email, str):
            return cleaned
        organisation = cleaned.get("organisation")
        matches = self._matches(
            email, organisation if isinstance(organisation, Organisation) else None
        )
        if matches is None:
            return cleaned
        if not matches:
            self.add_error("learner_email", NO_LEARNER)
        elif len(matches) > 1:
            self.add_error("organisation", SEVERAL_ORGANISATIONS)
        else:
            self._set_target(matches[0])
        return cleaned

    def _set_target(self, target: models.Model) -> None:
        model = self._meta.model
        taken = (
            model._default_manager.filter(**{self.learner_field: target})
            .exclude(pk=self.instance.pk)
            .exists()
        )
        if taken:
            self.add_error(
                "learner_email",
                f"A {model._meta.verbose_name} already exists for this learner.",
            )
            return
        setattr(self.instance, self.learner_field, target)


class LearnerRegistrationPickerForm(LearnerPickerForm):
    """Picks a learner's course registration by the learner's email and the course."""

    learner_field: ClassVar[str] = "registration"

    course = SiteChoiceField(_courses)

    def _initial_from(self, target: models.Model) -> dict[str, object]:
        registration = cast(LearnerCourseRegistration, target)
        return {
            **super()._initial_from(registration.learner),
            "course": registration.course_id,
        }

    def _matches(
        self, email: str, organisation: Organisation | None
    ) -> list[models.Model] | None:
        course = self.cleaned_data.get("course")
        if not isinstance(course, Course):
            return None
        registrations = LearnerCourseRegistration.objects.select_related(
            "learner__user", "learner__organisation", "course"
        ).filter(learner__user__email__iexact=email, course=course)
        if organisation is not None:
            registrations = registrations.filter(learner__organisation=organisation)
        matches: list[models.Model] = list(registrations[:2])
        if not matches and self._learners(email, organisation):
            self.add_error("course", NOT_REGISTERED)
            return None
        return matches


class CohortRegistrationPickerAdmin(SiteAwareModelAdmin):
    """Loads each cohort registration option with its cohort and course, which its label
    names. Not registered itself."""

    cohort_registration_field: ClassVar[str]

    def formfield_for_foreignkey(
        self,
        db_field: models.ForeignKey,
        request: HttpRequest,
        **kwargs: object,
    ) -> forms.ModelChoiceField | None:
        if db_field.name == self.cohort_registration_field:
            kwargs["queryset"] = CohortCourseRegistration.objects.select_related(
                "cohort", "course"
            )
        field: forms.ModelChoiceField | None = super().formfield_for_foreignkey(
            db_field, request, **kwargs
        )
        return field
