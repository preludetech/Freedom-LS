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
    CourseCategoryAdmin,
    CoursePartAdmin,
    FileAdmin,
    TopicAdmin,
)
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseCategoryFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    Activity,
    ContentCollectionItem,
    Course,
    CourseCategory,
    CoursePart,
    File,
    Topic,
)

CONTENT_ADMINS = [
    (TopicAdmin, Topic),
    (ActivityAdmin, Activity),
    (CourseAdmin, Course),
    (CourseCategoryAdmin, CourseCategory),
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


def test_course_category_admin_never_permits_add() -> None:
    course_category_admin = CourseCategoryAdmin(CourseCategory, admin.site)
    assert course_category_admin.has_add_permission(request=None) is False


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

    def test_the_course_category_add_page_is_forbidden(self, staff_client) -> None:
        response = staff_client.get(
            reverse("admin:freedom_ls_content_engine_coursecategory_add")
        )

        assert response.status_code == 403

    def test_posting_the_course_category_delete_url_leaves_it_standing(
        self, staff_client
    ) -> None:
        category = CourseCategoryFactory()

        response = staff_client.post(
            reverse(
                "admin:freedom_ls_content_engine_coursecategory_delete",
                args=[category.pk],
            ),
            {"post": "yes"},
        )

        assert response.status_code == 403
        assert CourseCategory.objects.filter(pk=category.pk).exists()

    def test_the_course_change_form_shows_categories_read_only(
        self, staff_client
    ) -> None:
        category = CourseCategoryFactory(title="Data literacy")
        course = CourseFactory(dashboard_category=category)
        course.categories.set([category])

        response = staff_client.get(
            reverse("admin:freedom_ls_content_engine_course_change", args=[course.pk])
        )

        html = response.content.decode()
        assert "Data literacy" in html
        assert not re.search(r'<select[^>]*name="dashboard_category"', html)
        assert not re.search(r'<select[^>]*name="categories"', html)
