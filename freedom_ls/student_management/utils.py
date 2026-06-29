from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from django.db.models import Exists, OuterRef, Q

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course

    type RequestUser = User | AnonymousUser | AbstractBaseUser


def calculate_course_progress_percentage(
    course,
    completed_topic_ids: set[UUID],
    completed_form_ids: set[UUID],
) -> int:
    """
    Calculate the percentage of completion for a course.

    This function counts all completable items in a course, including:
    - Direct child items (Topics and Forms)
    - Items nested inside CourseParts

    Args:
        course: The Course object
        completed_topic_ids: Set of UUIDs for completed topics
        completed_form_ids: Set of UUIDs for completed forms

    Returns:
        Integer percentage (0-100) of course completion, rounded
    """
    # Get all completable items (recursively for CourseParts)
    total_items = 0
    completed_items = 0

    def count_items(children):
        """Recursively count items, expanding CourseParts."""
        nonlocal total_items, completed_items

        for child in children:
            if child.content_type == "COURSE_PART":
                # Recurse into CoursePart children
                count_items(child.children())
            elif child.content_type == "TOPIC":
                total_items += 1
                if child.id in completed_topic_ids:
                    completed_items += 1
            elif child.content_type == "FORM":
                total_items += 1
                if child.id in completed_form_ids:
                    completed_items += 1

    # Start counting from course children
    children = course.children()
    count_items(children)

    # Calculate percentage
    if total_items > 0:
        return round((completed_items / total_items) * 100)
    else:
        return 0


def registered_course_exists(user: RequestUser) -> Q:
    """OR of Exists() subqueries: courses (OuterRef pk) this user is registered for.

    Queryset-level mirror of is_registered_for_course, so the wrapper's
    filter_visible and the per-row check stay in lockstep. Combining two
    Exists() with ``|`` yields a Q-compatible expression usable in both
    ``annotate()`` and ``exclude()``.
    """
    # Lazy import inside the body — mirrors is_registered_for_course (utils.py:76-79),
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


def is_registered_for_course(user: RequestUser, course: Course) -> bool:
    """Check if user is registered for the course (directly or via cohort).

    Extracted from student_interface.utils.get_is_registered so that
    course_access.backends can call it without creating a dependency cycle
    (student_interface → course_access would be cyclic).

    student_interface.get_is_registered delegates to this function.
    """
    from freedom_ls.student_management.models import (
        CohortCourseRegistration,
        UserCourseRegistration,
    )

    if not user.is_authenticated:
        return False
    direct = UserCourseRegistration.objects.filter(
        user=user, collection=course, is_active=True
    ).exists()
    if direct:
        return True
    cohort = CohortCourseRegistration.objects.filter(
        cohort__cohortmembership__user=user, collection=course, is_active=True
    ).exists()
    return cohort
