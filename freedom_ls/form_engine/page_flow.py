"""One page of a form sitting: reading it, submitting it, and rendering it.

The exam runner and the application shell are two products built around the
same page. This is the part that is the same in both -- which page a number
names, what a submission of it did, and the context a template needs to draw
it. Neither chrome lives here: no courses, no applications, no access gates.

Distinct from `submissions`, which reads one field out of a POST. This module
handles a whole page of them.

Imported by views, never by `models`, so it may import the models it needs at
module level.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID

from django.http import Http404, HttpRequest, HttpResponse, QueryDict
from django.shortcuts import render

from .models import Form, FormPage, FormProgress, FormQuestion
from .paging import (
    build_page_links,
    rejected_answers_message,
    unanswered_required_message,
    unanswered_required_on_page,
)
from .queries import page_questions
from .typed_answers import RejectedAnswer


@dataclass(frozen=True, slots=True)
class CurrentPage:
    """The page a request is standing on, alongside what it takes to place it.

    Carries `all_pages` because every caller needs the count anyway -- for the
    page-jump nav, the footer, and the decision about what a clean submission of
    the last page does next -- and reading the form's pages a second time to get
    it is a query nobody needs to pay for.
    """

    page: FormPage
    number: int
    all_pages: list[FormPage]
    questions: list[FormQuestion]

    @property
    def total_pages(self) -> int:
        return len(self.all_pages)

    @property
    def is_last(self) -> bool:
        return self.number == len(self.all_pages)


def page_at(form: Form, page_number: int) -> CurrentPage | None:
    """The page this number names, or None when the form has no such page."""
    all_pages = list(form.pages.all())
    if not 1 <= page_number <= len(all_pages):
        return None
    page = all_pages[page_number - 1]
    return CurrentPage(
        page=page,
        number=page_number,
        all_pages=all_pages,
        questions=page_questions(page),
    )


def resolve_page(form: Form, page_number: int) -> CurrentPage:
    """The page a URL names. A number the form has no page for is a 404."""
    current = page_at(form, page_number)
    if current is None:
        raise Http404("No form page at this number.")
    return current


@dataclass(frozen=True, slots=True)
class PageSubmission:
    """What a submission of one page saved, and what stopped it being accepted.

    Default-constructed for a GET: nothing was submitted, so nothing was
    refused. The two messages are the rendered text rather than the questions,
    because that is all any template does with them.
    """

    rejected_answers: dict[UUID, RejectedAnswer] = field(default_factory=dict)
    required_answers_error: str = ""
    rejected_answers_error: str = ""

    @property
    def accepted(self) -> bool:
        return not self.required_answers_error and not self.rejected_answers_error


def submit_page(
    current: CurrentPage,
    post_data: QueryDict,
    form_progress: FormProgress,
    *,
    require_answers: bool = True,
) -> PageSubmission:
    """Save this page's answers, and report what refuses the submission.

    The required-answer check reads the POST before the save, and the save runs
    either way. Throwing away the work someone did do, because of the one field
    they missed, is the cruellest thing a form can do -- so a refused page is
    re-rendered over saved answers rather than over blanks.

    `require_answers=False` is for a submission that finalises the sitting as it
    stands: a blank required question must not trap someone inside an exit
    dialog. A rejected answer still refuses either way, because it cannot be
    stored at all, and finalising on it would freeze the sitting without it.
    """
    unanswered = (
        unanswered_required_on_page(current.questions, post_data, form_progress)
        if require_answers
        else []
    )
    rejected = form_progress.save_answers(current.questions, post_data)
    return PageSubmission(
        rejected_answers=rejected,
        required_answers_error=(
            unanswered_required_message(unanswered) if unanswered else ""
        ),
        rejected_answers_error=(
            rejected_answers_message(
                [question for question in current.questions if question.id in rejected]
            )
            if rejected
            else ""
        ),
    )


def page_context(
    form: Form,
    current: CurrentPage,
    form_progress: FormProgress,
    submission: PageSubmission,
    url_for_page: Callable[[int], str],
    *,
    read_only: bool = False,
) -> dict[str, object]:
    """The keys every rendering of a form page needs.

    `url_for_page` is the caller's: the runner and the application shell reach
    the same page at different URLs, and that is the only thing about paging
    they disagree on.

    `next_page_url` is the address, `has_next_page` the fact. A template that
    only asks whether there is more to come should not have to hold a URL to
    find out.
    """
    next_page_url = None if current.is_last else url_for_page(current.number + 1)
    return {
        "form": form,
        "form_page": current.page,
        "form_progress": form_progress,
        "current_page_num": current.number,
        "total_pages": current.total_pages,
        "previous_page_url": (
            url_for_page(current.number - 1) if current.number > 1 else None
        ),
        "next_page_url": next_page_url,
        "has_next_page": next_page_url is not None,
        "read_only": read_only,
        "existing_answers": form_progress.existing_answers_dict(current.questions),
        "page_links": build_page_links(
            form, form_progress, current.number, url_for_page
        ),
        "required_answers_error": submission.required_answers_error,
        "rejected_answers": submission.rejected_answers,
        "rejected_answers_error": submission.rejected_answers_error,
    }


def render_form_page(
    request: HttpRequest,
    template_name: str,
    context: dict[str, object],
    submission: PageSubmission,
) -> HttpResponse:
    """Render a form page, at the status its submission earned.

    A refused submission is a validation failure rather than a fresh page view,
    so it answers 422. No form page may be cached: on a back-nav it would show
    answers that have since changed.
    """
    response = render(
        request,
        template_name,
        context,
        status=200 if submission.accepted else 422,
    )
    response["Cache-Control"] = "no-store"
    return response
