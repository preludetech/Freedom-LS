from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Exists, OuterRef, Q

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course
    from freedom_ls.student_management.models import UserCourseRegistration

    type RequestUser = User | AnonymousUser | AbstractBaseUser


def is_registered_for_course_expression(user: RequestUser) -> Q:
    """Build a Q expression marking courses this user is registered for.

    Queryset-level mirror of is_registered_for_course, so the wrapper's
    filter_visible and the per-row check stay in lockstep. Combining two
    Exists() with ``|`` yields a Q-compatible expression usable in both
    ``annotate()`` and ``exclude()``.

    The ``Exists()`` subqueries reference ``OuterRef("pk")``, so this must be
    embedded in a queryset of courses (its pk is the registration target).

    Example::

        courses.annotate(
            _is_registered=is_registered_for_course_expression(user)
        ).exclude(Q(visibility=CourseVisibility.HIDDEN) & Q(_is_registered=False))
    """
    # Lazy import inside the body — mirrors is_registered_for_course (utils.py),
    # which imports these models locally to avoid a module-load import cycle.
    from freedom_ls.student_management.models import (
        CohortCourseRegistration,
        UserCourseRegistration,
    )

    return Exists(
        UserCourseRegistration.objects.filter(
            collection=OuterRef("pk"), user=user, is_active=True
        )
    ) | Exists(
        CohortCourseRegistration.objects.filter(
            collection=OuterRef("pk"),
            cohort__cohortmembership__user=user,
            is_active=True,
        )
    )


def latest_registration(user: User, course: Course) -> UserCourseRegistration | None:
    """Most recent active registration, else most recent of any status.

    A learner can hold more than one registration for the same course, one
    per organisation. Callers that need a single row rather than the full
    set order by ``(-is_active, -registered_at)`` in one query: a descending
    boolean sorts every active row ahead of every inactive one, so recency
    only breaks ties within whichever group is present.
    """
    from freedom_ls.student_management.models import UserCourseRegistration

    return (
        UserCourseRegistration.objects.filter(user=user, collection=course)
        .order_by("-is_active", "-registered_at")
        .first()
    )
