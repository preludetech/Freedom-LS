from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from django.db.models import Model, QuerySet, prefetch_related_objects
from django.utils.translation import ngettext

from .conditions import (
    FORM_TREE_LOOKUPS,
    SittingPath,
    load_form_tree,
    sitting_path,
)
from .live_tree import live_children, live_pages, served_pages
from .models import (
    Form,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionAnswer,
)
from .units import shuffle_units, unit_question_counts

FINAL_GROUP_TITLE = "Questions no longer on the form"


def without_quiz_answers[T: Model](
    queryset: QuerySet[T], form_progress_path: str
) -> QuerySet[T]:
    """`queryset` without rows answering a quiz.

    `form_progress_path` is the lookup from the queryset's model to its
    FormProgress, e.g. "form_progress" or "answer__form_progress".
    """
    return queryset.exclude(
        **{f"{form_progress_path}__form__strategy": FormStrategy.QUIZ}
    )


def quiz_verdict(form: Form, form_progress: FormProgress) -> bool | None:
    """Whether a completed attempt passed, or None when there is no verdict to give.

    None covers a form that is not a scored quiz at all, a quiz whose author
    left ``quiz_pass_percentage`` unset (the score is real, but nothing in the
    course says what counts as passing it), and an attempt with no percentage to
    read at all. Guarding here also keeps ``FormProgress.passed()``, which raises
    on a null pass mark, from being reached with one.

    Every caller that decides whether a learner may move on reads the verdict
    from here, so the course index and the form's own start page cannot drift
    apart on what "passed" means.
    """
    if form.strategy != FormStrategy.QUIZ or form.quiz_pass_percentage is None:
        return None
    try:
        return form_progress.passed()
    except ValueError:
        # An unscored attempt, a quiz whose questions were added after it was
        # sat, or one whose scores were written under another strategy, has no
        # percentage to measure against the pass mark. Matches how
        # attempt_completes_form declines to hold such an attempt against the
        # learner.
        return None


def attempt_completes_form(attempt: FormProgress) -> bool:
    """Whether a completed attempt leaves its form finished for progress purposes.

    A learner has to pass to complete: sitting a scored quiz and failing it is an
    attempt, not an item they are done with. Anything ``quiz_verdict`` declines
    to judge -- a survey, a quiz with no pass mark, an attempt with no readable
    percentage -- has no bar to clear, so completing it is enough.

    The positive spelling of ``quiz_verdict``, not a second rule beside it: every
    caller that asks whether a placement is finished has to reach the same answer
    as the caller that asks whether the learner may move on.
    """
    return quiz_verdict(attempt.form, attempt) is not False


def count_form_questions(form: Form) -> int:
    """Return the number of live questions across the live pages of a form.

    Uses a single COUNT query traversing the FK chain FormQuestion.form_page → FormPage.form.
    Avoids loading all child objects into memory. A retired question, and every
    question on a retired page, is left out: a new sitting is not served them.
    """
    return (
        FormQuestion.objects.not_retired()
        .filter(form_page__form=form, form_page__retired_at__isnull=True)
        .count()
    )


@dataclass(frozen=True)
class DrawingPageCounts:
    drawn_unit_count: int
    unit_count: int
    questions_per_unit: int
    units_are_groups: bool

    @property
    def drawn_question_count(self) -> int:
        return self.drawn_unit_count * self.questions_per_unit

    @property
    def summary(self) -> str:
        """One line saying what a sitting draws from the page."""
        if not self.units_are_groups:
            return ngettext(
                "Draws %(drawn)d of %(total)d question per attempt",
                "Draws %(drawn)d of %(total)d questions per attempt",
                self.unit_count,
            ) % {"drawn": self.drawn_unit_count, "total": self.unit_count}
        groups = ngettext(
            "Draws %(drawn)d of %(total)d group",
            "Draws %(drawn)d of %(total)d groups",
            self.unit_count,
        ) % {"drawn": self.drawn_unit_count, "total": self.unit_count}
        questions = ngettext(
            "%(count)d question", "%(count)d questions", self.drawn_question_count
        ) % {"count": self.drawn_question_count}
        return f"{groups} ({questions}) per attempt"


def drawing_page_counts(page: FormPage) -> DrawingPageCounts | None:
    """What one sitting draws from the page, or None when the page has no draw.

    Questions per unit are read off the first unit: every unit of a drawing
    page holds the same number, which the content validator enforces on
    authored files and `drawing_page_unit_error` on children edited by hand.
    Group wording is used only when every unit is a group; a unit is a run
    sharing one group, so its first child says whether it is one.
    """
    if page.draw is None:
        return None
    units = shuffle_units(live_children(page))
    counts = unit_question_counts(units, lambda c: isinstance(c, FormQuestion))
    return DrawingPageCounts(
        drawn_unit_count=min(page.draw, len(units)),
        unit_count=len(units),
        questions_per_unit=counts[0] if counts else 0,
        units_are_groups=bool(units) and all(unit[0].group for unit in units),
    )


