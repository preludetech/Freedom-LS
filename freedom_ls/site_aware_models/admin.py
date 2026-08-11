import contextlib

from guardian.admin import GuardedModelAdmin
from unfold.admin import ModelAdmin

from django.contrib import admin
from django.contrib.admin.exceptions import NotRegistered
from django.contrib.sites.models import Site

with contextlib.suppress(NotRegistered):
    admin.site.unregister(Site)


class SiteAwareModelAdmin(ModelAdmin):
    """Base admin class for site-aware models"""

    exclude = ["site"]


class GuardedSiteAwareModelAdmin(ModelAdmin, GuardedModelAdmin):
    """Site-aware admin with guardian's object-permission UI.

    Unfold's ModelAdmin first, guardian second, per the combination documented
    in the admin-guardian resource. That resource also warns the pairing is not
    guaranteed by either package, so the object-permissions page is checked by
    hand before anything relies on it.
    """

    exclude = ["site"]
