"""Context processors for student management."""

from __future__ import annotations

from django.http import HttpRequest
from django.utils.functional import SimpleLazyObject

from freedom_ls.learner_management.queries import organisations_accessible_to


def can_access_educator_interface(
    request: HttpRequest,
) -> dict[str, bool | SimpleLazyObject]:
    """Expose whether this user may enter the educator interface.

    The answer is the interface's own gate — reaching at least one
    organisation, whether by organisation role or by a per-cohort grant — so
    the header never offers a link that leads to a 404.

    Every page renders the header, but only some of them ask the question, so
    the EXISTS is wrapped in a SimpleLazyObject: the query runs when a
    template first evaluates the flag, and never otherwise. An anonymous
    visitor is answered without touching the database at all.

    A request that never passed through AuthenticationMiddleware carries no
    ``user`` at all, so it is treated the same way an anonymous one is —
    matching how the contrib auth context processor handles it.
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"can_access_educator_interface": False}

    return {
        "can_access_educator_interface": SimpleLazyObject(
            lambda: organisations_accessible_to(user).exists()
        )
    }