def count_sitting_questions(form: Form) -> int:
    """How many questions one sitting of the form is served.

    A drawing page counts only what it draws, so the number never reveals
    how many questions the page draws from. A retired page or question is
    left out: a new sitting is not served it.
    """
    load_form_tree(form)
    total = 0
    for page in live_pages(form):
        counts = drawing_page_counts(page)
        total += (
            sum(isinstance(child, FormQuestion) for child in live_children(page))
            if counts is None
            else counts.drawn_question_count
        )
    return total


def count_sitting_pages(form: Form) -> int:
    """How many pages one sitting of the form is served, retired pages left out."""
    load_form_tree(form)
    return len(served_pages(form))


def page_questions(form_page: FormPage) -> list[FormQuestion]:
    """The questions on a page, in the order the page lays them out.

    A page's children interleave questions with content blocks, so the ordering
    only survives if the questions are filtered out of `children()` rather than
    read off the reverse relation.
    """
    return [
        child for child in form_page.children() if child.content_type == "FORM_QUESTION"
    ]


def form_questions(form: Form) -> list[FormQuestion]:
    """Every question currently on the form, in the order a sitting meets them.

    Pages in their own order, then each page's questions as `page_questions`
    lays them out. Expects the form's pages, with their questions and text
    items, to be prefetched; a form read bare costs a query per page.
    """
    return [question for page in form.pages.all() for question in page_questions(page)]


@dataclass(frozen=True)
class AnswerRow:
    question: FormQuestion
    # None when the applicant left the question unanswered: a blank answer stores no row.
    answer: QuestionAnswer | None
    # False when the sitting's path never reached the question; its row then
    # carries no answer, even one an in-progress sitting still holds.
    is_asked: bool = True
    question_retired: bool = False
    # The ids of the chosen options a content save has retired.
    retired_option_ids: frozenset[UUID] = frozenset()


@dataclass(frozen=True)
class AnswerGroup:
    title: str
    rows: list[AnswerRow]


def _row(
    question: FormQuestion, answer: QuestionAnswer | None, is_asked: bool = True
) -> AnswerRow:
    retired_option_ids = (
        frozenset(
            option.pk for option in answer.selected_options.all() if option.is_retired
        )
        if answer is not None
        else frozenset()
    )
    return AnswerRow(
        question,
        answer,
        is_asked,
        question_retired=question.is_retired,
        retired_option_ids=retired_option_ids,
    )


def _answer_row(
    question: FormQuestion,
    answers: dict[UUID, QuestionAnswer],
    path: SittingPath,
) -> AnswerRow:
    answer = answers.get(question.id)
    # Every kind of path keeps a retired question the sitting was asked, so the
    # path alone says whether it was.
    is_asked = path.has_question(question.id)
    return _row(question, answer if is_asked else None, is_asked)


def answer_groups(form_progress: FormProgress) -> list[AnswerGroup]:
    """The sitting's answers, laid out the way the form lays out its questions.

    Walks the form's current pages, so a question the applicant skipped still
    has a row and a question edited since shows its current wording. The join
    is to the live form definition, not a snapshot. A question the sitting's
    path never reached is marked not asked. Answers whose question is on no
    page follow in a final group.
    """
    prefetch_related_objects(
        [form_progress],
        "answers__selected_options",
        "answers__answer_file",
        "answers__question",
        *(f"form__{lookup}" for lookup in FORM_TREE_LOOKUPS),
    )
    # One dict for the whole sitting rather than existing_answers_dict per page:
    # the final group needs the answers no page accounts for.
    answers = {answer.question_id: answer for answer in form_progress.answers.all()}
    path = sitting_path(form_progress, answers)
    groups: list[AnswerGroup] = []
    page_question_ids: set[UUID] = set()
    for page in form_progress.form.pages.all():
        questions = page_questions(page)
        page_question_ids.update(question.id for question in questions)
        groups.append(
            AnswerGroup(
                title=page.title,
                rows=[_answer_row(question, answers, path) for question in questions],
            )
        )
    # A question can leave every page but never be deleted while answered (the
    # answer's FK protects it), so an answer with no page is still an answer.
    off_page_rows = [
        _row(answer.question, answer)
        for answer in form_progress.answers.all()
        if answer.question_id not in page_question_ids
    ]
    if off_page_rows:
        groups.append(AnswerGroup(title=FINAL_GROUP_TITLE, rows=off_page_rows))
    return groups


def stored_score_outdated(
    form_progress: FormProgress,
    path: SittingPath | None,
    answers: Mapping[UUID, QuestionAnswer] | None = None,
) -> bool:
    """Whether the score stored at submission disagrees with what the same
    answers earn under the current marking.

    Scores are frozen at submission and never rescored. max_score is
    compared too: a quiz that gained or lost a question shows a stale
    percentage the score alone cannot catch. A served item missing from
    the form shrinks the recomputed score although marking is unchanged,
    so such a sitting is never reported as outdated.
    """
    if form_progress.form.strategy != FormStrategy.QUIZ or not form_progress.scores:
        return False
    if path is not None and path.has_missing_served_items:
        return False
    current = form_progress.compute_quiz_scores(path, answers)
    return any(
        form_progress.scores.get(key) != current[key] for key in ("score", "max_score")
    )
