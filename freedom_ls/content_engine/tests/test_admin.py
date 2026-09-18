"""Content admins are locked down against deletion, plus the Course price fieldset."""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from django.contrib import admin
from django.test import override_settings
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
def test_the_admin_saves_a_range_price(staff_client) -> None:
    course = CourseFactory()
    url = _course_change_url(course)

    staff_client.post(
        url,
        _course_change_payload(
            staff_client.get(url),
            price_kind="range",
            price_low_amount="1200.00",
            price_high_amount="3000.00",
            price_currency="ZAR",
        ),
    )

    course.refresh_from_db()
    assert course.price_kind == "range"
    assert course.price_low_amount == Decimal("1200.000")
    assert course.price_high_amount == Decimal("3000.000")


@pytest.mark.django_db
def test_the_admin_saves_a_discounted_price(staff_client) -> None:
    course = CourseFactory()
    url = _course_change_url(course)

    staff_client.post(
        url,
        _course_change_payload(
            staff_client.get(url),
            price_kind="discounted",
            price_amount="1499.00",
            price_sale_amount="999.00",
            price_currency="ZAR",
        ),
    )

    course.refresh_from_db()
    assert course.price_kind == "discounted"
    assert course.price_amount == Decimal("1499.000")
    assert course.price_sale_amount == Decimal("999.000")


@pytest.mark.django_db
def test_the_admin_saves_an_on_request_price(staff_client) -> None:
    course = CourseFactory()
    url = _course_change_url(course)

    staff_client.post(
        url,
        _course_change_payload(staff_client.get(url), price_kind="on_request"),
    )

    course.refresh_from_db()
    assert course.price_kind == "on_request"


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
