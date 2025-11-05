from django.contrib import admin
from .models import (
    Topic,
    ContentCollection,
    ContentCollectionItem,
    Form,
    FormPage,
    FormContent,
    FormQuestion,
    QuestionOption,
    File,
)


class QuestionOptionInline(admin.TabularInline):
    """Inline for question options."""

    model = QuestionOption
    extra = 1
    fields = ("text", "value", "order")


@admin.register(QuestionOption)
class QuestionOptionAdmin(admin.ModelAdmin):
    list_display = ("text", "value", "question", "order")
    list_filter = ("question__form_page__form",)
    search_fields = ("text", "question__question")
    ordering = ("question", "order")


class FormContentInline(admin.StackedInline):
    """Inline for form text items."""

    model = FormContent
    extra = 0
    fields = ("text", "order")


class FormQuestionInline(admin.StackedInline):
    """Inline for form questions."""

    model = FormQuestion
    extra = 0
    fields = ("question", "type", "required", "category", "order")
    show_change_link = True


@admin.register(FormContent)
class FormContentAdmin(admin.ModelAdmin):
    list_display = ("text_preview", "form_page", "order")
    list_filter = ("form_page__form",)
    search_fields = ("text", "form_page__title")
    ordering = ("form_page", "order")

    def text_preview(self, obj):
        return obj.text[:50]

    text_preview.short_description = "Text"


@admin.register(FormQuestion)
class FormQuestionAdmin(admin.ModelAdmin):
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

    def question_preview(self, obj):
        return obj.question[:50]

    question_preview.short_description = "Question"


class FormPageInline(admin.StackedInline):
    """Inline for form pages."""

    model = FormPage
    extra = 0
    fields = ("title", "subtitle", "order")
    show_change_link = True


@admin.register(FormPage)
class FormPageAdmin(admin.ModelAdmin):
    list_display = ("title", "subtitle", "form", "order")
    list_filter = ("form",)
    search_fields = ("title", "subtitle", "form__title")
    ordering = ("form", "order")
    inlines = [FormContentInline, FormQuestionInline]


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("title", "subtitle", "file_path")
    list_filter = ("tags",)
    search_fields = ("title", "subtitle")
    fieldsets = (
        (None, {"fields": ("title", "subtitle", "content")}),
        ("Metadata", {"fields": ("meta", "tags"), "classes": ("collapse",)}),
    )


class ContentCollectionItemInline(admin.TabularInline):
    """Inline for collection items."""

    model = ContentCollectionItem
    extra = 1
    fields = ("child_type", "child_id", "order", "overrides")
    ordering = ("order",)


@admin.register(ContentCollection)
class ContentCollectionAdmin(admin.ModelAdmin):
    list_display = ("title", "subtitle")
    list_filter = ("tags",)
    search_fields = ("title", "subtitle")
    inlines = [ContentCollectionItemInline]
    fieldsets = (
        (None, {"fields": ("title", "subtitle")}),
        ("Metadata", {"fields": ("meta", "tags"), "classes": ("collapse",)}),
    )


@admin.register(ContentCollectionItem)
class ContentCollectionItemAdmin(admin.ModelAdmin):
    list_display = ("collection", "child", "order")
    list_filter = ("collection",)
    search_fields = ("collection__title",)
    ordering = ("collection", "order")


@admin.register(Form)
class FormAdmin(admin.ModelAdmin):
    list_display = ("title", "subtitle", "strategy")
    list_filter = ("strategy", "tags")
    search_fields = ("title", "subtitle")
    inlines = [FormPageInline]
    fieldsets = (
        (None, {"fields": ("title", "subtitle", "content", "strategy")}),
        ("Metadata", {"fields": ("meta", "tags"), "classes": ("collapse",)}),
    )


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = (
        "original_filename",
        "file_type",
        "mime_type",
        "file_path",
    )
    list_filter = ("file_type",)
    search_fields = ("original_filename", "file_path", "mime_type")
    fieldsets = (
        (None, {"fields": ("file", "file_type", "original_filename")}),
        (
            "File Information",
            {"fields": ("file_path", "mime_type"), "classes": ("collapse",)},
        ),
    )
