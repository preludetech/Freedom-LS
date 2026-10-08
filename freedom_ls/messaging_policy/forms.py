from __future__ import annotations

from typing import cast

from django import forms
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError

from freedom_ls.learner_management.capabilities import roles_granting
from freedom_ls.learner_management.queries import VIEW_LEARNER
from freedom_ls.messaging_policy.models import FLAG_NAMES, SiteMessagingConfig
from freedom_ls.role_based_permissions.loader import get_role_config
from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin

USE_SETTINGS_DEFAULT = "__settings_default__"


def offered_role_choices(site: Site) -> list[tuple[str, str]]:
    """The settings-default option first, then every role on this site that grants
    VIEW_LEARNER, labelled by its display name."""
    role_config = get_role_config(site.name)
    return [
        (USE_SETTINGS_DEFAULT, "Use the settings default"),
        *(
            (key, role_config[key].display_name)
            for key in sorted(roles_granting(VIEW_LEARNER, site))
        ),
    ]


class OfferedEducatorRolesField(forms.MultipleChoiceField):
    """Checkboxes stored as a JSON list, with "use the settings default" (stored
    as None) kept distinct from an empty selection (stored as [])."""

    widget = forms.CheckboxSelectMultiple

    def clean(self, value: object) -> list[str] | None:
        chosen: list[str] = super().clean(value)
        if USE_SETTINGS_DEFAULT not in chosen:
            return chosen
        if len(chosen) > 1:
            raise ValidationError(
                "Choose either the settings default or specific roles, not both."
            )
        return None


class SiteMessagingConfigForm(ConstraintValidationFormMixin):
    """Admin form for SiteMessagingConfig.

    ``site`` is un-excluded from validation so unique_messaging_config_per_site
    is checked while cleaning rather than failing at the database. It is still
    never rendered.
    """

    # The admin binds this per request; a class-level choice list would be shared
    # between sites.
    site: Site | None = None
    offered_educator_roles = OfferedEducatorRolesField(required=False, choices=())

    class Meta:
        model = SiteMessagingConfig
        fields = [*FLAG_NAMES, "offered_educator_roles"]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        site = self.site or (self.instance.site if self.instance.site_id else None)
        # self.fields is this form's own copy; base_fields is shared process-wide.
        roles_field = cast(
            OfferedEducatorRolesField, self.fields["offered_educator_roles"]
        )
        roles_field.choices = offered_role_choices(site) if site else []
        if self.instance.offered_educator_roles is None:
            self.initial["offered_educator_roles"] = [USE_SETTINGS_DEFAULT]
