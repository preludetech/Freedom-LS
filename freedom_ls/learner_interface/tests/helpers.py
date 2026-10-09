"""Builders and lookups shared by the learner_interface view tests."""

from __future__ import annotations

from django.http import HttpResponse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
)
from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.content_engine.tests.helpers import collection_item_for
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.learner_interface.dashboard_sections import DashboardSection
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory


def section_by_slug(response: HttpResponse, slug: str) -> DashboardSection | None:
    """The dashboard section with this slug, or None when it did not render.

    The dashboard's context is a single ordered ``sections`` list rather than
    one key per section, so a test that cares about one section looks it up by
    the slug that also names its page parameter.
    """
    sections: list[DashboardSection] = response.context["sections"]
    return next((section for section in sections if section.slug == slug), None)


def rendered_section(response: HttpResponse, slug: str) -> DashboardSection:
    """The dashboard section with this slug, failing the test when it is absent."""
    section = section_by_slug(response, slug)
    assert section is not None, f"The dashboard rendered no {slug!r} section."
    return section


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
