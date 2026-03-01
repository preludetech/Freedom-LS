import contextlib

from unfold.admin import ModelAdmin

from django.contrib import admin
from django.contrib.sites.models import Site

with contextlib.suppress(admin.sites.NotRegistered):
    admin.site.unregister(Site)


class SiteAwareModelAdmin(ModelAdmin):
    """Base admin class for site-aware models"""

    exclude = ["site"]
