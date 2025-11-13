from django.contrib import admin
from django.contrib.sites.models import Site
from unfold.admin import ModelAdmin

admin.site.unregister(Site)


class SiteAwareModelAdmin(ModelAdmin):
    """Base admin class for site-aware models"""
    exclude = ["site_id"]
