"""Forms for the organisations admin."""

from __future__ import annotations

from collections.abc import Mapping

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.utils.datastructures import MultiValueDict

from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin

from .models import LOGO_FIELD_NAMES, Organisation

INVALID_IMAGE_MESSAGE = "File is not a readable image. Use PNG, JPEG or WebP."


class LineBreakNormalisingTextarea(forms.Textarea):
    """A textarea whose submitted value uses ``\\n`` for every line break.

    Browsers submit each break as ``\\r\\n``, which would count as two characters
    against a field's ``max_length`` while the browser counts one.
    """

    def value_from_datadict(
        self,
        data: Mapping[str, object],
        files: MultiValueDict[str, UploadedFile],
        name: str,
    ) -> str | None:
        value = super().value_from_datadict(data, files, name)
        if not isinstance(value, str):
            return None
        return value.replace("\r\n", "\n").replace("\r", "\n")


class OrganisationAdminForm(ConstraintValidationFormMixin):
    """Admin form for Organisation.

    ``site`` is un-excluded so ``unique_organisation_name_per_site`` is checked
    while cleaning. ``slug`` is deliberately left out: it is read-only in the
    admin and assigned by ``OrganisationAdmin.save_model``, which already
    de-duplicates it, so validating ``unique_organisation_slug_per_site`` here
    would reject names the admin is able to accommodate.
    """

    constraint_fields = ("site",)

    class Meta:
        model = Organisation
        fields = ["name", "logo", "logo_on_dark", "profile_logo", "bio"]
        widgets = {"bio": LineBreakNormalisingTextarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for field_name in LOGO_FIELD_NAMES:
            field = self.fields.get(field_name)
            if field is not None:
                # ImageField.to_python rejects a non-image before the model's
                # own validators run, so this is the only place the allowed
                # formats can be named for that case.
                field.error_messages["invalid_image"] = INVALID_IMAGE_MESSAGE
