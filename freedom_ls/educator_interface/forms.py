from collections.abc import Mapping
from typing import cast

from django import forms
from django.db.models import QuerySet
from django.http import QueryDict

from freedom_ls.accounts.models import User
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
)
from freedom_ls.learner_management.queries import registerable_courses_for
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


class CohortPickerForm(forms.Form):
    """Picks one cohort from the queryset the action offers."""

    cohort = forms.ModelChoiceField(queryset=Cohort.objects.none())

    def __init__(
        self, data: Mapping[str, str] | None = None, *, queryset: QuerySet[Cohort]
    ) -> None:
        super().__init__(data)
        cast(forms.ModelChoiceField, self.fields["cohort"]).queryset = queryset


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
