import contextlib

from guardian.admin import GuardedModelAdmin
from unfold.admin import ModelAdmin

from django.contrib import admin
from django.contrib.admin.exceptions import NotRegistered
from django.contrib.sites.models import Site
from django.http import HttpRequest

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


def admin_page_context(
    request: HttpRequest, model_admin: ModelAdmin, title: str
) -> dict[str, object]:
    """Context a custom admin page needs to render inside the admin shell.

    `each_context` is what supplies the sidebar, theme colours and branding;
    `model_admin` is what the admin header turns into a breadcrumb trail back
    to the model's changelist. A hand-rolled context dict loses both.
    """
    return {
        **model_admin.admin_site.each_context(request),
        "model_admin": model_admin,
        "title": title,
    }
