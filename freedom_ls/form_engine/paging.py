"""Page arithmetic for a form sitting: where it resumes, which pages the
page-jump nav may reach, and which required questions are still outstanding.

Imported by views, never by `models`, so it may import the models it needs at
module level. Nothing here knows about courses, collection items or course
progress: the exam runner and the application shell are both callers, and
neither owns the arithmetic.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from django.http import QueryDict

from .conditions import SittingPath
from .enums import QuestionType
from .models import FormProgress, FormQuestion
from .submissions import has_submitted_answer


def is_answered(question: FormQuestion, form_progress: FormProgress) -> bool:
    """Whether a stored answer row exists for this question."""
    return form_progress.answers.filter(question=question).exists()


def _answered_ids(form_progress: FormProgress) -> set[UUID]:
    return set(form_progress.answers.values_list("question_id", flat=True))


def _furthest_answered_page(path: SittingPath, answered_ids: set[UUID]) -> int:
    """The highest on-path page number carrying an answer to an on-path question, or 0."""
    return max(
        (
            number
            for number, page in path.numbered_pages()
            if any(q.id in answered_ids for q in path.questions_of(page))
        ),
        default=0,
    )


def _resume_page_number(form_progress: FormProgress, path: SittingPath) -> int:
    numbered = path.numbered_pages()
    if not numbered:
        return 1
    answered_ids = _answered_ids(form_progress)
    candidate = min(
        max(
            form_progress.get_current_page_number(path, answered_ids),
            _furthest_answered_page(path, answered_ids),
            form_progress.furthest_page_reached,
        ),
        len(path.all_pages),
    )
    # furthest_page_reached is an authored number and may name a page the
    # answers have since closed, so the candidate is moved onto the path.
    landed = path.first_page_number_at_or_after(candidate)
    return landed if landed is not None else numbered[-1][0]


def resume_page_number(form_progress: FormProgress, path: SittingPath) -> int:
    """The page a sitting picks back up on.

    A skipped optional question leaves no answer row behind, so the
    first-outstanding page can sit behind where the candidate actually reached.
    The furthest page they were shown, and the furthest one they answered on,
    both count too: that is what stops a resume dropping them back in front of
    work they have already done. The answered-page term still matters for
    sittings that predate the reached-page record. The reached-page record
    outlives a page an author later deletes and may name a page the answers
    have since taken off the path, so the result is clamped to the pages the
    form has and moved onto the path.
    """
    return _resume_page_number(form_progress, path)


def page_accessibility_limit(
    form_progress: FormProgress, current_page_number: int, path: SittingPath
) -> int:
    """The highest page number the page-jump nav may reach."""
    return max(resume_page_number(form_progress, path), current_page_number)


def build_page_links(
    form_progress: FormProgress,
    current_page_number: int,
    url_for_page: Callable[[int], str],
    path: SittingPath,
) -> list[dict[str, object]]:
    """One entry per page the sitting is asked, for the page-jump nav, in page order.

    `number` is the label: the page's place on the path. `url` is built from the
    authored page number.
    """
    limit = page_accessibility_limit(form_progress, current_page_number, path)
    return [
        {
            "number": path.page_position(number),
            "title": page.title,
            "url": url_for_page(number),
            "is_current": number == current_page_number,
            "is_accessible": number <= limit,
        }
        for number, page in path.numbered_pages()
    ]


def unanswered_required_on_page(
    questions: list[FormQuestion],
    post_data: QueryDict,
    form_progress: FormProgress,
) -> list[FormQuestion]:
    """The required questions on this page the submission does not answer.

    A file question is measured against its stored row rather than the POST: its
    answer arrived on its own request and never rides the page submission.
    """

    def answered(question: FormQuestion) -> bool:
        if question.type == QuestionType.FILE_UPLOAD:
            return is_answered(question, form_progress)
        return has_submitted_answer(question, post_data)

    return [
        question
        for question in questions
        if question.required and not answered(question)
    ]


def unanswered_required_in_form(
    form_progress: FormProgress, path: SittingPath
) -> list[FormQuestion]:
    """The required questions the sitting is asked that have no stored answer.

    Reads every page on the path, so a required question on a page the candidate
    never visited is caught -- which is what the final submission has to check.
    """
    answered_ids = _answered_ids(form_progress)
    return [
        question
        for question in path.questions()
        if question.required and question.id not in answered_ids
    ]


def first_page_number_with_unanswered_required(
    path: SittingPath, unanswered: list[FormQuestion], *, after: int = 0
) -> int | None:
    """The lowest authored page number above `after` holding one of `unanswered`."""
    unanswered_ids = {question.id for question in unanswered}
    return next(
        (
            number
            for number, page in path.numbered_pages()
            if number > after
            and any(q.id in unanswered_ids for q in path.questions_of(page))
        ),
        None,
    )


def _question_numbers(questions: list[FormQuestion], path: SittingPath) -> list[str]:
    positions = path.question_positions()
    return [str(positions[question.id]) for question in questions]


def unanswered_required_message(
    questions: list[FormQuestion], path: SittingPath
) -> str:
    """Name the required questions that still have to be answered."""
    numbers = _question_numbers(questions, path)
    if len(numbers) == 1:
        return f"Question {numbers[0]} needs an answer before you can continue."
    listed = f"{', '.join(numbers[:-1])} and {numbers[-1]}"
    return f"Questions {listed} need answers before you can continue."


def rejected_answers_message(questions: list[FormQuestion], path: SittingPath) -> str:
    """Name the questions whose answers were not valid for their type."""
    numbers = _question_numbers(questions, path)
    if len(numbers) == 1:
        return f"Question {numbers[0]} needs a valid answer."
    listed = f"{', '.join(numbers[:-1])} and {numbers[-1]}"
    return f"Questions {listed} need valid answers."


def answered_counts(
    form_progress: FormProgress,
    current_page_questions: list[FormQuestion],
    path: SittingPath,
) -> dict[str, int]:
    """The three tallies the progress indicator reads.

    Only questions the sitting is asked count, so an answer left behind by a
    question that has since dropped off the path is not tallied.
    `answered_count` is the no-JS fallback (persisted answers only);
    `answered_other_pages` is the base the client adds the live current-page
    tally to, so questions on this page are excluded from it.
    """
    answered_ids = _answered_ids(form_progress) & path.question_ids
    current_ids = {question.id for question in current_page_questions}
    return {
        "answered_count": len(answered_ids),
        "answered_other_pages": len(answered_ids - current_ids),
        "total_question_count": len(path.question_ids),
    }
