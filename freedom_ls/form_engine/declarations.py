"""When a quiz sitting needs a signed declaration.

The rule lives here and nowhere else: views and `start_attempt` ask these
helpers rather than re-deriving it from the form's fields.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from freedom_ls.form_engine.enums import FormStrategy
from freedom_ls.form_engine.models import FormDeclaration

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser

    from freedom_ls.accounts.models import User
    from freedom_ls.form_engine.models import Form, FormProgress


def form_requires_declaration(form: Form, user: User | AnonymousUser) -> bool:
    """A quiz that asks a signed-in learner to sign before each attempt."""
    return (
        form.strategy == FormStrategy.QUIZ
        and form.requires_declaration
        and user.is_authenticated
    )


def sitting_needs_declaration(form_progress: FormProgress) -> bool:
    """Whether this sitting is still waiting for its declaration."""
    return (
        form_progress.user is not None
        and form_requires_declaration(form_progress.form, form_progress.user)
        and not FormDeclaration.objects.filter(form_progress=form_progress).exists()
    )


def declaration_text_hash(text: str) -> str:
    """SHA-256 of the declaration as rendered, so a POST can prove it signed that text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
