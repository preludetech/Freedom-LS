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
from freedom_ls.content_engine.models import ContentCollectionItem, Course, Topic
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.queries import learner_for_course
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory


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
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=True)
    return resolved_user


def course_progress_record(
    course: Course, user: User, **fields: object
) -> CourseProgress:
    """The course progress record the player writes into for this learner.

    Registers the user if nothing already grants them the course. The signal
    receivers that would mint the record defer to ``transaction.on_commit``,
    which a rolled-back test transaction never reaches, so this calls the same
    service the player's self-healing path calls.

    Any ``fields`` given are written onto the record, so a test that wants a
    particular percentage or completion time states it here rather than
    building a row the resolver would not pick.
    """
    resolved = learner_for_course(user, course)
    if resolved is None:
        register_user_for_course(course, user)
        resolved = learner_for_course(user, course)
    assert resolved is not None
    record = ensure_course_progress_record(
        resolved.learner, course, resolved.registration
    )
    if fields:
        for name, value in fields.items():
            setattr(record, name, value)
        record.save(update_fields=list(fields))
    return record


def form_attempt(
    course: Course, user: User, form: Form, **kwargs: object
) -> FormProgress:
    """One attempt at `form` where it sits in `course`, under this learner's record.

    Attempts key on the record and the placement, so a test that only has a
    user and a form has to resolve both before it can build one. Attempt fields
    are forwarded to the form_engine row, so callers still name
    `completed_time` and `scores` directly.
    """
    attempt: FormProgress = CourseFormAttemptFactory(
        course_progress=course_progress_record(course, user),
        collection_item=collection_item_for(course, form),
        form=form,
        **{f"form_progress__{name}": value for name, value in kwargs.items()},
    ).form_progress
    return attempt


def topic_completion(
    course: Course, user: User, topic: Topic, **kwargs: object
) -> TopicProgress:
    """This learner's progress row for `topic` where it sits in `course`."""
    completion: TopicProgress = TopicProgressFactory(
        course_progress=course_progress_record(course, user),
        collection_item=collection_item_for(course, topic),
        topic=topic,
        **kwargs,
    )
    return completion


def learner_with_two_grants(
    course: Course,
) -> tuple[User, CourseProgress, CourseProgress]:
    """One learner holding both a cohort and an individual registration for `course`.

    Returns (user, cohort_record, individual_record). The cohort registration is
    the one ``learner_for_course`` resolves to, so the cohort record is the one
    every learner-facing read path has to show.
    """
    organisation = OrganisationFactory()
    user: User = UserFactory()
    learner = LearnerFactory(user=user, organisation=organisation)
    cohort = CohortFactory(organisation=organisation)
    CohortMembershipFactory(learner=learner, cohort=cohort)
    cohort_registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
    individual_registration = LearnerCourseRegistrationFactory(
        learner=learner, course=course
    )
    cohort_record = ensure_course_progress_record(learner, course, cohort_registration)
    individual_record = ensure_course_progress_record(
        learner, course, individual_registration
    )
    return user, cohort_record, individual_record


def collection_item_for(course: Course, child: Form | Topic) -> ContentCollectionItem:
    """The collection item placing `child` in `course`."""
    for collection_item in course.viewable_collection_items():
        if collection_item.child == child:
            return collection_item
    raise AssertionError(f"{child} is not placed in {course}.")
