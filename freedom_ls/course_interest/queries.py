"""Query helpers for course_interest."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
    from django.db.models import QuerySet

    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course

    type RequestUser = User | AnonymousUser | AbstractBaseUser


def get_interested_course_ids(
    user: RequestUser, courses: QuerySet[Course] | Sequence[Course]
) -> set[UUID]:
    """Course ids (from ``courses``) the user has expressed interest in. One query.

    Returns an empty set for unauthenticated users.
    """
    if not user.is_authenticated:
        return set()
    from freedom_ls.course_interest.models import CourseInterest

    return set(
        CourseInterest.objects.filter(user=user, course__in=courses).values_list(
            "course_id", flat=True
        )
    )
