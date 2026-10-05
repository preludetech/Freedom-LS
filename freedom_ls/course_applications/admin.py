"""Admin for course applications."""

from __future__ import annotations

from datetime import datetime

from django.contrib import admin
from django.http import HttpRequest

from freedom_ls.accounts.admin import USER_ERASURE_CASCADE_MODELS
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin

from .models import CourseApplication

# The admin below denies delete so nobody can thin out applications one by one.
# Erasing the applicant is the one path that must take them along, and the User
# admin only vouches for the models named here.
USER_ERASURE_CASCADE_MODELS.add(CourseApplication)


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
    fields = ["is_submitted", "submitted_time", "created_at"]
    readonly_fields = fields

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
