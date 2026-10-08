"""Admins for the three HR attribute lists."""

from __future__ import annotations

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import ngettext

from freedom_ls.hr_attributes.forms import DepartmentForm, JobTitleForm, LocationForm
from freedom_ls.hr_attributes.models import Department, JobTitle, Location
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
