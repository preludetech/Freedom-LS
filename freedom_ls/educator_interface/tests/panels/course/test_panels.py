"""Tests for the course details panel."""

from __future__ import annotations

from datetime import timedelta

import pytest

from django.test import Client

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseCategoryFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course as CourseModel
from freedom_ls.educator_interface.tests.helpers import (
    _get_document,
    _interface_url,
)
from freedom_ls.organisations.factories import OrganisationFactory


def test_course_details_panel_does_not_edit_visibility():
    """The educator course details panel never exposes visibility for editing."""
    from freedom_ls.educator_interface.panels.course.panels import CourseDetailsPanel

    assert "visibility" not in CourseDetailsPanel.fields


def _course_details_text(client: Client, course: CourseModel) -> str:
    organisation = OrganisationFactory()
    document = _get_document(
        client, _interface_url(organisation.slug, f"courses/{course.pk}")
    )
    (panel,) = document.cssselect("section[data-panel='details']")
    return " ".join(panel.text_content().split())


@pytest.mark.django_db
def test_course_details_show_each_set_field_with_the_learner_label(
    staff_client: Client,
):
    course = CourseFactory(
        title="Algebra",
        subtitle="Start here",
        difficulty="beginner",
        estimated_duration=timedelta(hours=2),
        time_limit_days=90,
        learning_outcomes=["Solve equations", "Plot graphs"],
    )
    ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(), order=0
    )

    text = _course_details_text(staff_client, course)

    for expected in (
        "Subtitle",
        "Start here",
        "Visibility",
        "Level",
        "Beginner",
        "Duration ~2 hours",
        "Time limit 90 days",
        "Solve equations",
        "Plot graphs",
        "Lessons 1",
    ):
        assert expected in text


@pytest.mark.django_db
def test_course_details_list_each_learning_outcome_on_its_own(
    staff_client: Client,
):
    """An outcome can hold a comma, so joining them with commas would lose
    where one ends and the next begins."""
    organisation = OrganisationFactory()
    course = CourseFactory(learning_outcomes=["Read, write and speak", "Plan"])

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"courses/{course.pk}")
    )
    (panel,) = document.cssselect("section[data-panel='details']")

    items = [
        li.text_content().strip() for li in panel.cssselect("ul li > span:last-child")
    ]
    assert items == ["Read, write and speak", "Plan"]


@pytest.mark.django_db
def test_course_details_label_the_category_row_category(staff_client: Client):
    """The category row read "Dashboard category" (the model field's verbose
    name) instead of the learner page's word, "Category"."""
    course = CourseFactory(dashboard_category=CourseCategoryFactory(title="Maths"))

    text = _course_details_text(staff_client, course)

    assert "Category Maths" in text
    assert "Dashboard category" not in text


@pytest.mark.django_db
def test_course_details_leave_out_rows_without_a_value(staff_client: Client):
    course = CourseFactory(
        subtitle="",
        estimated_duration=None,
        time_limit_days=None,
        learning_outcomes=[],
    )

    text = _course_details_text(staff_client, course)

    for label in ("Subtitle", "Duration", "Time limit", "Learning outcomes"):
        assert label not in text
    assert "Lessons 0" in text


@pytest.mark.django_db
def test_course_details_lesson_count_reads_the_number_of_topics(
    staff_client: Client,
):
    course = CourseFactory()
    for order in range(3):
        ContentCollectionItemFactory(
            collection_object=course, child_object=TopicFactory(), order=order
        )

    assert "Lessons 3" in _course_details_text(staff_client, course)
