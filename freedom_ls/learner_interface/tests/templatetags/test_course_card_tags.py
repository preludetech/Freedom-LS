"""Tests for the course card filters and the ``c-course-card`` widget."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import cast

import pytest

from django.test import override_settings
from django.urls import reverse

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import CourseVisibility, Topic
from freedom_ls.course_access.loader import get_course_access_backend
from freedom_ls.learner_interface.templatetags.course_card_tags import (
    course_access_badge,
    get_course_by_path,
)
from freedom_ls.markdown_rendering.markdown_utils import render_markdown

APPLICATION_BACKEND = (
    "freedom_ls.course_applications.backends.ApplicationCourseAccessBackend"
)


@pytest.fixture
def source_topic(mock_site_context) -> Topic:
    return cast("Topic", TopicFactory(file_path="2. topic/content.md"))


def _render(body: str, topic: Topic) -> str:
    return str(render_markdown(body, None, context={"content_instance": topic}))


def _card(path: str = "../course/course.md", variant: str | None = None) -> str:
    variant_attr = f' variant="{variant}"' if variant else ""
    return f'<c-course-card path="{path}"{variant_attr}></c-course-card>'


@pytest.mark.django_db
class TestGetCourseByPath:
    def test_returns_a_published_course(self, source_topic: Topic) -> None:
        course = CourseFactory(file_path="course/course.md")

        assert get_course_by_path("../course/course.md", source_topic) == course

    def test_returns_a_coming_soon_course(self, source_topic: Topic) -> None:
        course = CourseFactory(
            file_path="course/course.md", visibility=CourseVisibility.COMING_SOON
        )

        assert get_course_by_path("../course/course.md", source_topic) == course

    def test_hidden_course_is_none(self, source_topic: Topic) -> None:
        CourseFactory(file_path="course/course.md", visibility=CourseVisibility.HIDDEN)

        assert get_course_by_path("../course/course.md", source_topic) is None

    @pytest.mark.parametrize("path", ["../course/missing.md", "", "   ", None])
    def test_missing_or_empty_path_is_none(
        self, source_topic: Topic, path: str | None
    ) -> None:
        CourseFactory(file_path="course/course.md")

        assert get_course_by_path(path, source_topic) is None

    def test_another_sites_course_is_none(self, source_topic: Topic) -> None:
        CourseFactory(file_path="course/course.md", site=SiteFactory())

        assert get_course_by_path("../course/course.md", source_topic) is None


@pytest.mark.django_db
class TestCourseAccessBadge:
    @override_settings(COURSE_ACCESS_BACKEND=APPLICATION_BACKEND)
    def test_free_course_reads_free(self, mock_site_context) -> None:
        get_course_access_backend.cache_clear()
        course = CourseFactory()

        badge = course_access_badge(course)

        assert badge is not None
        assert badge.label == "Free"

    @override_settings(COURSE_ACCESS_BACKEND=APPLICATION_BACKEND)
    def test_gated_course_reads_by_application(self, mock_site_context) -> None:
        get_course_access_backend.cache_clear()
        course = CourseFactory(access_config={"access_type": "application_gated"})

        badge = course_access_badge(course)

        assert badge is not None
        assert badge.label == "By application"


@pytest.mark.django_db
class TestCourseCardWidget:
    @pytest.fixture(autouse=True)
    def _application_backend(self):
        with override_settings(COURSE_ACCESS_BACKEND=APPLICATION_BACKEND):
            get_course_access_backend.cache_clear()
            yield
        get_course_access_backend.cache_clear()

    @pytest.mark.parametrize("variant", [None, "row", "compact", "bogus"])
    def test_variant_links_the_title_and_shows_the_badge(
        self, source_topic: Topic, variant: str | None
    ) -> None:
        course = CourseFactory(
            title="Card Course", slug="card-course", file_path="course/course.md"
        )
        url = reverse("learner_interface:course_detail", args=[course.slug])

        result = _render(_card(variant=variant), source_topic)

        assert f'href="{url}"' in result
        assert "Card Course" in result
        assert "Free" in result

    def test_shows_subtitle_difficulty_and_duration(self, source_topic: Topic) -> None:
        CourseFactory(
            file_path="course/course.md",
            subtitle="A short subtitle",
            difficulty="beginner",
            estimated_duration=timedelta(hours=2),
        )

        result = _render(_card(), source_topic)

        assert "A short subtitle" in result
        assert "Beginner" in result
        assert "~2 hours" in result

    def test_price_shows_without_the_tax_note(self, source_topic: Topic) -> None:
        CourseFactory(
            file_path="course/course.md",
            price_kind="fixed",
            price_amount=Decimal("1499.000"),
            price_currency="ZAR",
            price_tax_note="incl. VAT",
        )

        result = _render(_card(), source_topic)

        assert 'data-testid="course-price"' in result
        assert "1" in result
        assert "incl. VAT" not in result

    def test_course_without_a_price_shows_the_badge_and_no_price(
        self, source_topic: Topic
    ) -> None:
        CourseFactory(file_path="course/course.md")

        result = _render(_card(), source_topic)

        assert "Free" in result
        assert 'data-testid="course-price"' not in result

    def test_hidden_course_renders_nothing(self, source_topic: Topic) -> None:
        CourseFactory(
            title="Hidden Course",
            file_path="course/course.md",
            visibility=CourseVisibility.HIDDEN,
        )

        result = _render(f"before {_card()} after", source_topic)

        assert "before" in result
        assert "Hidden Course" not in result
        assert "<article" not in result

    def test_coming_soon_course_renders(self, source_topic: Topic) -> None:
        CourseFactory(
            title="Soon Course",
            file_path="course/course.md",
            visibility=CourseVisibility.COMING_SOON,
        )

        result = _render(_card(), source_topic)

        assert "Soon Course" in result

    def test_unknown_variant_equals_row(self, source_topic: Topic) -> None:
        CourseFactory(file_path="course/course.md")

        assert _render(_card(variant="bogus"), source_topic) == _render(
            _card(variant="row"), source_topic
        )

    def test_compact_markup_differs_from_row(self, source_topic: Topic) -> None:
        CourseFactory(file_path="course/course.md")

        assert _render(_card(variant="compact"), source_topic) != _render(
            _card(variant="row"), source_topic
        )
