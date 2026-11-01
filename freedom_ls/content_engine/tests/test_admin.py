"""Content admins are locked down against deletion, plus the Course price fieldset."""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from django.contrib import admin
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from freedom_ls.content_engine.admin import (
    ActivityAdmin,
    ArticleAdmin,
    ContentCollectionItemAdmin,
    CourseAdmin,
    CourseCategoryAdmin,
    CoursePartAdmin,
    FileAdmin,
    TopicAdmin,
)
from freedom_ls.content_engine.factories import (
    ArticleFactory,
    ContentCollectionItemFactory,
    CourseCategoryFactory,
    CourseFactory,
    CoursePartChildDueDateFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    Activity,
    Article,
    ContentCollectionItem,
    Course,
    CourseCategory,
    CoursePart,
    File,
    Topic,
)
from freedom_ls.organisations.factories import OrganisationFactory

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


# ---------------------------------------------------------------------------
# The Course "Price" fieldset
# ---------------------------------------------------------------------------


def _course_change_url(course: Course) -> str:
    return reverse("admin:freedom_ls_content_engine_course_change", args=[course.pk])


def _course_change_payload(response, **overrides: str) -> dict[str, str]:
    """The admin change form's own values, ready to post straight back.

    ``learning_outcomes``, ``tags`` and ``meta`` are overridden to a blank
    value rather than read from ``form.initial``: their initial value is a
    Python list/dict, and stringifying it (e.g. ``"[]"``) is not what the
    array/JSON widgets expect back as posted data.
    """
    form = response.context["adminform"].form
    payload = {
        name: "" if form.initial.get(name) is None else str(form.initial.get(name, ""))
        for name in form.fields
    }
    payload["learning_outcomes"] = ""
    payload["tags"] = ""
    payload["meta"] = ""
    for inline in response.context["inline_admin_formsets"]:
        prefix = inline.formset.prefix
        payload[f"{prefix}-TOTAL_FORMS"] = "0"
        payload[f"{prefix}-INITIAL_FORMS"] = "0"
        payload[f"{prefix}-MIN_NUM_FORMS"] = "0"
        payload[f"{prefix}-MAX_NUM_FORMS"] = "1000"
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_the_admin_saves_a_fixed_price(staff_client) -> None:
    course = CourseFactory()
    url = _course_change_url(course)

    staff_client.post(
        url,
        _course_change_payload(
            staff_client.get(url),
            price_kind="fixed",
            price_amount="1499.00",
            price_currency="ZAR",
        ),
    )

    course.refresh_from_db()
    assert course.price_kind == "fixed"
    assert course.price_amount == Decimal("1499.000")
    assert course.price_currency == "ZAR"


@pytest.mark.django_db
def test_an_invalid_price_rerenders_with_the_error_on_its_own_field(
    staff_client,
) -> None:
    course = CourseFactory()
    url = _course_change_url(course)

    response = staff_client.post(
        url,
        _course_change_payload(
            staff_client.get(url),
            price_kind="fixed",
            price_amount="0",
            price_currency="ZAR",
        ),
    )

    course.refresh_from_db()
    assert response.status_code == 200
    assert "price_amount" in response.context["adminform"].form.errors
    assert course.price_kind == ""


@pytest.mark.django_db
def test_a_blank_currency_is_saved_as_the_default_currency(staff_client) -> None:
    course = CourseFactory()
    url = _course_change_url(course)

    with override_settings(DEFAULT_CURRENCY="ZAR"):
        staff_client.post(
            url,
            _course_change_payload(
                staff_client.get(url),
                price_kind="fixed",
                price_amount="1499.00",
                price_currency="",
            ),
        )

    course.refresh_from_db()
    assert course.price_currency == "ZAR"


# ---------------------------------------------------------------------------
# Article admin
# ---------------------------------------------------------------------------


def test_article_admin_permits_deletion() -> None:
    assert ArticleAdmin(Article, admin.site).has_delete_permission(request=None) is True


@pytest.mark.parametrize("field", ["slug", "visibility"])
def test_article_admin_keeps_repo_owned_fields_read_only(field: str) -> None:
    assert field in ArticleAdmin(Article, admin.site).readonly_fields


