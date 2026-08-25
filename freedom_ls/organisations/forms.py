"""Forms for the organisations admin."""

from __future__ import annotations

from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin

from .models import Organisation

INVALID_IMAGE_MESSAGE = "File is not a readable image. Use PNG, JPEG or WebP."


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
        fields = ["name", "logo", "logo_on_dark"]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for field_name in ("logo", "logo_on_dark"):
            field = self.fields.get(field_name)
            if field is not None:
                # ImageField.to_python rejects a non-image before the model's
                # own validators run, so this is the only place the allowed
                # formats can be named for that case.
                field.error_messages["invalid_image"] = INVALID_IMAGE_MESSAGE
