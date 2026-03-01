import contextlib

from unfold.admin import ModelAdmin

from django.contrib import admin
from django.contrib.admin.exceptions import NotRegistered
from django.contrib.sites.models import Site

with contextlib.suppress(NotRegistered):
    admin.site.unregister(Site)


class SiteAwareModelAdmin(ModelAdmin):
    """Base admin class for site-aware models"""

    exclude = ["site"]
