from django.contrib import admin
from .models import FormProgress, QuestionAnswer, TopicProgress


class QuestionAnswerInline(admin.TabularInline):
    """Inline for question answers."""

    model = QuestionAnswer
    extra = 0
    fields = ("question", "selected_options", "text_answer", "last_updated_time")
    readonly_fields = ("last_updated_time",)


@admin.register(FormProgress)
class FormProgressAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "form",
        "start_time",
        "last_updated_time",
        "completed_time",
        "is_complete",
    )
    list_filter = ("completed_time", "form", "start_time")
    search_fields = ("user__email", "form__title")
    ordering = ("-start_time",)
    readonly_fields = ("start_time", "last_updated_time", "scores")
    inlines = [QuestionAnswerInline]
    exclude = ("site",)
    fieldsets = (
        (None, {"fields": ("user", "form")}),
        (
            "Progress",
            {
                "fields": (
                    "start_time",
                    "last_updated_time",
                    "completed_time",
                    "scores",
                )
            },
        ),
    )

    def is_complete(self, obj):
        return obj.completed_time is not None

    is_complete.boolean = True
    is_complete.short_description = "Complete"


@admin.register(QuestionAnswer)
class QuestionAnswerAdmin(admin.ModelAdmin):
    list_display = (
        "form_progress",
        "question",
        "answer_preview",
        "last_updated_time",
    )
    list_filter = ("question__form_page__form", "last_updated_time")
    search_fields = (
        "form_progress__user__email",
        "question__question",
        "text_answer",
    )
    ordering = ("-last_updated_time",)
    readonly_fields = ("last_updated_time",)
    exclude = ("site",)
    fieldsets = (
        (None, {"fields": ("form_progress", "question")}),
        ("Answer", {"fields": ("selected_options", "text_answer")}),
        ("Metadata", {"fields": ("last_updated_time",)}),
    )

    def answer_preview(self, obj):
        if obj.text_answer:
            return obj.text_answer[:50]
        elif obj.selected_options.exists():
            options = ", ".join([opt.text for opt in obj.selected_options.all()])
            return options[:50]
        return "-"

    answer_preview.short_description = "Answer"


@admin.register(TopicProgress)
class TopicProgressAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "topic",
        "start_time",
        "last_accessed_time",
        "complete_time",
        "is_complete",
    )
    list_filter = ("complete_time", "topic", "start_time")
    search_fields = ("user__email", "topic__title")
    ordering = ("-last_accessed_time",)
    readonly_fields = ("start_time", "last_accessed_time")
    exclude = ("site",)
    fieldsets = (
        (None, {"fields": ("user", "topic")}),
        (
            "Progress",
            {"fields": ("start_time", "last_accessed_time", "complete_time")},
        ),
    )

    def is_complete(self, obj):
        return obj.complete_time is not None

    is_complete.boolean = True
    is_complete.short_description = "Complete"
