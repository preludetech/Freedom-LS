"""Which user-less sittings a browser session may act on."""

from __future__ import annotations

from django.db.models import QuerySet
from django.http import HttpRequest

from freedom_ls.form_engine.models import FormProgress

ANONYMOUS_FORM_PROGRESS_SESSION_KEY = "form_engine_anonymous_form_progress"


def _allowed_pks(request: HttpRequest) -> list[str]:
    stored: list[str] = request.session.get(ANONYMOUS_FORM_PROGRESS_SESSION_KEY, [])
    return stored


def allow_anonymous_form_progress(
    request: HttpRequest, form_progress: FormProgress
) -> None:
    """Let this session act on a sitting that has no user.

    Call it when the sitting is created; afterwards `owned_form_progress`
    resolves it for this session the way it resolves a signed-in owner's.
    """
    pk = str(form_progress.pk)
    if pk in _allowed_pks(request):
        return
    # A new list, not an in-place append, so the session middleware's dirty
    # check sees the change.
    request.session[ANONYMOUS_FORM_PROGRESS_SESSION_KEY] = [*_allowed_pks(request), pk]


def owned_form_progress(request: HttpRequest) -> QuerySet[FormProgress]:
    """The sittings this request may act on: the signed-in user's, or the
    user-less ones this session was allowed. A sitting that gains a user drops
    out of the anonymous branch at once."""
    if request.user.is_authenticated:
        return FormProgress.objects.filter(user=request.user)
    return FormProgress.objects.filter(user__isnull=True, pk__in=_allowed_pks(request))
