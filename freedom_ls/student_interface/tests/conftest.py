"""Shared fixtures for the course-listing and dashboard view tests."""

from __future__ import annotations

import pytest

# This is the nearest `conftest` module for the playwright tests in this
# package, so it shadows the top-level one for their
# `from conftest import reverse_url` imports. Re-export the helper so those
# imports keep resolving to it.
from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.conftest import reverse_url
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course, Form
from freedom_ls.student_management.factories import UserCourseRegistrationFactory


@pytest.fixture
def courses(mock_site_context) -> list[Course]:
    """Create three courses, each with a topic so progress can be calculated."""
    result = []
    for i, title in enumerate(["Course A", "Course B", "Course C"]):
        slug = title.lower().replace(" ", "-")
        course: Course = CourseFactory(title=title, slug=slug)
        topic = TopicFactory(title=f"Topic {i}", slug=f"topic-{i}", content="content")
        course.items.create(child=topic, order=0)
        result.append(course)
    return result


def course_with_single_question_form(
    course_title: str, course_slug: str, *, required: bool = False
) -> Course:
    """A course whose first item is a one-page, one-question multiple-choice form."""
    course: Course = CourseFactory(title=course_title, slug=course_slug)
    form = FormFactory(title=f"{course_title} Form")
    form_page = FormPageFactory(form=form, order=0, title="Only Page")
    question = FormQuestionFactory(
        form_page=form_page,
        type="multiple_choice",
        question="Pick one",
        required=required,
        order=0,
    )
    QuestionOptionFactory(question=question, text="Alpha", order=0)
    QuestionOptionFactory(question=question, text="Beta", order=1)
    ContentCollectionItemFactory(collection_object=course, child_object=form, order=0)
    return course


def course_with_form(
    form: Form, *, title: str = "Test Course", slug: str | None = None
) -> Course:
    """A course containing `form` as its only item."""
    course: Course = (
        CourseFactory(title=title)
        if slug is None
        else CourseFactory(title=title, slug=slug)
    )
    ContentCollectionItemFactory(collection_object=course, child_object=form)
    return course


def register_user_for_course(course: Course, user: User | None = None) -> User:
    """Register a user (creating one if not given) for `course`; return the user."""
    resolved_user: User = UserFactory() if user is None else user
    UserCourseRegistrationFactory(user=resolved_user, collection=course, is_active=True)
    return resolved_user
