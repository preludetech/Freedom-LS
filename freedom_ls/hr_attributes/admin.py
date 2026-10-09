"""Admins for the HR attribute lists and the inlines on learner and organisation."""

from __future__ import annotations

from typing import cast

from unfold.admin import StackedInline

from django import forms
from django.contrib import admin
from django.db import models
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import ngettext

from freedom_ls.hr_attributes.forms import ListEntryForm
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


@admin.register(JobTitle, Department, Location)
class ListEntryAdmin(SiteAwareModelAdmin):
    """One admin for all three lists; ModelAdmin builds each list's form from ListEntryForm."""

    form = ListEntryForm
    # organisation first, so ListEntryForm.clean_name can read it.
    fields = ["organisation", "name", "is_active"]
    list_display = ["name", "organisation", "is_active"]
    list_filter = ["organisation", "is_active"]
    search_fields = ["name"]
    list_select_related = ["organisation"]
    autocomplete_fields = ["organisation"]
    # Stock delete stays. PROTECT on the learner side makes it refuse an entry
    # in use and allow an unused one.
    actions = ["deactivate_selected", "activate_selected"]

    def get_readonly_fields(
        self, request: HttpRequest, obj: JobTitle | Department | Location | None = None
    ) -> list[str] | tuple[str, ...]:
        # Learners may hold the entry, and LearnerHRAttributes.clean() only
        # holds an entry to the learner's organisation when that row is saved.
        # An entry made in the wrong organisation is deleted and made again.
        readonly = cast(
            "list[str] | tuple[str, ...]", super().get_readonly_fields(request, obj)
        )
        return readonly if obj is None else [*readonly, "organisation"]

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


#: Each picker's model, so the narrowed queryset is built from the field name alone.
_PICKER_MODELS: dict[str, type[JobTitle | Department | Location]] = {
    "job_title": JobTitle,
    "department": Department,
    "location": Location,
}


def _picker_querysets(
    learner: Learner | None,
) -> dict[str, QuerySet[JobTitle | Department | Location]]:
    """What each picker offers the learner being edited, from one query.

    Each queryset is both what the plain select offers and what validates the
    entry that comes back. It is scoped to the learner's stored organisation,
    read afresh because the posted form has already changed the instance, so a
    learner moved to another organisation while holding this one's entries is
    refused by the model until those entries are cleared. limit_choices_to
    would also reject a deactivated entry the learner already holds, which
    for_picker keeps. The add page has no learner and offers nothing.
    """
    stored = (
        Learner.objects.filter(pk=learner.pk)
        .values_list(
            "organisation_id",
            *(f"hr_attributes__{field_name}_id" for field_name in _PICKER_MODELS),
        )
        .first()
        if learner is not None
        else None
    )
    if stored is None:
        return {name: model.objects.none() for name, model in _PICKER_MODELS.items()}
    organisation_id, *held_pks = stored
    return {
        name: model.objects.for_picker(organisation_id, held_pk)
        for (name, model), held_pk in zip(_PICKER_MODELS.items(), held_pks, strict=True)
    }


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

    # Set by get_formset for the learner being edited, before the form's
    # fields are built. The admin makes a fresh inline per request.
    _picker_querysets: dict[str, QuerySet[JobTitle | Department | Location]]

    def get_formset(
        self,
        request: HttpRequest,
        obj: Learner | None = None,
        **kwargs: object,
    ) -> type[forms.BaseInlineFormSet]:
        self._picker_querysets = _picker_querysets(obj)
        return cast(
            "type[forms.BaseInlineFormSet]",
            super().get_formset(request, obj, **kwargs),
        )

    def formfield_for_foreignkey(
        self,
        db_field: models.ForeignKey,
        request: HttpRequest,
        **kwargs: object,
    ) -> forms.ModelChoiceField | None:
        if db_field.name in _PICKER_MODELS:
            kwargs["queryset"] = self._picker_querysets[db_field.name]
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
