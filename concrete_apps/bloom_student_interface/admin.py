from unfold.admin import ModelAdmin
from django.contrib import admin

from .models import Child, ChildFormProgress, RecommendedActivity


@admin.register(Child)
class ChildAdmin(ModelAdmin):
    list_display = ["name", "user"]
    search_fields = ["name", "user__email"]
    readonly_fields = ["slug"]
    exclude = ["site"]


@admin.register(ChildFormProgress)
class ChildFormProgressAdmin(ModelAdmin):
    list_display = ["child", "form_progress"]
    search_fields = ["child__name", "form_progress__form__title"]
    exclude = ["site"]


@admin.register(RecommendedActivity)
class RecommendedActivityAdmin(ModelAdmin):
    list_display = ["child", "activity", "form_progress", "created_at"]
    search_fields = ["child__name", "activity__title"]
    list_filter = ["created_at"]
    readonly_fields = ["created_at"]
    exclude = ["site"]
