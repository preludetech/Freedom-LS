"""Content admins are locked down against deletion."""

from __future__ import annotations

import re

import pytest

from django.contrib import admin
from django.urls import reverse

from freedom_ls.content_engine.admin import (
    ActivityAdmin,
    ContentCollectionItemAdmin,
    CourseAdmin,
    CoursePartAdmin,
    FileAdmin,
    TopicAdmin,
)
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    Activity,
    ContentCollectionItem,
    Course,
    CoursePart,
    File,
    Topic,
)

CONTENT_ADMINS = [
    (TopicAdmin, Topic),
    (ActivityAdmin, Activity),
    (CourseAdmin, Course),
    (CoursePartAdmin, CoursePart),
    (ContentCollectionItemAdmin, ContentCollectionItem),
    (FileAdmin, File),
]


@pytest.mark.parametrize(
    ("admin_class", "model"),
    CONTENT_ADMINS,
    ids=[model.__name__ for _, model in CONTENT_ADMINS],
)
def test_content_admins_never_permit_deletion(admin_class, model) -> None:
    assert admin_class(model, admin.site).has_delete_permission(request=None) is False


@pytest.mark.django_db
class TestTheLockdownReachesTheAdminUi:
    """A superuser -- who holds every Django permission -- still cannot delete.

    `has_delete_permission` returning False is only worth anything if it is what
    the admin actually consults, so these go through HTTP rather than call it.
    """

    def test_the_change_page_offers_no_delete_link(self, staff_client) -> None:
        topic = TopicFactory()

        response = staff_client.get(
            reverse("admin:freedom_ls_content_engine_topic_change", args=[topic.pk])
        )

        delete_url = reverse(
            "admin:freedom_ls_content_engine_topic_delete", args=[topic.pk]
        )
        assert delete_url not in response.content.decode()

    def test_posting_the_delete_url_leaves_the_topic_standing(
        self, staff_client
    ) -> None:
        topic = TopicFactory()

        response = staff_client.post(
            reverse("admin:freedom_ls_content_engine_topic_delete", args=[topic.pk]),
            {"post": "yes"},
        )

        assert response.status_code == 403
        assert Topic.objects.filter(pk=topic.pk).exists()

    def test_the_course_change_page_offers_no_inline_delete_checkbox(
        self, staff_client
    ) -> None:
        """Placements are removed by editing the course, never by a stray tick."""
        course = CourseFactory()
        ContentCollectionItemFactory(
            collection_object=course, child_object=TopicFactory()
        )

        response = staff_client.get(
            reverse("admin:freedom_ls_content_engine_course_change", args=[course.pk])
        )

        assert not re.search(r'name="[^"]*-DELETE"', response.content.decode())
