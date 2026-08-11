from django.contrib import admin
from django.contrib.sites.models import Site
from django.http import HttpRequest
from django.utils.text import slugify

from freedom_ls.site_aware_models.admin import GuardedSiteAwareModelAdmin
from freedom_ls.site_aware_models.models import get_cached_site
from freedom_ls.site_aware_models.slugs import get_unique_slug

from .models import Organisation


@admin.register(Organisation)
class OrganisationAdmin(GuardedSiteAwareModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name"]
    readonly_fields = ["slug"]
    fields = ["name", "slug", "logo"]

    def has_delete_permission(
        self, request: HttpRequest, obj: Organisation | None = None
    ) -> bool:
        return False

    def save_model(
        self, request: HttpRequest, obj: Organisation, form: object, change: bool
    ) -> None:
        if not obj.slug:
            # get_cached_site can return a RequestSite fallback, but only when
            # django.contrib.sites is uninstalled, which never happens here.
            site = get_cached_site(request)
            if isinstance(site, Site):
                obj.slug = get_unique_slug(
                    Organisation,
                    site,
                    slugify(obj.name),
                    existing_uuid=str(obj.pk),
                )
        super().save_model(request, obj, form, change)
