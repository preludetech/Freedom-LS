from collections.abc import Mapping
from typing import cast

from django import forms
from django.db.models import QuerySet
from django.http import QueryDict

from freedom_ls.accounts.models import User
from freedom_ls.learner_management.learner_actions import LearnerEntry
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    registerable_courses_for,
    registerable_courses_for_learner,
)
from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin


class CohortForm(ConstraintValidationFormMixin):
    """Form for a cohort's editable fields.

    ``organisation`` and ``site`` are both un-excluded so
    ``unique_cohort_name_per_organisation`` is checked while cleaning rather
    than failing at the database. Un-excluding ``site`` is safe even though
    neither it nor ``organisation`` is rendered here: SiteAwareModelBase.full_clean()
    fills ``site`` from the current request before validation runs, and the
    view attaches ``organisation`` to the instance before the form validates.
    """

    constraint_fields = ("organisation", "site")

    class Meta:
        model = Cohort
        fields = ["name"]


class LearnerNameForm(forms.ModelForm):
    """A learner's first and last name, edited on their user."""

    class Meta:
        model = User
        fields = ["first_name", "last_name"]


class CohortCourseRegistrationForm(forms.ModelForm):
    """The course picker for registering a cohort.

    A ModelForm only because FormPanelAction types its form that way. Nothing
    calls save() on it: the chosen course goes to register_cohort_for_course,
    which owns the reuse of an inactive row.
    """

    class Meta:
        model = CohortCourseRegistration
        fields = ["course"]

    def __init__(
        self, data: Mapping[str, str] | None = None, *, cohort: Cohort
    ) -> None:
        super().__init__(data)
        course_field = cast(forms.ModelChoiceField, self.fields["course"])
        course_field.queryset = registerable_courses_for(cohort)


class LearnerCourseRegistrationForm(forms.ModelForm):
    """The course picker for registering a learner.

    A ModelForm only because FormPanelAction types its form that way. Nothing
    calls save() on it: the chosen course goes to register_for_course, which
    owns the reuse of an inactive row.
    """

    class Meta:
        model = LearnerCourseRegistration
        fields = ["course"]

    def __init__(
        self, data: Mapping[str, str] | None = None, *, learner: Learner
    ) -> None:
        super().__init__(data)
        course_field = cast(forms.ModelChoiceField, self.fields["course"])
        course_field.queryset = registerable_courses_for_learner(learner)


class CohortPickerForm(forms.Form):
    """Picks one cohort from the queryset the action offers. The field is
    named `cohort` unless `field_name` says otherwise."""

    cohort = forms.ModelChoiceField(queryset=Cohort.objects.none())

    def __init__(
        self,
        data: Mapping[str, str] | None = None,
        *,
        queryset: QuerySet[Cohort],
        field_name: str = "cohort",
    ) -> None:
        super().__init__(data)
        self.fields[field_name] = self.fields.pop("cohort")
        cast(forms.ModelChoiceField, self.fields[field_name]).queryset = queryset


class LearnerPickerForm(forms.Form):
    """Picks any number of learners from the queryset the action offers."""

    learners = forms.ModelMultipleChoiceField(
        queryset=Learner.objects.none(), widget=forms.SelectMultiple
    )

    def __init__(
        self, data: QueryDict | None = None, *, queryset: QuerySet[Learner]
    ) -> None:
        super().__init__(data)
        cast(
            forms.ModelMultipleChoiceField, self.fields["learners"]
        ).queryset = queryset


MAX_ADD_LEARNERS = 50


class AddLearnersForm(forms.Form):
    """Pasted lines of `email, first name, last name`, and an optional cohort.

    An invalid address is not a form error: add_learners reports it on its
    own row, so one typo does not block the rest of the list.
    """

    entries = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 8}),
        help_text="One per line: email, first name, last name",
    )
    cohort = forms.ModelChoiceField(queryset=Cohort.objects.none(), required=False)

    def __init__(
        self,
        data: Mapping[str, str] | None = None,
        *,
        cohorts: QuerySet[Cohort],
        preset: Cohort | None = None,
    ) -> None:
        super().__init__(data)
        cohort_field = cast(forms.ModelChoiceField, self.fields["cohort"])
        cohort_field.queryset = cohorts
        if preset is not None:
            cohort_field.widget = forms.HiddenInput()
            cohort_field.initial = preset.pk

    def clean_entries(self) -> list[LearnerEntry]:
        lines = [
            line.strip()
            for line in self.cleaned_data["entries"].splitlines()
            if line.strip()
        ]
        if not lines:
            raise forms.ValidationError("Enter at least one email address.")
        if len(lines) > MAX_ADD_LEARNERS:
            raise forms.ValidationError(
                f"Add up to {MAX_ADD_LEARNERS} at a time; larger lists are "
                "imported from a file."
            )
        entries = []
        for line in lines:
            email, first_name, last_name, *_ = [
                part.strip() for part in line.split(",")
            ] + ["", ""]
            entries.append(LearnerEntry(email, first_name, last_name))
        return entries
