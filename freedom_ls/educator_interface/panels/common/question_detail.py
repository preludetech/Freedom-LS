"""Which note a panel shows in place of question detail it may not render."""

from __future__ import annotations

from django.http import HttpRequest

from freedom_ls.learner_management.capabilities import can_view_course_questions
from freedom_ls.organisations.models import Organisation

__all__ = [
    "QUESTION_DETAIL_HIDDEN_NOTE",
    "QUESTION_DETAIL_NEEDS_JAVASCRIPT_NOTE",
    "question_detail_withheld_note",
]

QUESTION_DETAIL_HIDDEN_NOTE = (
    "Question detail is hidden: you do not have permission to view questions."
)
QUESTION_DETAIL_NEEDS_JAVASCRIPT_NOTE = (
    "Question detail loads only with JavaScript turned on."
)


def question_detail_withheld_note(
    request: HttpRequest, organisation: Organisation
) -> str:
    """The note to show in place of question detail, or "" when it may render.

    Question detail renders only on the page's own htmx request: a plain GET
    (a prefetch, or the no-JavaScript link of a lazy panel) would show it
    without the view being recorded. The permission is checked first, so
    someone who could never see the detail is not told to turn JavaScript on.
    """
    if not can_view_course_questions(request.user, organisation):
        return QUESTION_DETAIL_HIDDEN_NOTE
    if request.headers.get("HX-Request") != "true":
        return QUESTION_DETAIL_NEEDS_JAVASCRIPT_NOTE
    return ""
