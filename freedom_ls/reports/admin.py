from __future__ import annotations

from functools import partial

from guardian.shortcuts import get_objects_for_user
from unfold.decorators import action as unfold_action

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import URLPattern, path, reverse
from django.utils.html import format_html

from freedom_ls.reports.models import GeneratedReport
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin
from freedom_ls.student_management.models import Cohort


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

    def _visible_cohorts(self, request: HttpRequest) -> QuerySet[Cohort]:
        """Model-level report permissions say nothing about which cohorts a
        user may see; object-level view_cohort is what draws that line.
        Guardian returns everything for a superuser, so they are unaffected.
        """
        return get_objects_for_user(request.user, "view_cohort", klass=Cohort)

    def get_queryset(self, request: HttpRequest) -> QuerySet[GeneratedReport]:
        # select_related here rather than only in list_select_related: the
        # change and delete views look objects up through this queryset and
        # render str(report), which reads the cohort name.
        queryset: QuerySet[GeneratedReport] = super().get_queryset(request)
        return queryset.select_related("cohort").filter(
            cohort__in=self._visible_cohorts(request)
        )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: GeneratedReport | None = None
    ) -> bool:
        return False

    def has_view_permission(
        self, request: HttpRequest, obj: GeneratedReport | None = None
    ) -> bool:
        if not super().has_view_permission(request, obj):
            return False
        # Without an object this is the changelist, already scoped by
        # get_queryset.
        if obj is None:
            return True
        return request.user.has_perm(
            "freedom_ls_student_management.view_cohort", obj.cohort
        )

    # delete stays available -- it is the only cleanup path in v1 -- but it must
    # not become a way to reach or destroy another cohort's reports
    def has_delete_permission(
        self, request: HttpRequest, obj: GeneratedReport | None = None
    ) -> bool:
        if not super().has_delete_permission(request, obj):
            return False
        if obj is None:
            return True
        return request.user.has_perm(
            "freedom_ls_student_management.view_cohort", obj.cohort
        )

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
                self.admin_site.admin_view(
                    partial(generate_report_view, model_admin=self)
                ),
                name="freedom_ls_reports_generatedreport_generate",
            ),
            path(
                "<path:object_id>/download/",
                self.admin_site.admin_view(download_report_view),
                name="freedom_ls_reports_generatedreport_download",
            ),
        ]
        return custom_urls + list(super().get_urls())
