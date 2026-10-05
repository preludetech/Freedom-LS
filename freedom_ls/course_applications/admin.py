"""Admin for course applications."""

from __future__ import annotations

from datetime import datetime

from unfold.contrib.filters.admin import AutocompleteSelectFilter

from django.contrib import admin
from django.db.models import Q, QuerySet
from django.http import HttpRequest, HttpResponse

from freedom_ls.accounts.admin import USER_ERASURE_CASCADE_MODELS
from freedom_ls.form_engine.admin import answers_context
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin, admin_change_link
from freedom_ls.site_aware_models.admin_filters import InclusiveRangeDateTimeFilter

from .models import CourseApplication

# The admin below denies delete so nobody can thin out applications one by one.
# Erasing the applicant is the one path that must take them along, and the User
# admin only vouches for the models named here.
USER_ERASURE_CASCADE_MODELS.add(CourseApplication)


class CourseApplicationSubmittedFilter(admin.SimpleListFilter):
    """Submitted or draft, by the same rule as CourseApplication.is_submitted.

    An application with no sitting was submitted the moment it was created, so
    "submitted" is an OR over two shapes and the shared completion filter, which
    tests one timestamp, cannot express it.
    """

    title = "submitted"
    parameter_name = "submitted"

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin
    ) -> list[tuple[str, str]]:
        return [("submitted", "Submitted"), ("draft", "Draft")]

    def queryset(
        self, request: HttpRequest, queryset: QuerySet[CourseApplication]
    ) -> QuerySet[CourseApplication]:
        if self.value() == "submitted":
            return queryset.filter(
                Q(form_progress__isnull=True)
                | Q(form_progress__completed_time__isnull=False)
            )
        if self.value() == "draft":
            return queryset.filter(
                form_progress__isnull=False, form_progress__completed_time__isnull=True
            )
        return queryset


@admin.register(CourseApplication)
class CourseApplicationAdmin(SiteAwareModelAdmin):
    """Find an application and read it. Nothing here writes.

    Applications are created only by the apply flow, which also creates the
    sitting; re-pointing the user, course or sitting from here would break the
    rule that the sitting is the applicant's own sitting of that course's form,
    and deleting one would leave its sitting and files with no owner.
    """

    list_display = [
        "applicant_email",
        "applicant_name",
        "course",
        "is_submitted",
        "submitted_time",
        "created_at",
    ]
    # Every column reads one of these relations; without them the changelist
    # queries once per row.
    list_select_related = ["user", "course", "form_progress"]
    ordering = ["-created_at"]
    list_filter = [
        CourseApplicationSubmittedFilter,
        ("course", AutocompleteSelectFilter),
        ("created_at", InclusiveRangeDateTimeFilter),
    ]
    # Filters apply on Submit, so a created-date range goes through as a pair of
    # dates rather than refreshing the list after each box.
    list_filter_submit = True
    search_fields = [
        "user__email",
        "user__first_name",
        "user__last_name",
        "course__title",
    ]
    fields = ["is_submitted", "submitted_time", "created_at"]
    readonly_fields = fields
    change_form_template = "admin/form_engine/answers_change_form.html"

    def get_queryset(self, request: HttpRequest) -> QuerySet[CourseApplication]:
        queryset: QuerySet[CourseApplication] = (
            super()
            .get_queryset(request)
            .select_related("user", "course", "form_progress")
        )
        return queryset

    def render_change_form(
        self,
        request: HttpRequest,
        context: dict[str, object],
        add: bool = False,
        change: bool = False,
        form_url: str = "",
        obj: CourseApplication | None = None,
    ) -> HttpResponse:
        if obj is not None:
            form_progress = obj.form_progress
            context["summary_rows"] = [
                ("Applicant", admin_change_link(request, obj.user)),
                ("Course", admin_change_link(request, obj.course)),
                (
                    "Form progress record",
                    admin_change_link(request, form_progress)
                    if form_progress is not None
                    else "The course asked for no application form.",
                ),
            ]
            if form_progress is not None:
                context.update(answers_context(request, form_progress))
        response: HttpResponse = super().render_change_form(
            request, context, add, change, form_url, obj
        )
        return response

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: CourseApplication | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: CourseApplication | None = None
    ) -> bool:
        return False

    @admin.display(description="Applicant", ordering="user__email")
    def applicant_email(self, obj: CourseApplication) -> str:
        return obj.user.email

    @admin.display(description="Applicant name", ordering="user__last_name")
    def applicant_name(self, obj: CourseApplication) -> str:
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

    @admin.display(boolean=True, description="Submitted")
    def is_submitted(self, obj: CourseApplication) -> bool:
        return obj.is_submitted

    @admin.display(description="Submitted time")
    def submitted_time(self, obj: CourseApplication) -> datetime | None:
        # An application with no sitting was submitted the moment it was created.
        if obj.form_progress is None:
            return obj.created_at
        return obj.form_progress.completed_time
