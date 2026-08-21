from __future__ import annotations

from functools import partial

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
from freedom_ls.student_management.queries import (
    all_cohorts_visible_to,
    can_view_cohort,
)


@admin.register(GeneratedReport)
class GeneratedReportAdmin(SiteAwareModelAdmin):
    list_display = [
        "organisation",
        "cohort",
        "status",
        "requested_by",
        "requested_at",
        "finished_at",
        "download",
    ]
    list_select_related = ["cohort__organisation", "requested_by"]
    list_filter = ["status", "requested_at", "cohort__organisation"]
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
        user may see; cohort visibility is what draws that line, by either a
        per-cohort guardian grant or a role on the cohort's organisation.
        Guardian returns everything for a superuser, so they are unaffected.

        The organisation-unscoped helper, because the admin is site-wide and
        has no organisation in scope to pass the narrower one.
        """
        return all_cohorts_visible_to(request.user)

    def get_queryset(self, request: HttpRequest) -> QuerySet[GeneratedReport]:
        # select_related here rather than only in list_select_related: the
        # change and delete views look objects up through this queryset and
        # render str(report), which reads the cohort name.
        queryset: QuerySet[GeneratedReport] = super().get_queryset(request)
        return queryset.select_related("cohort__organisation").filter(
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
        return can_view_cohort(request.user, obj.cohort)

    # delete stays available -- it is the only cleanup path in v1 -- but it must
    # not become a way to reach or destroy another cohort's reports
    def has_delete_permission(
        self, request: HttpRequest, obj: GeneratedReport | None = None
    ) -> bool:
        if not super().has_delete_permission(request, obj):
            return False
        if obj is None:
            return True
        return can_view_cohort(request.user, obj.cohort)

    @admin.display(description="Organisation", ordering="cohort__organisation__name")
    def organisation(self, obj: GeneratedReport) -> str:
        return obj.cohort.organisation.name

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
