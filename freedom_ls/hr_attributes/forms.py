"""Admin form for the three HR attribute lists."""

from __future__ import annotations

from django import forms
from django.db.models import Value
from django.db.models.functions import Lower, Trim

from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin


class ListEntryForm(ConstraintValidationFormMixin):
    """Report a duplicate name on the ``name`` field.

    The database constraint compares ``Lower(Trim("name"))`` within the
    organisation. ConstraintValidationFormMixin can only put an expression
    constraint's error among the non-field errors, because it names no field
    to attach it to, and skips the constraint altogether once ``organisation``
    is read-only. Checking here first puts a plain message on the one field a
    person can change.

    It has no ``Meta.model``: the admin builds one form per list with
    ``modelform_factory``. ``organisation`` must come before ``name`` in the
    fields, so it is already cleaned when this runs. When it is not rendered
    the entry's stored organisation is used.
    """

    def clean_name(self) -> str:
        name: str = self.cleaned_data["name"].strip()
        if "organisation" in self.fields:
            organisation = self.cleaned_data.get("organisation")
            if organisation is None:
                return name
            organisation_id = organisation.pk
        else:
            organisation_id = self.instance.organisation_id
        duplicates = (
            type(self.instance)
            ._default_manager.filter(organisation_id=organisation_id)
            .alias(normalised_name=Lower(Trim("name")))
            .filter(normalised_name=Lower(Value(name)))
            .exclude(pk=self.instance.pk)
        )
        if duplicates.exists():
            raise forms.ValidationError(
                "An entry with this name already exists in this organisation."
            )
        return name
