"""Which unowned sittings a browser holds.

A sitting can exist before any account owns it. Until the claim sets its user,
the only proof a visitor may read or write it is that their session remembers
its id.
"""

from __future__ import annotations

from django.db.models import Q
from django.http import HttpRequest
from django.shortcuts import get_object_or_404

from .models import FormProgress

ANONYMOUS_SITTINGS_SESSION_KEY = "form_engine_anonymous_sitting_ids"


def held_sitting_ids(request: HttpRequest) -> list[str]:
    """The sitting ids this browser holds. Strings, because the session is JSON."""
    ids: list[str] = request.session.get(ANONYMOUS_SITTINGS_SESSION_KEY, [])
    return list(ids)


def remember_anonymous_sitting(
    request: HttpRequest, form_progress: FormProgress
) -> None:
    # Reassigned rather than appended in place: the session only notices a
    # change when the key is set.
    ids = held_sitting_ids(request)
    if str(form_progress.pk) not in ids:
        request.session[ANONYMOUS_SITTINGS_SESSION_KEY] = [
            *ids,
            str(form_progress.pk),
        ]


def forget_anonymous_sitting(request: HttpRequest, form_progress_pk: str) -> None:
    ids = held_sitting_ids(request)
    if form_progress_pk in ids:
        request.session[ANONYMOUS_SITTINGS_SESSION_KEY] = [
            pk for pk in ids if pk != form_progress_pk
        ]


def owned_or_held_q(
    request: HttpRequest, *, user_path: str, pk_path: str, held_ids: list[str]
) -> Q:
    """The rows this request may reach: its own, or unowned ones the session holds.

    An unowned row is only reachable while it is unowned, so a stale id left
    in the session after a claim grants nothing.
    """
    allowed = Q(**{f"{user_path}__isnull": True, f"{pk_path}__in": held_ids})
    if request.user.is_authenticated:
        allowed |= Q(**{user_path: request.user})
    return allowed


def sitting_for_request(request: HttpRequest, progress_pk: str) -> FormProgress:
    """The sitting this request may read and write, or Http404.

    The requester's own sitting, or an unowned one whose id the session holds.
    Nothing else. A signed-in account still reaches a session-held unowned
    sitting: until the application is claimed, the session that created it is
    the only credential there is.
    """
    allowed = owned_or_held_q(
        request, user_path="user", pk_path="pk", held_ids=held_sitting_ids(request)
    )
    sitting: FormProgress = get_object_or_404(
        FormProgress.objects.select_related("form").filter(allowed), pk=progress_pk
    )
    return sitting
