"""Page arithmetic for a form sitting: where it resumes, which pages the
page-jump nav may reach, and which required questions are still outstanding.

Imported by views, never by `models`, so it may import the models it needs at
module level. Nothing here knows about courses, collection items or course
progress: the exam runner and the application shell are both callers, and
neither owns the arithmetic.
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import QueryDict

from .enums import QuestionType
from .models import Form, FormPage, FormProgress, FormQuestion
from .queries import count_form_questions, page_questions
from .submissions import has_submitted_answer


def is_answered(question: FormQuestion, form_progress: FormProgress) -> bool:
    """Whether a stored answer row exists for this question."""
    return form_progress.answers.filter(question=question).exists()


def _furthest_answered_page(form_progress: FormProgress, pages: list[FormPage]) -> int:
    """The highest-numbered page carrying a stored answer, or 0 when none does."""
    answered_page_ids = set(
        form_progress.answers.values_list("question__form_page_id", flat=True)
    )
    return max(
        (
            number
            for number, page in enumerate(pages, start=1)
            if page.id in answered_page_ids
        ),
        default=0,
    )


def _resume_page_number(form_progress: FormProgress, pages: list[FormPage]) -> int:
    current: int = form_progress.get_current_page_number()
    return max(current, _furthest_answered_page(form_progress, pages))


def resume_page_number(form_progress: FormProgress) -> int:
    """The page a sitting picks back up on.

    A skipped optional question leaves no answer row behind, so the
    first-outstanding page can sit behind where the candidate actually reached.
    Taking the furthest answered page as well is what stops a resume dropping
    them back in front of work they have already done.
    """
    return _resume_page_number(form_progress, list(form_progress.form.pages.all()))


def page_accessibility_limit(
    form_progress: FormProgress, current_page_number: int
) -> int:
    """The highest page number the page-jump nav may reach."""
    return max(resume_page_number(form_progress), current_page_number)


def build_page_links(
    form: Form,
    form_progress: FormProgress,
    current_page_number: int,
    url_for_page: Callable[[int], str],
) -> list[dict[str, object]]:
    """One entry per page for the page-jump nav, in page order."""
    pages = list(form.pages.all())
    limit = max(_resume_page_number(form_progress, pages), current_page_number)
    return [
        {
            "number": number,
            "title": page.title,
            "url": url_for_page(number),
            "is_current": number == current_page_number,
            "is_accessible": number <= limit,
        }
        for number, page in enumerate(pages, start=1)
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


def unanswered_required_in_form(form_progress: FormProgress) -> list[FormQuestion]:
    """The required questions anywhere in the form with no stored answer.

    Reads every page, so a required question on a page the candidate never
    visited is caught -- which is what the final submission has to check.
    """
    answered_ids = set(form_progress.answers.values_list("question_id", flat=True))
    return [
        question
        for page in form_progress.form.pages.all()
        for question in page_questions(page)
        if question.required and question.id not in answered_ids
    ]


def unanswered_required_message(questions: list[FormQuestion]) -> str:
    """Name the required questions that still have to be answered."""
    numbers = [str(question.question_number()) for question in questions]
    if len(numbers) == 1:
        return f"Question {numbers[0]} needs an answer before you can continue."
    listed = f"{', '.join(numbers[:-1])} and {numbers[-1]}"
    return f"Questions {listed} need answers before you can continue."


def answered_counts(
    form: Form,
    form_progress: FormProgress,
    current_page_questions: list[FormQuestion],
) -> dict[str, int]:
    """The three tallies the progress indicator reads.

    `answered_count` is the no-JS fallback (persisted answers only);
    `answered_other_pages` is the base the client adds the live current-page
    tally to, so questions on this page are excluded from it.
    """
    current_ids = {question.id for question in current_page_questions}
    return {
        "answered_count": form_progress.answers.count(),
        "answered_other_pages": form_progress.answers.exclude(
            question_id__in=current_ids
        ).count(),
        "total_question_count": count_form_questions(form),
    }
