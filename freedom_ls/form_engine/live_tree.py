"""The part of a form's tree a new sitting may be served.

A row a content save stopped finding in its source is retired, and the form keeps
holding it so sittings already started stay whole. Anything that offers the form
to a sitting not yet served reads it through these functions instead of the
relations. They filter in Python, over whatever the caller already prefetched.

Imported by `models`, so the model classes are named for type checking only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .conditions import FormChild
    from .models import Form, FormPage, FormQuestion, QuestionOption


def live_pages(form: Form) -> list[FormPage]:
    """The form's pages a new sitting may be served."""
    return [page for page in form.pages.all() if not page.is_retired]


def live_children(page: FormPage) -> list[FormChild]:
    """The page's questions and content a new sitting may be served, in order."""
    return [child for child in page.children() if not child.is_retired]


def live_options(question: FormQuestion) -> list[QuestionOption]:
    """The question's options a new sitting may be offered, in order."""
    return [option for option in question.options.all() if not option.is_retired]
