from django.contrib import admin

from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin

from .models import (
    Form,
    FormContent,
    FormPage,
    FormProgress,
    FormQuestion,
    QuestionAnswer,
    QuestionOption,
)


class QuestionOptionInline(admin.TabularInline):
    """Inline for question options."""

    model = QuestionOption
    extra = 1
    fields = ("text", "value", "order")


@admin.register(QuestionOption)
class QuestionOptionAdmin(SiteAwareModelAdmin):
    list_display = ["text", "value", "question", "order"]
    list_filter = ("question__form_page__form",)
    search_fields = ("text", "question__question")
    ordering = ("question", "order")


class FormContentInline(admin.StackedInline):
    """Inline for form text items."""

    model = FormContent
    extra = 0
    fields = (
        "content",
        "order",
    )


class FormQuestionInline(admin.StackedInline):
    """Inline for form questions."""

    model = FormQuestion
    extra = 0
    fields = ("question", "type", "required", "category", "order")
    show_change_link = True


@admin.register(FormContent)
class FormContentAdmin(SiteAwareModelAdmin):
    list_display = [
        "content_preview",
        "form_page",
        "order",
    ]
    list_filter = ("form_page__form",)
    search_fields = ("content", "form_page__title")
    ordering = ("form_page", "order")

    @admin.display(description="Content")
    def content_preview(self, obj):
        return obj.content[:50]


@admin.register(FormQuestion)
class FormQuestionAdmin(SiteAwareModelAdmin):
    list_display = [
        "question_preview",
        "type",
        "required",
        "category",
        "form_page",
        "order",
    ]
    list_filter = ("type", "required", "category", "form_page__form")
    search_fields = ("question", "category", "form_page__title")
    ordering = ("form_page", "order")
    inlines = [QuestionOptionInline]

    @admin.display(description="Question")
    def question_preview(self, obj):
        return obj.question[:50]


class FormPageInline(admin.StackedInline):
    """Inline for form pages."""

    model = FormPage
    extra = 0
    fields = ("title", "subtitle", "description", "order")
    show_change_link = True


@admin.register(FormPage)
class FormPageAdmin(SiteAwareModelAdmin):
    list_display = ["title", "subtitle", "form", "order"]
    list_filter = ("form",)
    search_fields = ("title", "subtitle", "description", "form__title")
    ordering = ("form", "order")
    readonly_fields = ("slug",)
    inlines = [FormContentInline, FormQuestionInline]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "subtitle",
                    "description",
                    "slug",
                    "form",
                    "category",
                    "order",
                )
            },
        ),
        ("Metadata", {"fields": ("meta", "tags"), "classes": ("collapse",)}),
    )


@admin.register(Form)
class FormAdmin(SiteAwareModelAdmin):
    list_display = ["title", "subtitle", "strategy"]
    list_filter = ("strategy", "tags")
    search_fields = ("title", "subtitle", "description")
    readonly_fields = ("slug",)
    inlines = [FormPageInline]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "subtitle",
                    "description",
                    "content",
                    "strategy",
                    "slug",
                )
            },
        ),
        ("Metadata", {"fields": ("meta", "tags"), "classes": ("collapse",)}),
    )


class QuestionAnswerInline(admin.TabularInline):
    """Inline for question answers."""

    model = QuestionAnswer
    extra = 0
    fields = ("question", "selected_options", "text_answer", "last_updated_time")
    readonly_fields = ("last_updated_time",)


@admin.register(FormProgress)
class FormProgressAdmin(SiteAwareModelAdmin):
    list_display = [
        "user",
        "form",
        "start_time",
        "last_updated_time",
        "completed_time",
        "is_complete",
    ]
    list_filter = ("completed_time", "form", "start_time")
    search_fields = ("user__email", "form__title")
    ordering = ("-start_time",)
    readonly_fields = ("start_time", "last_updated_time", "scores")
    inlines = [QuestionAnswerInline]

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

    @admin.display(boolean=True, description="Complete")
    def is_complete(self, obj):
        return obj.completed_time is not None


@admin.register(QuestionAnswer)
class QuestionAnswerAdmin(SiteAwareModelAdmin):
    list_display = [
        "form_progress",
        "question",
        "answer_preview",
        "last_updated_time",
    ]
    list_filter = ("question__form_page__form", "last_updated_time")
    search_fields = (
        "form_progress__user__email",
        "question__question",
        "text_answer",
    )
    ordering = ("-last_updated_time",)
    readonly_fields = ("last_updated_time",)

    fieldsets = (
        (None, {"fields": ("form_progress", "question")}),
        ("Answer", {"fields": ("selected_options", "text_answer")}),
        ("Metadata", {"fields": ("last_updated_time",)}),
    )

    @admin.display(description="Answer")
    def answer_preview(self, obj):
        if obj.text_answer:
            return obj.text_answer[:50]
        elif obj.selected_options.exists():
            options = ", ".join([opt.text for opt in obj.selected_options.all()])
            return options[:50]
        return "-"
