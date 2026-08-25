"""Hand-built, unsaved model instances for the pure gather-layer tests.

Nothing here touches the database, which is why `test_gather_helpers.py` carries
no `django_db` marker: if a helper under test ever grows a query, pytest-django's
blocker fails the test instead of letting it pass slowly.

Unsaved is enough, for two reasons. `SiteAwareModel` declares a `uuid4` default
primary key, so `a_topic().id` is a real, distinct value the moment the instance
exists -- and every lookup in the gather layer is keyed on those ids. Assigning
`FormProgress(form=form)` caches the `Form` on the instance, so `fp.form`, and
therefore `quiz_percentage()` and `passed()`, read the cache rather than the
database.

Real models rather than the `@dataclass` stand-ins `test_at_risk_rules.py` uses,
because `_completion_counts`, `_latest_completion` and `_completed_items` all
branch on `isinstance(item, Topic)`. A stand-in would silently take the `Form`
branch and the test would pass for the wrong reason.

Every builder returns a fresh instance and nothing is shared at module level, so
one test mutating a map it was handed cannot reach another under pytest-randomly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Topic
from freedom_ls.form_engine.models import (
    Form,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionOption,
    QuestionType,
)
from freedom_ls.learner_progress.models import CourseFormAttempt, CourseProgress
from freedom_ls.reports.indexes import (
    CohortRoster,
    CourseCatalogue,
    FormProgressIndex,
    ProgressIndex,
    TopicProgressIndex,
)

# The gather layer keys everything on Learner ids, and every lookup in it is
# a plain dict read -- so two distinct ids are all the progress helpers need,
# with no Learner row, saved or otherwise.
LEARNER_ID = uuid4()
OTHER_LEARNER_ID = uuid4()

JAN_1 = datetime(2026, 1, 1, tzinfo=UTC)
JAN_2 = datetime(2026, 1, 2, tzinfo=UTC)
JAN_3 = datetime(2026, 1, 3, tzinfo=UTC)


def a_topic(title: str = "A Topic") -> Topic:
    return Topic(title=title)


def a_quiz(title: str = "A Quiz", *, pass_percentage: int | None = 50) -> Form:
    return Form(
        title=title, strategy=FormStrategy.QUIZ, quiz_pass_percentage=pass_percentage
    )


def a_survey(title: str = "A Survey") -> Form:
    return Form(title=title, strategy=FormStrategy.CATEGORY_VALUE_SUM)


def an_attempt(
    form: Form,
    *,
    learner_id: UUID = LEARNER_ID,
    completed_time: datetime | None = None,
    scores: dict[str, int] | None = None,
) -> FormProgress:
    """One sitting of `form`, with the form cached so scoring issues no query.

    The sitting is paired with an unsaved `CourseFormAttempt`, because that is
    where the fold reads the learner from now that the attempt itself is
    course-blind. Assigning the reverse side primes both caches, so
    `fp.course_attempt.course_progress` resolves without a query. Two sittings
    built for the same learner get a record each; the fold keys on the learner
    id inside them, so that is indistinguishable from one record holding both.
    """
    attempt = FormProgress(form=form, completed_time=completed_time, scores=scores)
    attempt.course_attempt = CourseFormAttempt(
        course_progress=CourseProgress(learner_id=learner_id), form_progress=attempt
    )
    return attempt


def a_page(form: Form, *, order: int = 0) -> FormPage:
    return FormPage(form=form, order=order)


def a_question(
    form: Form,
    *,
    text: str = "A question?",
    question_type: str = QuestionType.MULTIPLE_CHOICE,
    order: int = 0,
    page: FormPage | None = None,
) -> FormQuestion:
    """A question on `form`, reachable as `question.form_page.form_id` in memory."""
    return FormQuestion(
        form_page=page if page is not None else a_page(form),
        question=text,
        type=question_type,
        order=order,
    )


def an_option(
    question: FormQuestion, text: str, *, correct: bool | None, order: int = 0
) -> QuestionOption:
    return QuestionOption(question=question, text=text, correct=correct, order=order)


def a_learner(
    *,
    first_name: str = "",
    last_name: str = "",
    email: str = "learner@example.test",
) -> User:
    """The User a roster entry displays. The roster keys it by Learner id."""
    return User(first_name=first_name, last_name=last_name, email=email)


def a_roster(*entries: tuple[UUID, User]) -> CohortRoster:
    """A roster over the given (learner id, user) pairs, ordered exactly as passed."""
    learners_by_id = dict(entries)
    return CohortRoster(
        learners_by_id=learners_by_id,
        sort_key_by_id={
            learner_id: (user.last_name or user.email, user.first_name)
            for learner_id, user in entries
        },
        learner_ids=[learner_id for learner_id, _ in entries],
    )


def a_catalogue(
    *,
    course_items: dict[UUID, list[Topic | Form]] | None = None,
    forms_by_id: dict[UUID, Form] | None = None,
    quiz_form_ids: set[UUID] | None = None,
    ordered_quiz_form_ids: list[UUID] | None = None,
) -> CourseCatalogue:
    items = course_items if course_items is not None else {}
    all_items = [item for course in items.values() for item in course]
    forms = (
        forms_by_id
        if forms_by_id is not None
        else {item.id: item for item in all_items if isinstance(item, Form)}
    )
    quiz_ids = (
        quiz_form_ids
        if quiz_form_ids is not None
        else {form.id for form in forms.values() if form.strategy == FormStrategy.QUIZ}
    )
    return CourseCatalogue(
        course_items=items,
        all_items=all_items,
        forms_by_id=forms,
        topic_ids={item.id for item in all_items if isinstance(item, Topic)},
        form_ids=set(forms),
        quiz_form_ids=quiz_ids,
        ordered_quiz_form_ids=(
            ordered_quiz_form_ids
            if ordered_quiz_form_ids is not None
            else [form_id for form_id in forms if form_id in quiz_ids]
        ),
    )


def a_progress_index(
    *,
    completed_topic_ids_by_learner: dict[UUID, set[UUID]] | None = None,
    topic_complete_time: dict[tuple[UUID, UUID], datetime] | None = None,
    latest_by_learner_form: dict[tuple[UUID, UUID], FormProgress] | None = None,
    completed_attempts_by_learner_form: dict[tuple[UUID, UUID], list[FormProgress]]
    | None = None,
    completed_form_ids_by_learner: dict[UUID, set[UUID]] | None = None,
    completed_attempt_ids: list[UUID] | None = None,
    learner_form_by_attempt_id: dict[UUID, tuple[UUID, UUID]] | None = None,
    learner_ids_with_any_progress: set[UUID] | None = None,
) -> ProgressIndex:
    """A ProgressIndex assembled field by field, for helpers that only read a few."""
    topics = TopicProgressIndex(
        learner_ids_seen=set(),
        completed_topic_ids_by_learner=completed_topic_ids_by_learner or {},
        complete_time=topic_complete_time or {},
    )
    forms = FormProgressIndex(
        learner_ids_seen=set(),
        latest_by_learner_form=latest_by_learner_form or {},
        completed_attempts_by_learner_form=completed_attempts_by_learner_form or {},
        completed_form_ids_by_learner=completed_form_ids_by_learner or {},
        completed_attempt_ids=completed_attempt_ids or [],
        learner_form_by_attempt_id=learner_form_by_attempt_id or {},
    )
    return ProgressIndex(
        topics=topics,
        forms=forms,
        learner_ids_with_any_progress=learner_ids_with_any_progress or set(),
    )


def attempted(
    form: Form, attempts: list[FormProgress], *, learner_id: UUID = LEARNER_ID
) -> ProgressIndex:
    """A ProgressIndex holding one learner's chronological sittings of one form.

    Mirrors what `fold_form_progress_rows` produces: the attempts oldest first,
    and the latest row being the last completed one.
    """
    completed = [attempt for attempt in attempts if attempt.completed_time is not None]
    latest = completed[-1] if completed else attempts[-1]
    return a_progress_index(
        latest_by_learner_form={(learner_id, form.id): latest},
        completed_attempts_by_learner_form={(learner_id, form.id): completed},
    )
