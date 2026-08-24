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
from uuid import UUID

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Topic
from freedom_ls.form_engine.models import (
    Form,
    FormPage,
    FormQuestion,
    FormStrategy,
    QuestionOption,
    QuestionType,
)
from freedom_ls.learner_progress.models import FormProgress
from freedom_ls.reports.indexes import (
    CohortRoster,
    CourseCatalogue,
    FormProgressIndex,
    ProgressIndex,
    TopicProgressIndex,
)

# FormProgress.user is a plain integer FK column, so a user id is all the
# progress helpers need -- no User row, saved or otherwise.
USER_ID = 1
OTHER_USER_ID = 2

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
    user_id: int = USER_ID,
    completed_time: datetime | None = None,
    scores: dict[str, int] | None = None,
) -> FormProgress:
    """One sitting of `form`, with the form cached so scoring issues no query."""
    return FormProgress(
        user_id=user_id, form=form, completed_time=completed_time, scores=scores
    )


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
    user_id: int = USER_ID,
    first_name: str = "",
    last_name: str = "",
    email: str = "learner@example.test",
) -> User:
    return User(id=user_id, first_name=first_name, last_name=last_name, email=email)


def a_roster(*users: User) -> CohortRoster:
    """A roster over the given users, ordered exactly as passed."""
    learners_by_id = {user.id: user for user in users}
    return CohortRoster(
        learners_by_id=learners_by_id,
        sort_key_by_id={
            user.id: (user.last_name or user.email, user.first_name) for user in users
        },
        learner_ids=[user.id for user in users],
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
    completed_topic_ids_by_user: dict[int, set[UUID]] | None = None,
    topic_complete_time: dict[tuple[int, UUID], datetime] | None = None,
    latest_by_user_form: dict[tuple[int, UUID], FormProgress] | None = None,
    completed_attempts_by_user_form: dict[tuple[int, UUID], list[FormProgress]]
    | None = None,
    completed_form_ids_by_user: dict[int, set[UUID]] | None = None,
    completed_attempt_ids: list[UUID] | None = None,
    user_form_by_attempt_id: dict[UUID, tuple[int, UUID]] | None = None,
    user_ids_with_any_progress: set[int] | None = None,
) -> ProgressIndex:
    """A ProgressIndex assembled field by field, for helpers that only read a few."""
    topics = TopicProgressIndex(
        user_ids_seen=set(),
        completed_topic_ids_by_user=completed_topic_ids_by_user or {},
        complete_time=topic_complete_time or {},
    )
    forms = FormProgressIndex(
        user_ids_seen=set(),
        latest_by_user_form=latest_by_user_form or {},
        completed_attempts_by_user_form=completed_attempts_by_user_form or {},
        completed_form_ids_by_user=completed_form_ids_by_user or {},
        completed_attempt_ids=completed_attempt_ids or [],
        user_form_by_attempt_id=user_form_by_attempt_id or {},
    )
    return ProgressIndex(
        topics=topics,
        forms=forms,
        user_ids_with_any_progress=user_ids_with_any_progress or set(),
    )


def attempted(
    form: Form, attempts: list[FormProgress], *, user_id: int = USER_ID
) -> ProgressIndex:
    """A ProgressIndex holding one learner's chronological sittings of one form.

    Mirrors what `fold_form_progress_rows` produces: the attempts oldest first,
    and the latest row being the last completed one.
    """
    completed = [attempt for attempt in attempts if attempt.completed_time is not None]
    latest = completed[-1] if completed else attempts[-1]
    return a_progress_index(
        latest_by_user_form={(user_id, form.id): latest},
        completed_attempts_by_user_form={(user_id, form.id): completed},
    )
