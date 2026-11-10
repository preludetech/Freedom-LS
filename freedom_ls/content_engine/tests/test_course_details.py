"""Tests for the course details context and hero partial shared by the learner
page and the educator preview."""

from __future__ import annotations

import pytest

from django.template.loader import render_to_string

from freedom_ls.content_engine.course_details import course_details_context
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.factories import FormFactory
from freedom_ls.organisations.factories import OrganisationFactory

HERO_TEMPLATE = "content_engine/partials/course_details_hero.html"
FULL_BLEED_CLASS = "w-screen"


def _course_with_topics(count: int) -> Course:
    course: Course = CourseFactory()
    for order in range(count):
        course.items.create(child=TopicFactory(), order=order)
    return course


def _render_hero(course: Course, **extra: object) -> str:
    context = {
        **course_details_context(course),
        "course": course,
        "extra_stats": [],
        "in_modal": False,
        **extra,
    }
    return render_to_string(HERO_TEMPLATE, context)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("topic_count", "label"),
    [(0, "0 lessons"), (1, "1 lesson"), (2, "2 lessons")],
)
def test_lesson_count_label_pluralises(
    mock_site_context, topic_count: int, label: str
) -> None:
    course = _course_with_topics(topic_count)

    context = course_details_context(course)

    assert context["lesson_count"] == topic_count
    assert context["lesson_count_label"] == label


@pytest.mark.django_db
def test_includes_assessments_reflects_a_form_child(mock_site_context) -> None:
    with_form = _course_with_topics(1)
    with_form.items.create(child=FormFactory(), order=5)

    assert course_details_context(with_form)["includes_assessments"] is True
    assert (
        course_details_context(_course_with_topics(1))["includes_assessments"] is False
    )


@pytest.mark.django_db
def test_organisation_is_the_single_non_default_organisation(
    mock_site_context,
) -> None:
    course = CourseFactory()
    organisation = OrganisationFactory()
    course.organisations.add(organisation)

    assert course_details_context(course)["organisation"] == organisation


@pytest.mark.django_db
def test_organisation_is_none_for_a_multi_organisation_course(
    mock_site_context,
) -> None:
    course = CourseFactory()
    course.organisations.add(OrganisationFactory(), OrganisationFactory())

    assert course_details_context(course)["organisation"] is None


@pytest.mark.django_db
def test_hero_renders_each_extra_stat(mock_site_context) -> None:
    course = _course_with_topics(1)

    html = _render_hero(
        course,
        extra_stats=[{"icon": "check", "label": "Enrolment", "value": "Open to all"}],
    )

    assert "Enrolment" in html
    assert "Open to all" in html


@pytest.mark.django_db
def test_hero_without_extra_stats_shows_no_enrolment_stat(mock_site_context) -> None:
    html = _render_hero(_course_with_topics(1))

    assert "Enrolment" not in html


@pytest.mark.django_db
def test_hero_is_full_bleed_outside_a_modal(mock_site_context) -> None:
    html = _render_hero(_course_with_topics(1))

    assert FULL_BLEED_CLASS in html
    assert "max-w-7xl" in html


@pytest.mark.django_db
def test_hero_in_a_modal_drops_the_full_bleed_classes(mock_site_context) -> None:
    html = _render_hero(_course_with_topics(1), in_modal=True)

    assert FULL_BLEED_CLASS not in html
    assert "-ml-[50vw]" not in html
    assert "max-w-7xl" not in html
    assert "rounded-lg" in html
