from django.contrib import admin
from .models import (
    Topic,
    Course,
    ContentCollectionItem,
    Form,
    FormPage,
    FormContent,
    FormQuestion,
    QuestionOption,
    File,
)

from site_aware_models.admin import SiteAwareModelAdmin


class QuestionOptionInline(admin.TabularInline):
    """Inline for question options."""

    model = QuestionOption
    extra = 1
    fields = ("text", "value", "order")


@admin.register(QuestionOption)
class QuestionOptionAdmin(SiteAwareModelAdmin):
    list_display = ("text", "value", "question", "order")
    list_filter = ("question__form_page__form",)
    search_fields = ("text", "question__question")
    ordering = ("question", "order")
    exclude = ("site",)


class FormContentInline(admin.StackedInline):
    """Inline for form text items."""

    model = FormContent
    extra = 0
    fields = ("content", "order")


class FormQuestionInline(admin.StackedInline):
    """Inline for form questions."""

    model = FormQuestion
    extra = 0
    fields = ("question", "type", "required", "category", "order")
    show_change_link = True


@admin.register(FormContent)
class FormContentAdmin(SiteAwareModelAdmin):
    list_display = ("content_preview", "form_page", "order")
    list_filter = ("form_page__form",)
    search_fields = ("content", "form_page__title")
    ordering = ("form_page", "order")
    exclude = ("site",)

    def content_preview(self, obj):
        return obj.content[:50]

    content_preview.short_description = "Content"


@admin.register(FormQuestion)
class FormQuestionAdmin(SiteAwareModelAdmin):
    list_display = (
        "question_preview",
        "type",
        "required",
        "category",
        "form_page",
        "order",
    )
    list_filter = ("type", "required", "category", "form_page__form")
    search_fields = ("question", "category", "form_page__title")
    ordering = ("form_page", "order")
    inlines = [QuestionOptionInline]
    exclude = ("site",)

    def question_preview(self, obj):
        return obj.question[:50]

    question_preview.short_description = "Question"


class FormPageInline(admin.StackedInline):
    """Inline for form pages."""

    model = FormPage
    extra = 0
    fields = ("title", "subtitle", "description", "order")
    show_change_link = True


@admin.register(FormPage)
class FormPageAdmin(SiteAwareModelAdmin):
    list_display = ("title", "subtitle", "form", "order")
    list_filter = ("form",)
    search_fields = ("title", "subtitle", "description", "form__title")
    ordering = ("form", "order")
    inlines = [FormContentInline, FormQuestionInline]
    exclude = ("site",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "subtitle",
                    "description",
                    "form",
                    "category",
                    "order",
                )
            },
        ),
        ("Metadata", {"fields": ("meta", "tags"), "classes": ("collapse",)}),
    )


@admin.register(Topic)
class TopicAdmin(SiteAwareModelAdmin):
    list_display = ("title", "subtitle", "file_path")
    list_filter = ("tags",)
    search_fields = ("title", "subtitle", "description")
    exclude = ("site",)
    fieldsets = (
        (None, {"fields": ("title", "subtitle", "description", "content")}),
        ("Metadata", {"fields": ("meta", "tags"), "classes": ("collapse",)}),
    )


class ContentCollectionItemInline(admin.TabularInline):
    """Inline for collection items."""

    model = ContentCollectionItem
    extra = 1
    fields = ("child_type", "child_id", "order", "overrides")
    ordering = ("order",)


@admin.register(Course)
class CourseAdmin(SiteAwareModelAdmin):
    list_display = ("title", "subtitle")
    list_filter = ("tags",)
    search_fields = ("title", "subtitle", "description")
    inlines = [ContentCollectionItemInline]
    exclude = ("site",)
    fieldsets = (
        (None, {"fields": ("title", "subtitle", "description")}),
        ("Metadata", {"fields": ("meta", "tags"), "classes": ("collapse",)}),
    )


@admin.register(ContentCollectionItem)
class ContentCollectionItemAdmin(SiteAwareModelAdmin):
    list_display = ("collection", "child", "order")
    list_filter = ("collection",)
    search_fields = ("collection__title",)
    ordering = ("collection", "order")
    exclude = ("site",)


@admin.register(Form)
class FormAdmin(SiteAwareModelAdmin):
    list_display = ("title", "subtitle", "strategy")
    list_filter = ("strategy", "tags")
    search_fields = ("title", "subtitle", "description")
    inlines = [FormPageInline]
    exclude = ("site",)
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


@admin.register(File)
class FileAdmin(SiteAwareModelAdmin):
    list_display = (
        "original_filename",
        "file_type",
        "mime_type",
        "file_path",
    )
    list_filter = ("file_type",)
    search_fields = ("original_filename", "file_path", "mime_type")
    exclude = ("site",)
    fieldsets = (
        (None, {"fields": ("file", "file_type", "original_filename")}),
        (
            "File Information",
            {"fields": ("file_path", "mime_type"), "classes": ("collapse",)},
        ),
    )
