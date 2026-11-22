from __future__ import annotations

from datetime import datetime
from random import Random
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from django.db import transaction
from django.db.models import QuerySet

from freedom_ls.form_engine.models import FormQuestion, QuestionOption
from freedom_ls.form_engine.scoring import is_quiz_answer_correct
from freedom_ls.form_engine.served_paper import new_seed, shuffle_with_locks
from freedom_ls.revision import scheduler
from freedom_ls.revision.config import config
from freedom_ls.revision.models import RevisionReview, RevisionSchedule
from freedom_ls.revision.queries import due_questions

if TYPE_CHECKING:
    from freedom_ls.accounts.models import User
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
    user: User, record: CourseProgress, now: datetime
) -> RevisionSessionState:
    questions = due_questions(user, record, now)[: config.REVISION_SESSION_SIZE]
    return RevisionSessionState(
        question_ids=tuple(question.pk for question in questions),
        seeds=tuple(new_seed() for _ in questions),
        started_at=now,
    )


def shuffled_options(question: FormQuestion, seed: int) -> list[QuestionOption]:
    """The question's options in the order this showing serves them.

    Rebuilt from the seed on every render rather than stored, so a reload
    shows the order the learner was first given.
    """
    return shuffle_with_locks(
        list(question.options.all()),
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
) -> RevisionReview:
    options = list(question.options.all())
    was_correct = is_quiz_answer_correct(selected_option_ids, options)
    schedule = (
        RevisionSchedule.objects.select_for_update()
        .filter(user=user, question=question)
        .first()
    )
    if schedule is None:
        schedule = RevisionSchedule(user=user, question=question)
        before = scheduler.new_card(now)
    else:
        before = scheduler.card_from_columns(
            state=schedule.state,
            step=schedule.step,
            stability=schedule.stability,
            difficulty=schedule.difficulty,
            due=schedule.due,
            last_review=schedule.last_review,
        )
    after, rating = scheduler.review(
        before, scheduler.rating_for(was_correct, guessed=False), now
    )
    columns = scheduler.columns_from_card(after)
    schedule.state = columns["state"]
    schedule.step = columns["step"]
    schedule.stability = columns["stability"]
    schedule.difficulty = columns["difficulty"]
    schedule.due = columns["due"]
    schedule.last_review = columns["last_review"]
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


def session_reviews(
    user: User, state: RevisionSessionState
) -> QuerySet[RevisionReview]:
    """The reviews written since this session started, for its questions."""
    return RevisionReview.objects.filter(
        user=user,
        question_id__in=state.question_ids,
        reviewed_at__gte=state.started_at,
    )
