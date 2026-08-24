"""Shared fixtures for the course-listing and dashboard view tests."""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User

# Re-exported so tests in this package can pull it from the nearest conftest
# alongside the fixtures below, rather than importing from two places.
from freedom_ls.conftest import reverse_url
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import Form
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)


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
    course_title: str,
    course_slug: str,
    *,
    required: bool = False,
    question_type: str = "multiple_choice",
) -> Course:
    """A course whose first item is a one-page, one-question choice form."""
    course: Course = CourseFactory(title=course_title, slug=course_slug)
    form = FormFactory(title=f"{course_title} Form")
    form_page = FormPageFactory(form=form, order=0, title="Only Page")
    question = FormQuestionFactory(
        form_page=form_page,
        type=question_type,
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
    learner = LearnerFactory(user=resolved_user)
    LearnerCourseRegistrationFactory(learner=learner, collection=course, is_active=True)
    return resolved_user
