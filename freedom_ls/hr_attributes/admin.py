"""Admins for the HR attribute lists and the inlines on learner and organisation."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from unfold.admin import StackedInline

from django import forms
from django.contrib import admin
from django.db import models
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import ngettext

from freedom_ls.hr_attributes.forms import DepartmentForm, JobTitleForm, LocationForm
from freedom_ls.hr_attributes.models import (
    Department,
    JobTitle,
    LearnerHRAttributes,
    Location,
    OrganisationHRSettings,
)
from freedom_ls.learner_management.admin import LearnerAdmin
from freedom_ls.learner_management.models import Learner
from freedom_ls.organisations.admin import OrganisationAdmin
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin


class ListEntryAdmin(SiteAwareModelAdmin):
    """What the three list admins share. Each registered subclass names its form."""

    list_display = ["name", "organisation", "is_active"]
    list_filter = ["organisation", "is_active"]
    search_fields = ["name"]
    list_select_related = ["organisation"]
    autocomplete_fields = ["organisation"]
    # Stock delete stays. PROTECT on the learner side makes it refuse an entry
    # in use and allow an unused one.
    actions = ["deactivate_selected", "activate_selected"]

    @admin.action(description="Deactivate selected entries")
    def deactivate_selected(
        self,
        request: HttpRequest,
        queryset: QuerySet[JobTitle | Department | Location],
    ) -> None:
        count = queryset.update(is_active=False)
        self.message_user(
            request,
            ngettext(
                "%(count)d entry deactivated.", "%(count)d entries deactivated.", count
            )
            % {"count": count},
        )

    @admin.action(description="Activate selected entries")
    def activate_selected(
        self,
        request: HttpRequest,
        queryset: QuerySet[JobTitle | Department | Location],
    ) -> None:
        count = queryset.update(is_active=True)
        self.message_user(
            request,
            ngettext(
                "%(count)d entry activated.", "%(count)d entries activated.", count
            )
            % {"count": count},
        )


@admin.register(JobTitle)
class JobTitleAdmin(ListEntryAdmin):
    form = JobTitleForm


@admin.register(Department)
class DepartmentAdmin(ListEntryAdmin):
    form = DepartmentForm


@admin.register(Location)
class LocationAdmin(ListEntryAdmin):
    form = LocationForm


#: Each picker's model, so the narrowed queryset is built from the field name alone.
_PICKER_MODELS: dict[str, type[JobTitle | Department | Location]] = {
    "job_title": JobTitle,
    "department": Department,
    "location": Location,
}


def _picker_scope(
    learner_id: str | None, field_name: str
) -> tuple[UUID, UUID | None] | None:
    """The edited learner's organisation and the entry they hold in ``field_name``.

    None when the id is absent or not a UUID, which is the add page or a
    hand-edited URL; the picker then offers nothing, and the change view 404s
    moments later anyway. One query covers both values.
    """
    if not learner_id:
        return None
    try:
        pk = UUID(learner_id)
    except ValueError:
        return None
    return (
        Learner.objects.filter(pk=pk)
        .values_list("organisation_id", f"hr_attributes__{field_name}_id")
        .first()
    )


class LearnerHRAttributesInline(StackedInline):
    model = LearnerHRAttributes
    fields = [
        "job_title",
        "department",
        "location",
        "organisation_start_date",
        "job_title_start_date",
        "department_start_date",
        "location_start_date",
    ]
    max_num = 1
    can_delete = False

    def formfield_for_foreignkey(
        self,
        db_field: models.ForeignKey,
        request: HttpRequest,
        **kwargs: object,
    ) -> forms.ModelChoiceField | None:
        # This queryset is both what the plain select offers and what validates
        # the entry that comes back. It is scoped to the learner's stored
        # organisation, not the one posted with the page, so a learner moved to
        # another organisation while holding this one's entries is refused by
        # the model until those entries are cleared. limit_choices_to would
        # also reject a deactivated entry the learner already holds, which
        # for_picker keeps.
        if db_field.name in _PICKER_MODELS and request.resolver_match:
            model = _PICKER_MODELS[db_field.name]
            scope = _picker_scope(
                request.resolver_match.kwargs.get("object_id"), db_field.name
            )
            if scope is None:
                kwargs["queryset"] = model.objects.none()
            else:
                organisation_id, held_pk = scope
                kwargs["queryset"] = model.objects.for_picker(organisation_id, held_pk)
        return cast(
            "forms.ModelChoiceField | None",
            super().formfield_for_foreignkey(db_field, request, **kwargs),
        )


# A learner's HR attributes on their own change page, through the seam
# LearnerAdmin declares for it. The wiring runs from here rather than from
# learner_management, which must stay installable without this app and so
# cannot import LearnerHRAttributesInline. Adding rather than replacing keeps
# every inline another app has already contributed.
LearnerAdmin.inlines = [*LearnerAdmin.inlines, LearnerHRAttributesInline]


class OrganisationHRSettingsInline(StackedInline):
    model = OrganisationHRSettings
    fields = ["registration_rules_enabled"]
    max_num = 1
    can_delete = False


# The organisation's HR settings on its own change page, through the seam
# OrganisationAdmin declares for it. The wiring runs from here rather than
# from organisations, which must stay installable without this app and so
# cannot import OrganisationHRSettingsInline. Adding rather than replacing
# keeps every inline another app has already contributed.
OrganisationAdmin.inlines = [*OrganisationAdmin.inlines, OrganisationHRSettingsInline]
