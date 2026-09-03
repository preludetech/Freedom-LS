from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.http import HttpRequest

from freedom_ls.content_base.admin_filters import ContentTagListFilter
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin

from .forms import FileAdminForm
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
    list_filter = (ContentTagListFilter,)
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

    def has_delete_permission(
        self, request: HttpRequest, obj: Topic | None = None
    ) -> bool:
        return False

    @admin.display(description="Content Preview")
    def content_preview(self, obj: Activity) -> str:
        from django.utils.safestring import mark_safe

        if not obj.content:
            return ""
        # Safe: rendered_content() sanitizes via nh3.clean() with strict allowlist
        return str(mark_safe(obj.rendered_content()))  # noqa: S308  # nosec B308 B703


@admin.register(Activity)
class ActivityAdmin(SiteAwareModelAdmin):
    list_display = ["title", "category", "level", "file_path"]
    list_filter = (ContentTagListFilter,)
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

    def has_delete_permission(
        self, request: HttpRequest, obj: Activity | None = None
    ) -> bool:
        return False

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
    can_delete = False


@admin.register(Course)
class CourseAdmin(SiteAwareModelAdmin):
    list_display = ["title", "subtitle", "visibility"]
    list_filter = ("visibility", ContentTagListFilter)
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

    def has_delete_permission(
        self, request: HttpRequest, obj: Course | None = None
    ) -> bool:
        return False


@admin.register(CoursePart)
class CoursePartAdmin(SiteAwareModelAdmin):
    list_display = ["title", "subtitle"]
    list_filter = (ContentTagListFilter,)
    search_fields = ("title", "subtitle", "description")
    readonly_fields = ("slug",)
    inlines = [ContentCollectionItemInline]

    fieldsets = (
        (None, {"fields": ("title", "subtitle", "description", "slug")}),
        ("Metadata", {"fields": ("meta", "tags"), "classes": ("collapse",)}),
    )

    def has_delete_permission(
        self, request: HttpRequest, obj: CoursePart | None = None
    ) -> bool:
        return False


@admin.register(ContentCollectionItem)
class ContentCollectionItemAdmin(SiteAwareModelAdmin):
    # collection and child are generic FKs, so only the concrete columns behind
    # them can be ordered, filtered or searched. Ordering matters beyond this
    # changelist: it is also the queryset the admins that point a ForeignKey at
    # this model build their fields from.
    list_display = ["collection", "child", "order"]
    list_filter = ("collection_type", "child_type")
    search_fields = ("collection_type__model", "child_type__model")
    ordering = ("collection_type", "collection_id", "order")

    def has_delete_permission(
        self, request: HttpRequest, obj: ContentCollectionItem | None = None
    ) -> bool:
        return False


@admin.register(File)
class FileAdmin(SiteAwareModelAdmin):
    form = FileAdminForm
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

    def has_delete_permission(
        self, request: HttpRequest, obj: File | None = None
    ) -> bool:
        return False
