from collections.abc import Mapping
from typing import cast

from django import forms

from freedom_ls.learner_management.models import Cohort, CohortCourseRegistration
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
