from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from random import Random
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from django.db import transaction
from django.db.models import Count, Q, QuerySet

from freedom_ls.form_engine.live_tree import live_options
from freedom_ls.form_engine.models import FormQuestion, QuestionOption
from freedom_ls.form_engine.scoring import is_quiz_answer_correct
from freedom_ls.form_engine.served_paper import new_seed, shuffle_with_locks
from freedom_ls.revision import scheduler
from freedom_ls.revision.config import config
from freedom_ls.revision.models import RevisionReview, RevisionSchedule
from freedom_ls.revision.queries import (
    due_questions,
    practice_questions,
    schedule_card,
)

if TYPE_CHECKING:
    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course, CoursePart, Topic
    from freedom_ls.learner_progress.models import CourseProgress


class RevisionSessionState(BaseModel):
    """One revision session as plain data, so the caller can keep it wherever it likes."""

    model_config = ConfigDict(frozen=True)

    question_ids: tuple[UUID, ...]
    seeds: tuple[int, ...]
    started_at: datetime
    index: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _one_seed_per_question(self) -> RevisionSessionState:
        if len(self.seeds) != len(self.question_ids):
            raise ValueError("seeds and question_ids must be the same length")
        return self

    @property
    def current_question_id(self) -> UUID | None:
        """None once the index passes the last question."""
        if self.index >= len(self.question_ids):
            return None
        return self.question_ids[self.index]

    def advanced(self) -> RevisionSessionState:
        return self.model_copy(update={"index": self.index + 1})


def build_session(
    user: User,
    record: CourseProgress,
    now: datetime,
    section: Topic | CoursePart | None = None,
) -> RevisionSessionState:
    """A session over the due questions, or over the weakest ones when nothing is due.

    A learner is never refused a session: with nothing due in the whole
    course, the session practises the questions they find hardest.
    """
    questions = due_questions(user, record, now, section)
    if not questions and section is None:
        questions = practice_questions(
            user,
            record,
            Random(),  # noqa: S311 - ordering, not security
        )
    questions = questions[: config.REVISION_SESSION_SIZE]
    return RevisionSessionState(
        question_ids=tuple(question.pk for question in questions),
        seeds=tuple(new_seed() for _ in questions),
        started_at=now,
    )


def shuffled_options(question: FormQuestion, seed: int) -> list[QuestionOption]:
    """The question's options in the order this showing serves them.

    Rebuilt from the seed on every render rather than stored, so a reload
    shows the order the learner was first given. Retired options are left out.
    """
    return shuffle_with_locks(
        live_options(question),
        lambda option: option.locked,
        Random(seed),  # noqa: S311 - ordering, not security
    )


@transaction.atomic
def record_answer(
    user: User,
    record: CourseProgress,
    question: FormQuestion,
    selected_option_ids: set[UUID],
    now: datetime,
    *,
    session_started_at: datetime | None = None,
) -> RevisionReview:
    """Mark the answer, write its review and move the question's schedule on.

    With ``session_started_at``, an answer this session already wrote for the
    question in this course is returned in place of a second one. The check
    runs under the schedule's row lock, so two submits at once write one review.
    """
    new_columns = scheduler.columns_from_card(scheduler.new_card(now))
    _, created = RevisionSchedule.objects.get_or_create(
        user=user, question=question, defaults=dict(new_columns)
    )
    schedule = RevisionSchedule.objects.select_for_update().get(
        user=user, question=question
    )
    if session_started_at is not None:
        earlier: RevisionReview | None = (
            _reviews_since(user, record.course, session_started_at)
            .filter(question=question)
            .order_by("-reviewed_at")
            .first()
        )
        if earlier is not None:
            return earlier
    # Revision has no served paper, so the options on offer are the live ones.
    was_correct = is_quiz_answer_correct(selected_option_ids, live_options(question))
    before = scheduler.new_card(now) if created else schedule_card(schedule)
    after, rating = scheduler.review(
        before, scheduler.rating_for(was_correct, guessed=False), now
    )
    _store_card(schedule, after)
    schedule.reps += 1
    if not was_correct and scheduler.is_review_state(before):
        schedule.lapses += 1
    schedule.save()
    review: RevisionReview = RevisionReview.objects.create(
        user=user,
        question=question,
        course=record.course,
        reviewed_at=now,
        selected_option_ids=sorted(str(option_id) for option_id in selected_option_ids),
        was_correct=was_correct,
        rating=int(rating),
        schedule_before=before,
    )
    return review


def _store_card(schedule: RevisionSchedule, card: scheduler.CardDict) -> None:
    """Copy the card onto the schedule's columns, without saving."""
    columns = scheduler.columns_from_card(card)
    schedule.state = columns["state"]
    schedule.step = columns["step"]
    schedule.stability = columns["stability"]
    schedule.difficulty = columns["difficulty"]
    schedule.due = columns["due"]
    schedule.last_review = columns["last_review"]


class GuessRefused(Exception):  # noqa: N818 - a refusal, named for what the caller sees
    """The review can't be re-rated: it was wrong, or a later review has replaced it."""


@transaction.atomic
def mark_guessed(review: RevisionReview) -> RevisionReview:
    """Flip "I guessed" on a right answer and re-rate it.

    Replays the review from the card it started from, at the instant it was
    first given, so the schedule ends up where a first-time rating would
    have put it and a second tap undoes the first.
    """
    schedule = RevisionSchedule.objects.select_for_update().get(
        user=review.user, question=review.question
    )
    latest = (
        RevisionReview.objects.filter(user=review.user, question=review.question)
        .order_by("-reviewed_at")
        .first()
    )
    if not review.was_correct or latest is None or latest.pk != review.pk:
        raise GuessRefused
    guessed = not review.guessed
    after, rating = scheduler.review(
        review.schedule_before,
        scheduler.rating_for(True, guessed),
        review.reviewed_at,
    )
    _store_card(schedule, after)
    schedule.save()
    review.guessed = guessed
    review.rating = int(rating)
    review.save()
    return review


def _reviews_since(
    user: User, course: Course, since: datetime
) -> QuerySet[RevisionReview]:
    return RevisionReview.objects.filter(
        user=user, course=course, reviewed_at__gte=since
    )


def session_reviews(
    user: User, state: RevisionSessionState, course: Course
) -> QuerySet[RevisionReview]:
    """The reviews written on this course's revision page since this session started, for its questions.

    The schedule is shared across courses, but a session only counts the
    answers given in its own course.
    """
    return _reviews_since(user, course, state.started_at).filter(
        question_id__in=state.question_ids
    )


@dataclass(frozen=True)
class SessionSummary:
    """What the learner did in one session, in the words the done card uses."""

    answered: int
    knew: int
    hard: int
    forgot: int


def session_summary(
    user: User, state: RevisionSessionState, course: Course
) -> SessionSummary:
    """Knew is right, hard is right but guessed, forgot is wrong."""
    counts = session_reviews(user, state, course).aggregate(
        answered=Count("pk"),
        knew=Count("pk", filter=Q(was_correct=True, guessed=False)),
        hard=Count("pk", filter=Q(was_correct=True, guessed=True)),
        forgot=Count("pk", filter=Q(was_correct=False)),
    )
    return SessionSummary(**counts)
