from django.contrib import admin

from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin

from .models import CourseFormAttempt, CourseProgress, TopicProgress


@admin.register(TopicProgress)
class TopicProgressAdmin(SiteAwareModelAdmin):
    list_display = [
        "course_progress",
        "collection_item",
        "topic",
        "start_time",
        "last_accessed_time",
        "complete_time",
        "is_complete",
    ]
    list_filter = ("complete_time", "topic", "start_time")
    search_fields = ("course_progress__learner__user__email", "topic__title")
    ordering = ("-last_accessed_time",)
    readonly_fields = ("start_time", "last_accessed_time")
    autocomplete_fields = ["course_progress", "collection_item", "topic"]
    list_select_related = (
        "course_progress__learner__user",
        "collection_item",
        "topic",
    )

    fieldsets = (
        (None, {"fields": ("course_progress", "collection_item", "topic")}),
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
        "learner",
        "course",
        "learner_registration",
        "cohort_registration",
        "created_at",
        "started_at",
        "completed_time",
        "is_complete",
    ]
    list_filter = ("completed_time", "course", "created_at")
    search_fields = ("learner__user__email", "course__title")
    ordering = ("-created_at",)
    # created_at is auto_now_add; last_accessed_time is written by the player,
    # so editing either by hand would only ever misreport what happened.
    readonly_fields = ("created_at", "last_accessed_time")
    autocomplete_fields = [
        "learner",
        "course",
        "learner_registration",
        "cohort_registration",
        "last_accessed_item",
    ]
    list_select_related = (
        "learner__user",
        "course",
        "learner_registration__course",
        "cohort_registration__cohort",
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "learner",
                    "course",
                    "learner_registration",
                    "cohort_registration",
                )
            },
        ),
        (
            "Progress",
            {
                "fields": (
                    "created_at",
                    "started_at",
                    "last_accessed_time",
                    "last_accessed_item",
                    "completed_time",
                    "progress_percentage",
                )
            },
        ),
    )

    @admin.display(boolean=True, description="Complete")
    def is_complete(self, obj):
        return obj.completed_time is not None


@admin.register(CourseFormAttempt)
class CourseFormAttemptAdmin(SiteAwareModelAdmin):
    """The course side of an attempt. The attempt itself is edited in form_engine."""

    # `form` and `start_time` would shadow ModelAdmin.form and the attempt's own
    # field names, so the display callables carry their own names.
    list_display = [
        "course_progress",
        "collection_item",
        "form_title",
        "started_at",
        "finished_at",
        "is_complete",
    ]
    list_filter = ("form_progress__completed_time", "form_progress__start_time")
    search_fields = (
        "course_progress__learner__user__email",
        "form_progress__form__title",
    )
    ordering = ("-form_progress__start_time",)
    autocomplete_fields = ["course_progress", "collection_item", "form_progress"]
    # Each row renders its record, its learner and the attempt's form, so the
    # changelist would otherwise issue three queries per row.
    list_select_related = (
        "course_progress__learner__user",
        "collection_item",
        "form_progress__form",
    )

    @admin.display(description="Form")
    def form_title(self, obj):
        return obj.form_progress.form

    @admin.display(description="Started")
    def started_at(self, obj):
        return obj.form_progress.start_time

    @admin.display(description="Completed")
    def finished_at(self, obj):
        return obj.form_progress.completed_time

    @admin.display(boolean=True, description="Complete")
    def is_complete(self, obj):
        return obj.form_progress.completed_time is not None
