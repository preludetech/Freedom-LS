from collections.abc import Callable

from django.contrib import admin
from django.contrib.admin.options import InlineModelAdmin
from django.contrib.sites.models import Site
from django.http import HttpRequest
from django.utils.html import format_html_join

from freedom_ls.site_aware_models.admin import GuardedSiteAwareModelAdmin
from freedom_ls.site_aware_models.models import get_cached_site
from freedom_ls.site_aware_models.slugs import get_unique_slug, slug_base_for

from .forms import OrganisationAdminForm
from .models import Organisation

#: Read-only summaries other apps add to the Organisation change page. Each one
#: takes the organisation and returns a row of HTML.
#:
#: This and ``OrganisationAdmin.inlines`` are the two seams an app uses to put
#: an organisation's own objects on its page. The wiring can only run in that
#: direction: ``organisations`` sits below every app that owns such objects
#: (docs/app_structure.md) and must stay installable without them, so it cannot
#: import their models. Both are read on every request, so an app appending from
#: its own admin module at import time reaches the registered admin.
ORGANISATION_SUMMARIES: list[Callable[[Organisation], str]] = []

SUMMARIES_FIELD = "contributed_summaries"


@admin.register(Organisation)
class OrganisationAdmin(GuardedSiteAwareModelAdmin):
    form = OrganisationAdminForm
    list_display = ["name", "slug"]
    search_fields = ["name"]
    readonly_fields = ["slug", SUMMARIES_FIELD]
    fields = ["name", "slug", "logo", "logo_on_dark", SUMMARIES_FIELD]
    # Appended to by other apps, for the reason given on ORGANISATION_SUMMARIES.
    # Declared here rather than inherited so a contributor never mutates the
    # list shared with every other ModelAdmin.
    inlines = []

    @admin.display(description="Related")
    def contributed_summaries(self, obj: Organisation) -> str:
        # One block per summary, rather than a separator: a separator would
        # have to be marked safe, and there is nothing here worth reaching for
        # mark_safe over. Each summary escapes its own content already.
        return format_html_join(
            "",
            "<div>{}</div>",
            ((summary(obj),) for summary in ORGANISATION_SUMMARIES),
        )

    def get_inlines(
        self, request: HttpRequest, obj: Organisation | None = None
    ) -> list[type[InlineModelAdmin]]:
        """The contributed inlines, on the change page only.

        They all list things belonging to an organisation, and the add page has
        no organisation yet to list them for. Leaving them on would also make
        the create form refuse any submission not carrying their management
        forms.
        """
        return list(super().get_inlines(request, obj)) if obj is not None else []

    def get_fields(
        self, request: HttpRequest, obj: Organisation | None = None
    ) -> list[str | list[str] | tuple[str, ...]]:
        """Drop the summaries row unless there is something to put in it.

        Nothing to summarise on the add page, for the same reason as
        `get_inlines`, and nothing at all when no app has contributed a summary.
        """
        fields = list(super().get_fields(request, obj))
        if obj is not None and ORGANISATION_SUMMARIES:
            return fields
        return [field for field in fields if field != SUMMARIES_FIELD]

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
                    slug_base_for(obj.name),
                    existing_uuid=str(obj.pk),
                )
        super().save_model(request, obj, form, change)
