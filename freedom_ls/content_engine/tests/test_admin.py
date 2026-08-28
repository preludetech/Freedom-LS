"""Content admins are locked down against deletion."""

from __future__ import annotations

from django.contrib import admin

from freedom_ls.content_engine.admin import (
    ActivityAdmin,
    ContentCollectionItemAdmin,
    ContentCollectionItemInline,
    CourseAdmin,
    CoursePartAdmin,
    FileAdmin,
    TopicAdmin,
)
from freedom_ls.content_engine.models import (
    Activity,
    ContentCollectionItem,
    Course,
    CoursePart,
    File,
    Topic,
)


class TestDeletePermissionAlwaysFalse:
    def test_topic_admin(self) -> None:
        assert (
            TopicAdmin(Topic, admin.site).has_delete_permission(request=None) is False
        )

    def test_activity_admin(self) -> None:
        assert (
            ActivityAdmin(Activity, admin.site).has_delete_permission(request=None)
            is False
        )

    def test_course_admin(self) -> None:
        assert (
            CourseAdmin(Course, admin.site).has_delete_permission(request=None) is False
        )

    def test_course_part_admin(self) -> None:
        assert (
            CoursePartAdmin(CoursePart, admin.site).has_delete_permission(request=None)
            is False
        )

    def test_content_collection_item_admin(self) -> None:
        assert (
            ContentCollectionItemAdmin(
                ContentCollectionItem, admin.site
            ).has_delete_permission(request=None)
            is False
        )

    def test_file_admin(self) -> None:
        assert FileAdmin(File, admin.site).has_delete_permission(request=None) is False


def test_content_collection_item_inline_cannot_delete() -> None:
    assert ContentCollectionItemInline.can_delete is False
