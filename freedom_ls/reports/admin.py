from __future__ import annotations

from unfold.decorators import action as unfold_action

from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import URLPattern, path, reverse
from django.utils.html import format_html

from freedom_ls.reports.models import GeneratedReport
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin


@admin.register(GeneratedReport)
class GeneratedReportAdmin(SiteAwareModelAdmin):
    list_display = [
        "cohort",
        "status",
        "requested_by",
        "requested_at",
        "finished_at",
        "download",
    ]
    list_select_related = ["cohort", "requested_by"]
    list_filter = ["status", "requested_at"]
    readonly_fields = [
        "cohort",
        "requested_by",
        "status",
        "requested_at",
        "started_at",
        "finished_at",
        "error_message",
    ]
    actions_list = ["generate_report_action"]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: GeneratedReport | None = None
    ) -> bool:
        return False

    # delete stays available -- it is the only cleanup path in v1

    @admin.display(description="Download")
    def download(self, obj: GeneratedReport) -> str:
        if obj.status != GeneratedReport.STATUS_READY:
            return ""
        url = reverse(
            "admin:freedom_ls_reports_generatedreport_download", args=[obj.pk]
        )
        return format_html('<a href="{}">Download</a>', url)

    @unfold_action(description="Generate cohort report")
    def generate_report_action(self, request: HttpRequest) -> HttpResponse:
        return redirect(reverse("admin:freedom_ls_reports_generatedreport_generate"))

    def get_urls(self) -> list[URLPattern]:
        from freedom_ls.reports.views import download_report_view, generate_report_view

        # Must precede super().get_urls(): the admin's own
        # "<path:object_id>/change/" pattern would otherwise swallow
        # "generate/".
        custom_urls = [
            path(
                "generate/",
                self.admin_site.admin_view(generate_report_view),
                name="freedom_ls_reports_generatedreport_generate",
            ),
            path(
                "<path:object_id>/download/",
                self.admin_site.admin_view(download_report_view),
                name="freedom_ls_reports_generatedreport_download",
            ),
        ]
        return custom_urls + list(super().get_urls())
