from __future__ import annotations

from django.contrib import admin

from freedom_ls.messaging_policy.forms import SiteMessagingConfigForm
from freedom_ls.messaging_policy.models import FLAG_NAMES, SiteMessagingConfig
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin


@admin.register(SiteMessagingConfig)
class SiteMessagingConfigAdmin(SiteAwareModelAdmin):
    form = SiteMessagingConfigForm
    list_display = ["__str__", *FLAG_NAMES]
    list_filter = list(FLAG_NAMES)
