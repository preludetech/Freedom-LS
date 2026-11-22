from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from django.db.models import Exists, OuterRef, Q, QuerySet

from freedom_ls.content_engine.models import CoursePart, Topic
from freedom_ls.content_engine.models.question_sections import (
    FormQuestionCoursePart,
    FormQuestionTopic,
)
from freedom_ls.form_engine.enums import OPTION_QUESTION_TYPES
from freedom_ls.form_engine.models import Form, FormQuestion, QuestionOption
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.queries import completed_collection_item_ids
from freedom_ls.revision.models import RevisionSchedule

if TYPE_CHECKING:
    from freedom_ls.accounts.models import User


@dataclass(frozen=True)
class _PlacedSections:
    """What one course places, and which of it this record has finished."""

    topic_ids: frozenset[UUID]
    part_ids: frozenset[UUID]
    finished_topic_ids: frozenset[UUID]
    finished_part_ids: frozenset[UUID]
    # Forms placed in the course that the record has not completed.
    uncompleted_form_ids: frozenset[UUID]
    # Every section id in course order, a part ahead of its own topics.
    order: tuple[UUID, ...]


def _placed_sections(record: CourseProgress) -> _PlacedSections:
    # Memoised on the record instance, as Course.collection_items is on the
    # course: one page asks for it many times and nothing in a revision
    # request changes what the record has finished.
    cached: _PlacedSections | None = record.__dict__.get("_placed_sections_cache")
    if cached is not None:
        return cached

    completed = completed_collection_item_ids(record)
    topic_ids: set[UUID] = set()
    part_ids: set[UUID] = set()
    finished_topic_ids: set[UUID] = set()
    finished_part_ids: set[UUID] = set()
    form_ids: set[UUID] = set()
    finished_form_ids: set[UUID] = set()
    order: list[UUID] = []

    for item in record.course.collection_items_flat():
        child = item.child
        if isinstance(child, Topic):
            topic_ids.add(child.pk)
            order.append(child.pk)
            # A topic is finished when any one of its placements here is completed.
            if item.pk in completed:
                finished_topic_ids.add(child.pk)
        elif isinstance(child, CoursePart):
            part_ids.add(child.pk)
            order.append(child.pk)
            nested = child.collection_items()
            # A part with nothing nested has nothing to finish, so it banks nothing.
            if nested and all(nested_item.pk in completed for nested_item in nested):
                finished_part_ids.add(child.pk)
        elif isinstance(child, Form):
            form_ids.add(child.pk)
            # A form is completed when any one of its placements here is completed.
            if item.pk in completed:
                finished_form_ids.add(child.pk)

    placed = _PlacedSections(
        topic_ids=frozenset(topic_ids),
        part_ids=frozenset(part_ids),
        finished_topic_ids=frozenset(finished_topic_ids),
        finished_part_ids=frozenset(finished_part_ids),
        uncompleted_form_ids=frozenset(form_ids - finished_form_ids),
        order=tuple(order),
    )
    record.__dict__["_placed_sections_cache"] = placed
    return placed


def _revisable_questions() -> QuerySet[FormQuestion]:
    """Questions that can be asked in revision at all, whoever the learner is."""
    return FormQuestion.objects.filter(type__in=OPTION_QUESTION_TYPES).filter(
        Exists(QuestionOption.objects.filter(question=OuterRef("pk"), correct=True))
    )


def _naming(section: Topic | CoursePart) -> Q:
    """Matches the questions that name this section."""
    if isinstance(section, Topic):
        return Q(
            Exists(
                FormQuestionTopic.objects.filter(
                    question=OuterRef("pk"), topic_id=section.pk
                )
            )
        )
    return Q(
        Exists(
            FormQuestionCoursePart.objects.filter(
                question=OuterRef("pk"), course_part_id=section.pk
            )
        )
    )


def bank_questions(record: CourseProgress) -> QuerySet[FormQuestion]:
    """The questions this record's learner may revise in this course.

    Derived on every read, never stored: a section finished by any route,
    including one that sends no completion signal, banks its questions.
    """
    placed = _placed_sections(record)
    unfinished_topics = placed.topic_ids - placed.finished_topic_ids
    unfinished_parts = placed.part_ids - placed.finished_part_ids
    return (
        _revisable_questions()
        .filter(
            Exists(
                FormQuestionTopic.objects.filter(
                    question=OuterRef("pk"), topic_id__in=placed.topic_ids
                )
            )
            | Exists(
                FormQuestionCoursePart.objects.filter(
                    question=OuterRef("pk"), course_part_id__in=placed.part_ids
                )
            )
        )
        .exclude(
            Exists(
                FormQuestionTopic.objects.filter(
                    question=OuterRef("pk"), topic_id__in=unfinished_topics
                )
            )
        )
        .exclude(
            Exists(
                FormQuestionCoursePart.objects.filter(
                    question=OuterRef("pk"), course_part_id__in=unfinished_parts
                )
            )
        )
        # A quiz placed in this course keeps its questions and answers out of
        # revision until the learner has completed it. A bank form is placed
        # in no course, so it is never in this set.
        .exclude(form_page__form_id__in=placed.uncompleted_form_ids)
    )


def _ready(user: User, record: CourseProgress, now: datetime) -> QuerySet[FormQuestion]:
    """Bank questions the user has no schedule for, or whose schedule is due."""
    return bank_questions(record).exclude(
        Exists(
            RevisionSchedule.objects.filter(
                user=user, question=OuterRef("pk"), due__gt=now
            )
        )
    )


def ready_count(user: User, record: CourseProgress, now: datetime) -> int:
    return _ready(user, record, now).count()


def due_questions(
    user: User, record: CourseProgress, now: datetime
) -> list[FormQuestion]:
    """The ready questions in the order a session asks them.

    Course order: a question sits where its first section sits, and questions
    of one section keep their form, page and question order.
    """
    position = {
        section_id: index
        for index, section_id in enumerate(_placed_sections(record).order)
    }
    questions = list(
        _ready(user, record, now)
        .select_related("form_page__form")
        .prefetch_related("formquestiontopic_set", "formquestioncoursepart_set")
        .order_by("form_page__form_id", "form_page__order", "order", "pk")
    )

    def first_section(question: FormQuestion) -> int:
        named = [row.topic_id for row in question.formquestiontopic_set.all()] + [
            row.course_part_id for row in question.formquestioncoursepart_set.all()
        ]
        return min(
            position[section_id] for section_id in named if section_id in position
        )

    # A stable sort keeps the database's form, page and question order within a section.
    return sorted(questions, key=first_section)
