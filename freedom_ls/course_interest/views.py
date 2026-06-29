"""Views for course_interest.

Express/remove-interest HTMX views are added in Phase 3 (Task 3.1).
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse


def partial_express_interest(request: HttpRequest, course_slug: str) -> HttpResponse:
    # TODO(Phase 3): implement express-interest HTMX view (Task 3.1)
    raise NotImplementedError("Implemented in Phase 3")


def partial_remove_interest(request: HttpRequest, course_slug: str) -> HttpResponse:
    # TODO(Phase 3): implement remove-interest HTMX view (Task 3.1)
    raise NotImplementedError("Implemented in Phase 3")
