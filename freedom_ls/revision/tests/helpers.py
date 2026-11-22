"""Builders shared by the revision tests."""

from __future__ import annotations

from django.utils import timezone

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePart,
    Topic,
)
from freedom_ls.content_engine.models.question_sections import (
    FormQuestionCoursePart,
    FormQuestionTopic,
)
from freedom_ls.content_engine.tests.helpers import collection_item_for
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import Form, FormQuestion, FormStrategy
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress


def choice_question(
    *, form: Form | None = None, question_type: str = "multiple_choice"
) -> FormQuestion:
    """A question with one correct and one wrong option, on a page of `form` or of a new bank form."""
    page = FormPageFactory(form=form) if form is not None else FormPageFactory()
    question: FormQuestion = FormQuestionFactory(form_page=page, type=question_type)
    QuestionOptionFactory(question=question, text="Right", correct=True)
    QuestionOptionFactory(question=question, text="Wrong", correct=False)
    return question


def question_testing_topic(topic: Topic, *, form: Form | None = None) -> FormQuestion:
    """A choice question that names `topic` as a section it tests."""
    question = choice_question(form=form)
    FormQuestionTopic.objects.create(question=question, topic=topic)
    return question


def question_testing_part(part: CoursePart) -> FormQuestion:
    """A choice question that names `part` as a section it tests."""
    question = choice_question()
    FormQuestionCoursePart.objects.create(question=question, course_part=part)
    return question


def place_topic(course: Course, order: int = 0) -> tuple[Topic, ContentCollectionItem]:
    """A new topic placed directly in `course`."""
    topic: Topic = TopicFactory()
    item: ContentCollectionItem = ContentCollectionItemFactory(
        collection_object=course, child_object=topic, order=order
    )
    return topic, item


def place_part_with_topics(
    course: Course, topic_count: int
) -> tuple[CoursePart, list[Topic]]:
    """A part placed in `course` with `topic_count` topics nested in it."""
    part: CoursePart = CoursePartFactory()
    ContentCollectionItemFactory(collection_object=course, child_object=part, order=0)
    topics: list[Topic] = [TopicFactory() for _ in range(topic_count)]
    for index, topic in enumerate(topics):
        ContentCollectionItemFactory(
            collection_object=part, child_object=topic, order=index
        )
    return part, topics


def finish_topic(record: CourseProgress, topic: Topic) -> TopicProgress:
    """A completed progress row for `topic` where it sits in the record's course."""
    row: TopicProgress = TopicProgressFactory(
        course_progress=record,
        topic=topic,
        collection_item=collection_item_for(record.course, topic),
        complete_time=timezone.now(),
    )
    return row


def place_form(course: Course, order: int = 0) -> Form:
    """A new quiz form placed in `course`."""
    form: Form = FormFactory(strategy=FormStrategy.QUIZ)
    ContentCollectionItemFactory(
        collection_object=course, child_object=form, order=order
    )
    return form


def complete_form(record: CourseProgress, form: Form) -> None:
    """A completed sitting of `form` where it sits in the record's course."""
    CourseFormAttemptFactory(
        course_progress=record,
        collection_item=collection_item_for(record.course, form),
        form=form,
        form_progress__completed_time=timezone.now(),
    )
