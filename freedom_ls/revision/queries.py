from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from django.db.models import Exists, Max, Min, OuterRef, Q, QuerySet

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
from freedom_ls.form_engine.enums import OPTION_QUESTION_TYPES
from freedom_ls.form_engine.models import Form, FormQuestion, QuestionOption
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.queries import completed_collection_item_ids
from freedom_ls.revision import scheduler
from freedom_ls.revision.config import config
from freedom_ls.revision.models import RevisionReview, RevisionSchedule

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


def bank_sections(record: CourseProgress) -> list[Topic | CoursePart]:
    """The placed sections that at least one bank question names, in course order."""
    banked = bank_questions(record)
    named: set[UUID] = set(
        FormQuestionTopic.objects.filter(question__in=banked).values_list(
            "topic_id", flat=True
        )
    ) | set(
        FormQuestionCoursePart.objects.filter(question__in=banked).values_list(
            "course_part_id", flat=True
        )
    )
    placed: dict[UUID, Topic | CoursePart] = {}
    for item in record.course.collection_items_flat():
        child = item.child
        if isinstance(child, Topic | CoursePart):
            placed.setdefault(child.pk, child)
    return [
        placed[section_id]
        for section_id in _placed_sections(record).order
        if section_id in named and section_id in placed
    ]


def weak_sections(user: User, record: CourseProgress) -> set[UUID]:
    """The ids of the course's sections this learner keeps getting wrong.

    Read from the review log on every call, never stored: the flag clears
    by itself once recent answers improve.
    """
    weak: set[UUID] = set()
    for section in bank_sections(record):
        # One bounded query per section: the window is a LIMIT on that
        # section's reviews, which one grouped query could not express
        # without a window function over the whole log.
        recent = list(
            RevisionReview.objects.filter(user=user)
            .filter(question__in=FormQuestion.objects.filter(_naming(section)))
            .order_by("-reviewed_at")
            .values_list("was_correct", flat=True)[: config.REVISION_WEAK_WINDOW]
        )
        if len(recent) < config.REVISION_WEAK_MIN_REVIEWS:
            continue
        missed = recent.count(False)
        if missed / len(recent) >= config.REVISION_WEAK_MISS_RATE:
            weak.add(section.pk)
    return weak


def _ready(
    user: User,
    record: CourseProgress,
    now: datetime,
    section: Topic | CoursePart | None = None,
) -> QuerySet[FormQuestion]:
    """Bank questions the user has no schedule for, or whose schedule is due."""
    ready = bank_questions(record).exclude(
        Exists(
            RevisionSchedule.objects.filter(
                user=user, question=OuterRef("pk"), due__gt=now
            )
        )
    )
    if section is not None:
        ready = ready.filter(_naming(section))
    return ready


def ready_count(
    user: User,
    record: CourseProgress,
    now: datetime,
    *,
    limit: int,
    section: Topic | CoursePart | None = None,
) -> int:
    """How many bank questions are ready, counted no further than `limit`.

    A learner back after a long break may have hundreds due; the page only
    ever says "40+", so the database stops counting there.
    """
    return len(_ready(user, record, now, section).values_list("pk", flat=True)[:limit])


