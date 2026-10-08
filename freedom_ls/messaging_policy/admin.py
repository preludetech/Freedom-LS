from __future__ import annotations

from django.contrib import admin

from freedom_ls.messaging_policy.forms import SiteMessagingConfigForm
from freedom_ls.messaging_policy.models import (
    FLAG_NAMES,
    CohortMessagingConfig,
    OrganisationMessagingConfig,
    SiteMessagingConfig,
)
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin


@admin.register(SiteMessagingConfig)
class SiteMessagingConfigAdmin(SiteAwareModelAdmin):
    form = SiteMessagingConfigForm
    list_display = ["__str__", *FLAG_NAMES]
    list_filter = list(FLAG_NAMES)


@admin.register(OrganisationMessagingConfig)
class OrganisationMessagingConfigAdmin(SiteAwareModelAdmin):
    list_display = ["__str__", *FLAG_NAMES]
    list_filter = list(FLAG_NAMES)
    autocomplete_fields = ["organisation"]
    search_fields = ["organisation__name"]


@admin.register(CohortMessagingConfig)
class CohortMessagingConfigAdmin(SiteAwareModelAdmin):
    list_display = ["__str__", *FLAG_NAMES]
    list_filter = list(FLAG_NAMES)
    autocomplete_fields = ["cohort"]
    search_fields = ["cohort__name"]
