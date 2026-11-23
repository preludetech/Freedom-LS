"""Admins for the HR attribute lists and the inlines on learner and organisation."""

from __future__ import annotations

from typing import cast

from unfold.admin import StackedInline

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import ngettext

from freedom_ls.hr_attributes.forms import ListEntryForm
from freedom_ls.hr_attributes.models import (
    Department,
    JobTitle,
    Location,
    OrganisationHRSettings,
)
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
