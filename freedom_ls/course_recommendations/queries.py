"""Query helpers for course_recommendations."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
    from django.db.models import QuerySet

    from freedom_ls.accounts.models import User
    from freedom_ls.course_recommendations.models import RecommendedCourse

    type RequestUser = User | AnonymousUser | AbstractBaseUser


def get_recommended_courses(user: RequestUser) -> QuerySet[RecommendedCourse]:
    """Get recommended courses for a user. Returns empty queryset for anonymous users."""
    from freedom_ls.course_recommendations.models import RecommendedCourse

    if not user.is_authenticated:
        return RecommendedCourse.objects.none()
    return RecommendedCourse.objects.filter(user=user).select_related("course")
