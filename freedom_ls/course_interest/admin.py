from django.contrib import admin

from freedom_ls.course_interest.models import CourseInterest
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin


@admin.register(CourseInterest)
class CourseInterestAdmin(SiteAwareModelAdmin):
    """Read surface for expressed course interest. No actions -- the
    educator-facing panel this replaces was drill-down only."""

    list_display = ["user", "course", "created_at"]
    list_select_related = ["user", "course"]
    list_filter = ["course", "created_at"]
    search_fields = [
        "user__email",
        "user__first_name",
        "user__last_name",
        "course__title",
    ]
    autocomplete_fields = ["user", "course"]
    readonly_fields = ["created_at"]