@pytest.mark.django_db
def test_the_article_change_page_offers_the_delete_link(staff_client) -> None:
    article = ArticleFactory()

    response = staff_client.get(
        reverse("admin:freedom_ls_content_engine_article_change", args=[article.pk])
    )

    delete_url = reverse(
        "admin:freedom_ls_content_engine_article_delete", args=[article.pk]
    )
    assert response.status_code == 200
    assert delete_url in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "value"),
    [("image", "images/cover.png"), ("image_alt", "A cover")],
)
def test_the_article_change_page_shows_the_image_fields(
    staff_client, field: str, value: str
) -> None:
    article = ArticleFactory(image="images/cover.png", image_alt="A cover")

    response = staff_client.get(
        reverse("admin:freedom_ls_content_engine_article_change", args=[article.pk])
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert f'name="{field}"' in content
    assert f'value="{value}"' in content


@pytest.mark.django_db
def test_posting_the_article_delete_url_removes_the_article(staff_client) -> None:
    article = ArticleFactory()

    staff_client.post(
        reverse("admin:freedom_ls_content_engine_article_delete", args=[article.pk]),
        {"post": "yes"},
    )

    assert not Article.objects.filter(pk=article.pk).exists()


@pytest.mark.django_db
def test_the_article_changelist_lists_the_article(staff_client) -> None:
    ArticleFactory(title="Why we teach in public")

    response = staff_client.get(
        reverse("admin:freedom_ls_content_engine_article_changelist")
    )

    assert "Why we teach in public" in response.content.decode()


@pytest.mark.django_db
class TestCourseAdminOrganisations:
    def test_organisation_names_joins_the_names_of_the_courses_organisations(
        self, mock_site_context
    ) -> None:
        course = CourseFactory()
        course.organisations.set(
            [
                OrganisationFactory(name="Alpha"),
                OrganisationFactory(name="Beta"),
            ]
        )

        names = CourseAdmin(Course, admin.site).organisation_names(course)

        assert sorted(names.split(", ")) == ["Alpha", "Beta"]

    def test_organisation_names_is_empty_for_a_course_with_none(
        self, mock_site_context
    ) -> None:
        course = CourseFactory()

        assert CourseAdmin(Course, admin.site).organisation_names(course) == ""

    @pytest.mark.parametrize("field", ["organisations", "audience"])
    def test_organisations_and_audience_are_read_only(
        self, field: str, mock_site_context
    ) -> None:
        course_admin = CourseAdmin(Course, admin.site)

        assert field in course_admin.get_readonly_fields(request=None)


@pytest.mark.django_db
class TestPartPlacementChildDueDatesInline:
    def _change_page(self, staff_client, placement: ContentCollectionItem) -> str:
        response = staff_client.get(
            reverse(
                "admin:freedom_ls_content_engine_contentcollectionitem_change",
                args=[placement.pk],
            )
        )
        assert response.status_code == 200
        html: str = response.content.decode()
        return html

    def _part_placement_with_two_rows(self) -> ContentCollectionItem:
        part = CoursePartFactory()
        created = ContentCollectionItemFactory(
            collection_object=CourseFactory(), child_object=part
        )
        part_placement: ContentCollectionItem = ContentCollectionItem.objects.get(
            pk=created.pk
        )
        for order, title in enumerate(["Alpha Topic", "Beta Topic"]):
            child_placement = ContentCollectionItemFactory(
                collection_object=part,
                child_object=TopicFactory(title=title),
                order=order,
            )
            CoursePartChildDueDateFactory(
                part_collection_item=part_placement,
                collection_item=child_placement,
            )
        return part_placement

    def test_the_change_page_lists_both_child_rows(self, staff_client) -> None:
        part_placement = self._part_placement_with_two_rows()

        html = self._change_page(staff_client, part_placement)

        assert "Alpha Topic" in html
        assert "Beta Topic" in html

    def test_each_row_is_headed_by_its_child_not_by_an_object_id(
        self, staff_client
    ) -> None:
        part_placement = self._part_placement_with_two_rows()

        html = self._change_page(staff_client, part_placement)

        assert "CoursePartChildDueDate object" not in html
        assert "Due date for" in html

    def test_the_change_page_query_count_does_not_grow_with_child_rows(
        self, staff_client
    ) -> None:
        part_placement = self._part_placement_with_two_rows()
        # A first render fills the content-type and permission caches; a count taken
        # from it would differ from the second by those, whatever the row count.
        self._change_page(staff_client, part_placement)
        with CaptureQueriesContext(connection) as two_rows:
            self._change_page(staff_client, part_placement)
        part = part_placement.child
        for order in range(2, 6):
            child_placement = ContentCollectionItemFactory(
                collection_object=part,
                child_object=TopicFactory(title=f"Topic {order}"),
                order=order,
            )
            CoursePartChildDueDateFactory(
                part_collection_item=part_placement, collection_item=child_placement
            )

        with CaptureQueriesContext(connection) as six_rows:
            self._change_page(staff_client, part_placement)

        assert len(six_rows) == len(two_rows)

    def test_the_change_page_offers_no_add_row_and_no_delete_control(
        self, staff_client
    ) -> None:
        part_placement = self._part_placement_with_two_rows()

        html = self._change_page(staff_client, part_placement)

        assert 'name="child_due_dates-MAX_NUM_FORMS" value="0"' in html
        assert not re.search(r'name="child_due_dates-\d+-DELETE"', html)

    def test_a_topic_placement_lists_no_child_rows(self, staff_client) -> None:
        topic_placement = ContentCollectionItemFactory(
            collection_object=CourseFactory(),
            child_object=TopicFactory(title="Solo Topic"),
        )

        html = self._change_page(staff_client, topic_placement)

        assert 'name="child_due_dates-TOTAL_FORMS" value="0"' in html
