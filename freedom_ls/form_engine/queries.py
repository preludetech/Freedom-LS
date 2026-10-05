from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.db.models import prefetch_related_objects

from .models import (
    Form,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionAnswer,
)

FINAL_GROUP_TITLE = "Questions no longer on the form"


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
    """Return the total number of questions across all pages of a form.

    Uses a single COUNT query traversing the FK chain FormQuestion.form_page → FormPage.form.
    Avoids loading all child objects into memory.
    """
    return FormQuestion.objects.filter(form_page__form=form).count()


def page_questions(form_page: FormPage) -> list[FormQuestion]:
    """The questions on a page, in the order the page lays them out.

    A page's children interleave questions with content blocks, so the ordering
    only survives if the questions are filtered out of `children()` rather than
    read off the reverse relation.
    """
    return [
        child for child in form_page.children() if child.content_type == "FORM_QUESTION"
    ]


@dataclass(frozen=True)
class AnswerRow:
    question: FormQuestion
    # None when the applicant left the question unanswered: a blank answer stores no row.
    answer: QuestionAnswer | None


@dataclass(frozen=True)
class AnswerGroup:
    title: str
    rows: list[AnswerRow]


def answer_groups(form_progress: FormProgress) -> list[AnswerGroup]:
    """The sitting's answers, laid out the way the form lays out its questions.

    Walks the form's current pages, so a question the applicant skipped still
    has a row and a question edited since shows its current wording. The join
    is to the live form definition, not a snapshot. Answers whose question is
    on no page follow in a final group.
    """
    prefetch_related_objects(
        [form_progress],
        "answers__selected_options",
        "answers__answer_file",
        "answers__question",
    )
    # One dict for the whole sitting rather than existing_answers_dict per page:
    # the final group needs the answers no page accounts for.
    answers = {answer.question_id: answer for answer in form_progress.answers.all()}
    groups: list[AnswerGroup] = []
    page_question_ids: set[UUID] = set()
    pages = form_progress.form.pages.prefetch_related("text_items", "questions")
    for page in pages:
        questions = page_questions(page)
        page_question_ids.update(question.id for question in questions)
        groups.append(
            AnswerGroup(
                title=page.title,
                rows=[
                    AnswerRow(question, answers.get(question.id))
                    for question in questions
                ],
            )
        )
    # A question can leave every page but never be deleted while answered (the
    # answer's FK protects it), so an answer with no page is still an answer.
    off_page_rows = [
        AnswerRow(answer.question, answer)
        for answer in form_progress.answers.all()
        if answer.question_id not in page_question_ids
    ]
    if off_page_rows:
        groups.append(AnswerGroup(title=FINAL_GROUP_TITLE, rows=off_page_rows))
    return groups
