from django.contrib import admin
from django.contrib.sites.models import Site
from unfold.admin import ModelAdmin

try:
    admin.site.unregister(Site)
except admin.sites.NotRegistered:
    pass


class SiteAwareModelAdmin(ModelAdmin):
    """Base admin class for site-aware models"""

    exclude = ["site"]
