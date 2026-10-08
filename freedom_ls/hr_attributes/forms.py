"""Admin forms for the three HR attribute lists."""

from __future__ import annotations

from django import forms
from django.db.models import Value
from django.db.models.functions import Lower, Trim

from freedom_ls.hr_attributes.models import Department, JobTitle, Location
from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin


class ListEntryFormMixin(forms.ModelForm):
    """Report a duplicate name on the ``name`` field.

    The database constraint compares ``Lower(Trim("name"))`` within the
    organisation. ConstraintValidationFormMixin can only put an expression
    constraint's error among the non-field errors, because it names no field
    to attach it to. Checking here first puts a plain message on the one field
    a person can change. ``organisation`` is declared before ``name`` on every
    form using this mixin, so it is already cleaned when this runs.
    """

    def clean_name(self) -> str:
        name: str = self.cleaned_data["name"].strip()
        organisation = self.cleaned_data.get("organisation")
        if organisation is None:
            return name
        duplicates = (
            type(self.instance)
            ._default_manager.filter(organisation=organisation)
            .alias(normalised_name=Lower(Trim("name")))
            .filter(normalised_name=Lower(Value(name)))
            .exclude(pk=self.instance.pk)
        )
        if duplicates.exists():
            raise forms.ValidationError(
                "An entry with this name already exists in this organisation."
            )
        return name


class JobTitleForm(ConstraintValidationFormMixin, ListEntryFormMixin):
    class Meta:
        model = JobTitle
        fields = ["organisation", "name", "is_active"]


class DepartmentForm(ConstraintValidationFormMixin, ListEntryFormMixin):
    class Meta:
        model = Department
        fields = ["organisation", "name", "is_active"]


class LocationForm(ConstraintValidationFormMixin, ListEntryFormMixin):
    class Meta:
        model = Location
        fields = ["organisation", "name", "is_active"]
