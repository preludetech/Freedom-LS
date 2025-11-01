from django.contrib import admin
from .models import (
    Topic,
    ContentCollection,
    Form,
    FormPage,
    FormText,
    FormQuestion,
    QuestionOption,
)


class QuestionOptionInline(admin.TabularInline):
    """Inline for question options."""
    model = QuestionOption
    extra = 1
    fields = ('text', 'value', 'order')


@admin.register(QuestionOption)
class QuestionOptionAdmin(admin.ModelAdmin):
    list_display = ('text', 'value', 'question', 'order')
    list_filter = ('question__form_page__form',)
    search_fields = ('text', 'question__question')
    ordering = ('question', 'order')


class FormTextInline(admin.StackedInline):
    """Inline for form text items."""
    model = FormText
    extra = 0
    fields = ('text', 'order')


class FormQuestionInline(admin.StackedInline):
    """Inline for form questions."""
    model = FormQuestion
    extra = 0
    fields = ('question', 'type', 'required', 'category', 'order')
    show_change_link = True


@admin.register(FormText)
class FormTextAdmin(admin.ModelAdmin):
    list_display = ('text_preview', 'form_page', 'order')
    list_filter = ('form_page__form',)
    search_fields = ('text', 'form_page__title')
    ordering = ('form_page', 'order')

    def text_preview(self, obj):
        return obj.text[:50]
    text_preview.short_description = 'Text'


@admin.register(FormQuestion)
class FormQuestionAdmin(admin.ModelAdmin):
    list_display = ('question_preview', 'type', 'required', 'category', 'form_page', 'order')
    list_filter = ('type', 'required', 'category', 'form_page__form')
    search_fields = ('question', 'category', 'form_page__title')
    ordering = ('form_page', 'order')
    inlines = [QuestionOptionInline]

    def question_preview(self, obj):
        return obj.question[:50]
    question_preview.short_description = 'Question'


class FormPageInline(admin.StackedInline):
    """Inline for form pages."""
    model = FormPage
    extra = 0
    fields = ('title', 'subtitle', 'order')
    show_change_link = True


@admin.register(FormPage)
class FormPageAdmin(admin.ModelAdmin):
    list_display = ('title', 'subtitle', 'form', 'order')
    list_filter = ('form',)
    search_fields = ('title', 'subtitle', 'form__title')
    ordering = ('form', 'order')
    inlines = [FormTextInline, FormQuestionInline]


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'subtitle', 'site_id')
    list_filter = ('site_id', 'tags')
    search_fields = ('title', 'subtitle')
    fieldsets = (
        (None, {
            'fields': ('title', 'subtitle')
        }),
        ('Metadata', {
            'fields': ('meta', 'tags'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ContentCollection)
class ContentCollectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'subtitle', 'site_id')
    list_filter = ('site_id', 'tags')
    search_fields = ('title', 'subtitle')
    fieldsets = (
        (None, {
            'fields': ('title', 'subtitle', 'children')
        }),
        ('Metadata', {
            'fields': ('meta', 'tags'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Form)
class FormAdmin(admin.ModelAdmin):
    list_display = ('title', 'subtitle', 'strategy', 'site_id')
    list_filter = ('strategy', 'site_id', 'tags')
    search_fields = ('title', 'subtitle')
    inlines = [FormPageInline]
    fieldsets = (
        (None, {
            'fields': ('title', 'subtitle', 'strategy')
        }),
        ('Metadata', {
            'fields': ('meta', 'tags'),
            'classes': ('collapse',)
        }),
    )
