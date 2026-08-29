"""Content admins are locked down against deletion."""

from __future__ import annotations

import pytest

from django.contrib import admin
from django.urls import reverse

from freedom_ls.content_engine.admin import (
    ActivityAdmin,
    ContentCollectionItemAdmin,
    ContentCollectionItemInline,
    CourseAdmin,
    CoursePartAdmin,
    FileAdmin,
    TopicAdmin,
)
from freedom_ls.content_engine.factories import TopicFactory
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


TOPIC_CHANGELIST_URL_NAME = "admin:freedom_ls_content_engine_topic_changelist"


@pytest.mark.django_db
class TestTagFilter:
    def test_filtering_by_a_tag_narrows_the_changelist(self, staff_client) -> None:
        tagged = TopicFactory(title="Tagged", tags=["python", "advanced"])
        TopicFactory(title="Other", tags=["django"])

        response = staff_client.get(
            reverse(TOPIC_CHANGELIST_URL_NAME), {"tag": "python"}
        )

        assert [topic.pk for topic in response.context["cl"].result_list] == [tagged.pk]

    def test_the_filter_offers_every_stored_tag(self, staff_client) -> None:
        TopicFactory(tags=["python", "advanced"])
        TopicFactory(tags=["django"])

        response = staff_client.get(reverse(TOPIC_CHANGELIST_URL_NAME))

        assert _tag_filter_choices(response) == {"advanced", "django", "python"}

    def test_an_unknown_tag_matches_nothing(self, staff_client) -> None:
        TopicFactory(tags=["python"])

        response = staff_client.get(
            reverse(TOPIC_CHANGELIST_URL_NAME), {"tag": "nonexistent"}
        )

        assert list(response.context["cl"].result_list) == []


def _tag_filter_choices(response) -> set[str]:
    """The tag names the changelist sidebar offers, minus its "All" entry."""
    changelist = response.context["cl"]
    spec = next(spec for spec in changelist.filter_specs if str(spec.title) == "tags")
    return {
        choice["display"]
        for choice in spec.choices(changelist)
        if choice["query_string"] != "?"
    }
