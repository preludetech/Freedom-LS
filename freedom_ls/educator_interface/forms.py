from collections.abc import Mapping
from typing import cast

from django import forms
from django.db.models import QuerySet
from django.http import QueryDict

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.learner_actions import LearnerEntry
from freedom_ls.learner_management.models import (
    Cohort,
    Learner,
)
from freedom_ls.learner_management.queries import (
    ORGANISATION_ROLES,
    registerable_courses_for,
    registerable_courses_for_learner,
)
from freedom_ls.panel_framework.forms import ReasonForm
from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin


def choice_error(label: str) -> dict[str, str]:
    """The `error_messages` for a picker field. Django's own messages quote
    the submitted value, which for a stale pick is a bare id: invalid_choice
    for a pick not in the queryset, invalid_pk_value for one a multiple
    choice field cannot even cast to a key."""
    message = f"Choose a {label.lower()} from the list."
    return {"invalid_choice": message, "invalid_pk_value": message}


class LearnerImportForm(forms.Form):
    file = forms.FileField(
        label="CSV file",
        widget=forms.ClearableFileInput(
            attrs={
                "accept": ".csv,text/csv",
                "aria-describedby": "import-file-limits",
                "class": "sr-only",
            }
        ),
    )


class BulkTargetPickerForm(forms.Form):
    """Picks the one target a bulk action applies to, from every target the
    user may act on in the organisation. `field_name` is "cohort" or "course"."""

    def __init__(
        self,
        data: Mapping[str, str] | None = None,
        *,
        field_name: str,
        queryset: QuerySet,
        label: str,
    ) -> None:
        super().__init__(data)
        self.fields[field_name] = forms.ModelChoiceField(
            queryset=queryset, label=label, error_messages=choice_error(label)
        )


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


class CohortCourseRegistrationForm(forms.Form):
    """The course picker for registering a cohort. The chosen course goes to
    register_cohort_for_course, which owns the reuse of an inactive row."""

    course = forms.ModelChoiceField(queryset=Course.objects.none())

    def __init__(
        self, data: Mapping[str, str] | None = None, *, cohort: Cohort
    ) -> None:
        super().__init__(data)
        course_field = cast(forms.ModelChoiceField, self.fields["course"])
        course_field.queryset = registerable_courses_for(cohort)


class LearnerCourseRegistrationForm(forms.Form):
    """The course picker for registering a learner. The chosen course goes to
    register_for_course, which owns the reuse of an inactive row."""

    course = forms.ModelChoiceField(queryset=Course.objects.none())

    def __init__(
        self, data: Mapping[str, str] | None = None, *, learner: Learner
    ) -> None:
        super().__init__(data)
        course_field = cast(forms.ModelChoiceField, self.fields["course"])
        course_field.queryset = registerable_courses_for_learner(learner)


class CohortPickerForm(forms.Form):
    """Picks one cohort from the queryset the action offers. The field is
    named `cohort` unless `field_name` says otherwise."""

    cohort = forms.ModelChoiceField(
        queryset=Cohort.objects.none(), error_messages=choice_error("cohort")
    )

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


class LearnerMultipleChoiceField(forms.ModelMultipleChoiceField):
    """Labels each learner by their display name, which falls back to their
    email."""

    def label_from_instance(self, obj: Learner) -> str:
        return obj.user.display_name


class LearnerPickerForm(forms.Form):
    """Picks any number of learners from the queryset the action offers."""

    learners = LearnerMultipleChoiceField(
        queryset=Learner.objects.none(),
        widget=forms.SelectMultiple,
        error_messages=choice_error("learner"),
    )

    def __init__(
        self, data: QueryDict | None = None, *, queryset: QuerySet[Learner]
    ) -> None:
        super().__init__(data)
        cast(LearnerMultipleChoiceField, self.fields["learners"]).queryset = queryset


class AddLearnerForm(forms.Form):
    """One learner: an email address, an optional name and an optional
    cohort. A list of people is the file import, not this form."""

    email = forms.EmailField(label="Email address")
    first_name = forms.CharField(required=False, max_length=200)
    last_name = forms.CharField(required=False, max_length=200)
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

    def entry(self) -> LearnerEntry:
        """The validated person, for add_learner."""
        return LearnerEntry(
            self.cleaned_data["email"].strip(),
            self.cleaned_data["first_name"].strip(),
            self.cleaned_data["last_name"].strip(),
        )


class StaffEmailForm(forms.Form):
    """The email step: one address, looked up before anything is chosen."""

    email = forms.EmailField(label="Email address")


class AddStaffMemberForm(forms.Form):
    """The role step and the submit.

    On a GET the choices are what the grantor may give; on a POST they are
    every staff role and every cohort of the organisation, so a submitted
    choice outside the grantor's reach reaches the permission check and is
    refused as a denial rather than as a form error.
    """

    email = forms.EmailField(widget=forms.HiddenInput)
    first_name = forms.CharField(max_length=150, required=False, label="First name")
    last_name = forms.CharField(max_length=150, required=False, label="Last name")
    role = forms.ChoiceField(widget=forms.RadioSelect)
    cohorts = forms.ModelMultipleChoiceField(
        queryset=Cohort.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(
        self,
        data: Mapping[str, str] | None = None,
        *,
        roles: list[tuple[str, str]],
        cohorts: QuerySet[Cohort],
        preset: Cohort | None = None,
        new_account: bool = False,
        allow_no_role: bool = False,
    ) -> None:
        if preset is not None and isinstance(data, QueryDict):
            data = data.copy()
            data.setlist("cohorts", [str(preset.pk)])
        super().__init__(data)
        if not new_account:
            del self.fields["first_name"]
            del self.fields["last_name"]
        role_field = cast(forms.ChoiceField, self.fields["role"])
        self.allow_no_role = allow_no_role
        if allow_no_role:
            role_field.required = False
            roles = [("", "No roles yet"), *roles]
        role_field.choices = roles
        cohort_field = cast(forms.ModelMultipleChoiceField, self.fields["cohorts"])
        cohort_field.queryset = cohorts
        if preset is not None:
            cohort_field.widget = forms.MultipleHiddenInput()
            cohort_field.initial = [preset.pk]

    def clean(self) -> dict[str, object]:
        cleaned = super().clean() or {}
        if self.allow_no_role and cleaned.get("role") == "":
            cleaned["cohorts"] = Cohort.objects.none()
            return cleaned
        if cleaned.get("role") in ORGANISATION_ROLES:
            cleaned["cohorts"] = Cohort.objects.none()
        elif cleaned.get("role") and not cleaned.get("cohorts"):
            self.add_error("cohorts", "Choose at least one cohort.")
        return cleaned


class ChangeRoleForm(forms.Form):
    """The role a staff member should hold on a cohort instead of the one
    they hold now, among the `roles` offered as (key, display name) pairs."""

    new_role = forms.ChoiceField(widget=forms.RadioSelect, label="Role")

    def __init__(
        self,
        data: Mapping[str, str] | None = None,
        *,
        roles: list[tuple[str, str]],
    ) -> None:
        super().__init__(data)
        cast(forms.ChoiceField, self.fields["new_role"]).choices = roles


class CohortSetForm(forms.Form):
    """The cohorts a role should cover after the change, among the ones
    offered. An empty selection is valid: it means remove the role."""

    cohorts = forms.ModelMultipleChoiceField(
        queryset=Cohort.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )


class EducatorReasonForm(ReasonForm):
    """The reason dialog's form, with the help text that tells an educator who
    sees the reason."""

    reason_help_text = "Only staff can see this. It is shown in the history."
