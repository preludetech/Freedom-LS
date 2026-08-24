from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin

from .models import (
    Activity,
    ContentCollectionItem,
    Course,
    CoursePart,
    File,
    Topic,
)


@admin.register(Topic)
class TopicAdmin(SiteAwareModelAdmin):
    list_display = ["title", "subtitle", "file_path"]
    list_filter = ("tags",)
    search_fields = ("title", "subtitle", "description")
    readonly_fields = ("slug",)
    fieldsets = (
        (None, {"fields": ("title", "subtitle", "description", "slug", "content")}),
        ("Metadata", {"fields": ("meta", "tags"), "classes": ("collapse",)}),
    )


@admin.register(Activity)
class ActivityAdmin(SiteAwareModelAdmin):
    list_display = ["title", "category", "level", "file_path"]
    list_filter = ("tags",)
    search_fields = ("title", "subtitle", "description")
    readonly_fields = ("slug", "content_preview")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "subtitle",
                    "description",
                    "slug",
                    "content",
                    "content_preview",
                )
            },
        ),
        ("Metadata", {"fields": ("meta", "tags"), "classes": ("collapse",)}),
    )

    @admin.display(description="Content Preview")
    def content_preview(self, obj: Activity) -> str:
        from django.utils.safestring import mark_safe

        if not obj.content:
            return ""
        # Safe: rendered_content() sanitizes via nh3.clean() with strict allowlist
        return str(mark_safe(obj.rendered_content()))  # noqa: S308  # nosec B308 B703


class ContentCollectionItemInline(GenericTabularInline):
    """Inline for collection items."""

    model = ContentCollectionItem
    ct_field = "collection_type"
    ct_fk_field = "collection_id"
    extra = 1
    fields = ("child_type", "child_id", "order", "overrides")
    ordering = ("order",)


@admin.register(Course)
class CourseAdmin(SiteAwareModelAdmin):
    list_display = ["title", "subtitle", "visibility"]
    list_filter = ("visibility", "tags")
    search_fields = ("title", "subtitle", "description")
    readonly_fields = ("slug", "visibility")
    inlines = [ContentCollectionItemInline]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "subtitle",
                    "description",
                    "slug",
                    "learning_outcomes",
                    "difficulty",
                    "visibility",
                    "estimated_duration",
                )
            },
        ),
        ("Metadata", {"fields": ("meta", "tags"), "classes": ("collapse",)}),
    )


@admin.register(CoursePart)
class CoursePartAdmin(SiteAwareModelAdmin):
    list_display = ["title", "subtitle"]
    list_filter = ("tags",)
    search_fields = ("title", "subtitle", "description")
    readonly_fields = ("slug",)
    inlines = [ContentCollectionItemInline]

    fieldsets = (
        (None, {"fields": ("title", "subtitle", "description", "slug")}),
        ("Metadata", {"fields": ("meta", "tags"), "classes": ("collapse",)}),
    )


@admin.register(ContentCollectionItem)
class ContentCollectionItemAdmin(SiteAwareModelAdmin):
    list_display = ["collection", "child", "order"]
    list_filter = ("collection",)
    search_fields = ("collection__title",)
    ordering = ("collection", "order")


@admin.register(File)
class FileAdmin(SiteAwareModelAdmin):
    list_display = [
        "original_filename",
        "file_type",
        "mime_type",
        "file_path",
    ]
    list_filter = ("file_type",)
    search_fields = ("original_filename", "file_path", "mime_type")

    fieldsets = (
        (None, {"fields": ("file", "file_type", "original_filename")}),
        (
            "File Information",
            {"fields": ("file_path", "mime_type"), "classes": ("collapse",)},
        ),
    )