def due_questions(
    user: User,
    record: CourseProgress,
    now: datetime,
    section: Topic | CoursePart | None = None,
) -> list[FormQuestion]:
    """The ready questions in the order a session asks them.

    Questions the learner has reviewed come first, the one they are most
    likely to have forgotten (lowest retrievability) leading. Never-reviewed
    questions follow in course order: a question sits where its first section
    sits, and questions of one section keep their form, page and question order.
    """
    position = {
        section_id: index
        for index, section_id in enumerate(_placed_sections(record).order)
    }
    questions = list(
        _ready(user, record, now, section)
        .select_related("form_page__form")
        .prefetch_related("formquestiontopic_set", "formquestioncoursepart_set")
        .order_by("form_page__form_id", "form_page__order", "order", "pk")
    )
    schedules = {
        schedule.question_id: schedule
        for schedule in RevisionSchedule.objects.filter(
            user=user, question__in=questions
        )
    }

    def first_section(question: FormQuestion) -> int:
        named = [row.topic_id for row in question.formquestiontopic_set.all()] + [
            row.course_part_id for row in question.formquestioncoursepart_set.all()
        ]
        return min(
            position[section_id] for section_id in named if section_id in position
        )

    def retrievability(question: FormQuestion) -> float:
        schedule = schedules[question.pk]
        return scheduler.retrievability(
            scheduler.card_from_columns(
                state=schedule.state,
                step=schedule.step,
                stability=schedule.stability,
                difficulty=schedule.difficulty,
                due=schedule.due,
                last_review=schedule.last_review,
            ),
            now,
        )

    reviewed = [question for question in questions if question.pk in schedules]
    never_reviewed = [
        question for question in questions if question.pk not in schedules
    ]
    # A stable sort keeps the database's form, page and question order within a section.
    return sorted(reviewed, key=retrievability) + sorted(
        never_reviewed, key=first_section
    )


def question_sections(
    record: CourseProgress, question: FormQuestion
) -> list[Topic | CoursePart]:
    """The sections this question names that are placed in the record's course, in course order."""
    named = {row.topic_id for row in question.formquestiontopic_set.all()} | {
        row.course_part_id for row in question.formquestioncoursepart_set.all()
    }
    placed: dict[UUID, Topic | CoursePart] = {}
    for item in record.course.collection_items_flat():
        child = item.child
        if isinstance(child, Topic | CoursePart):
            placed.setdefault(child.pk, child)
    return [
        placed[section_id]
        for section_id in _placed_sections(record).order
        if section_id in named and section_id in placed
    ]


def section_first_placement(
    course: Course, section: Topic | CoursePart
) -> ContentCollectionItem | None:
    """The placement a learner opens to revise this section.

    A Topic's first placement in the course. A CoursePart is not a page, so
    its first nested placement stands in for it.
    """
    for item in course.collection_items_flat():
        child = item.child
        if not isinstance(child, Topic | CoursePart) or child.pk != section.pk:
            continue
        if isinstance(section, Topic):
            return item
        nested = section.collection_items()
        return nested[0] if nested else None
    return None


def next_ready_at(user: User, record: CourseProgress, now: datetime) -> datetime | None:
    """When the soonest scheduled bank question falls due, or None when none is waiting."""
    due: datetime | None = RevisionSchedule.objects.filter(
        user=user, question__in=bank_questions(record), due__gt=now
    ).aggregate(soonest=Min("due"))["soonest"]
    return due


def course_has_revision_questions(course: Course) -> bool:
    """Whether any revisable question names a section placed in this course.

    Asks nothing of the learner's progress: a course whose sections nobody
    has finished still has questions waiting.
    """
    topic_ids: set[UUID] = set()
    part_ids: set[UUID] = set()
    for item in course.collection_items_flat():
        child = item.child
        if isinstance(child, Topic):
            topic_ids.add(child.pk)
        elif isinstance(child, CoursePart):
            part_ids.add(child.pk)
    return (
        _revisable_questions()
        .filter(
            Exists(
                FormQuestionTopic.objects.filter(
                    question=OuterRef("pk"), topic_id__in=topic_ids
                )
            )
            | Exists(
                FormQuestionCoursePart.objects.filter(
                    question=OuterRef("pk"), course_part_id__in=part_ids
                )
            )
        )
        .exists()
    )


def last_reviewed_at(user: User, course: Course) -> datetime | None:
    """When this user last answered a revision question in this course."""
    reviewed: datetime | None = RevisionReview.objects.filter(
        user=user, course=course
    ).aggregate(latest=Max("reviewed_at"))["latest"]
    return reviewed
