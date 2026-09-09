import contextlib

from guardian.admin import GuardedModelAdmin
from import_export.admin import ExportActionMixin
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ExportForm

from django.contrib import admin
from django.contrib.admin.exceptions import NotRegistered
from django.contrib.sites.models import Site
from django.http import HttpRequest

from freedom_ls.site_aware_models.admin_exports import FormulaSafeCSV

with contextlib.suppress(NotRegistered):
    admin.site.unregister(Site)


class SiteAwareModelAdmin(ModelAdmin):
    """Base admin class for site-aware models"""

    exclude = ["site"]

    class Media:
        css = {"all": ["site_aware_models/css/admin.css"]}


class SiteAwareExportModelAdmin(ExportActionMixin, SiteAwareModelAdmin):
    """Site-aware admin with a CSV export action and an "Export" changelist button.

    Both download immediately: only one format is offered, so the package's
    intermediate form has nothing to ask. The format is fixed in code rather
    than through ``IMPORT_EXPORT_FORMATS`` so a downstream settings file
    cannot swap in one without formula escaping. Subclasses declare
    ``resource_classes`` with a ``SiteAwareModelResource``.

    The package's default export permission is "any staff user", which would
    let staff with no permission on the model download every row through the
    export URL. Export is gated on view permission instead.

    The detail-page export button is off: it posts to the change view, which
    denies any user without change permission.
    """

    export_form_class = ExportForm
    skip_export_form = True
    skip_export_form_from_action = True
    show_change_form_export = False

    def get_export_formats(self) -> list[type[FormulaSafeCSV]]:
        return [FormulaSafeCSV]

    def has_export_permission(self, request: HttpRequest) -> bool:
        allowed: bool = self.has_view_permission(request)
        return allowed


class GuardedSiteAwareModelAdmin(ModelAdmin, GuardedModelAdmin):
    """Site-aware admin with guardian's object-permission UI.

    Unfold's ModelAdmin first, guardian second, per the combination documented
    in the admin-guardian resource. That resource also warns the pairing is not
    guaranteed by either package, so the object-permissions page is checked by
    hand before anything relies on it.
    """

    exclude = ["site"]
    Media = SiteAwareModelAdmin.Media


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
