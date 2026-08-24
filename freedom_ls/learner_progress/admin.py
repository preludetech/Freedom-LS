from django.contrib import admin

from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin

from .models import CourseProgress, TopicProgress


@admin.register(TopicProgress)
class TopicProgressAdmin(SiteAwareModelAdmin):
    list_display = [
        "user",
        "topic",
        "start_time",
        "last_accessed_time",
        "complete_time",
        "is_complete",
    ]
    list_filter = ("complete_time", "topic", "start_time")
    search_fields = ("user__email", "topic__title")
    ordering = ("-last_accessed_time",)
    readonly_fields = ("start_time", "last_accessed_time")

    fieldsets = (
        (None, {"fields": ("user", "topic")}),
        (
            "Progress",
            {"fields": ("start_time", "last_accessed_time", "complete_time")},
        ),
    )

    @admin.display(boolean=True, description="Complete")
    def is_complete(self, obj):
        return obj.complete_time is not None


@admin.register(CourseProgress)
class CourseProgressAdmin(SiteAwareModelAdmin):
    list_display = [
        "user",
        "course",
        "start_time",
        "last_accessed_time",
        "completed_time",
        "is_complete",
    ]
    list_filter = ("completed_time", "course", "start_time")
    search_fields = ("user__email", "course__title")
    ordering = ("-last_accessed_time",)
    readonly_fields = ("start_time", "last_accessed_time")

    fieldsets = (
        (None, {"fields": ("user", "course")}),
        (
            "Progress",
            {"fields": ("start_time", "last_accessed_time", "completed_time")},
        ),
    )

    @admin.display(boolean=True, description="Complete")
    def is_complete(self, obj):
        return obj.completed_time is not None
