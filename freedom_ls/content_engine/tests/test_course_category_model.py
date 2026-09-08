"""CourseCategory: per-site uniqueness, Course ordering, and the dashboard_category FK."""

import uuid

import pytest

from django.db import IntegrityError, transaction

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.content_engine.factories import CourseCategoryFactory, CourseFactory
from freedom_ls.content_engine.models import Course


@pytest.mark.django_db
def test_duplicate_slug_within_one_site_raises_integrity_error(mock_site_context):
    CourseCategoryFactory(slug="technical")

    with pytest.raises(IntegrityError), transaction.atomic():
        CourseCategoryFactory(slug="technical")


@pytest.mark.django_db
def test_duplicate_slug_across_two_sites_is_allowed(mock_site_context):
    CourseCategoryFactory(slug="technical")
    other_site = SiteFactory()

    second = CourseCategoryFactory(slug="technical", site=other_site)

    assert second.site == other_site


@pytest.mark.django_db
def test_courses_come_back_ordered_by_title_then_pk(mock_site_context):
    zebra = CourseFactory(title="Zebra")
    alpha_low = CourseFactory(title="Alpha", slug="alpha-1", id=uuid.UUID(int=1))
    alpha_high = CourseFactory(title="Alpha", slug="alpha-2", id=uuid.UUID(int=2))

    assert list(Course.objects.all()) == [alpha_low, alpha_high, zebra]


@pytest.mark.django_db
def test_deleting_a_category_nulls_dashboard_category_on_its_courses(
    mock_site_context,
):
    category = CourseCategoryFactory()
    course = CourseFactory(dashboard_category=category)

    category.delete()
    course.refresh_from_db()

    assert course.dashboard_category is None
