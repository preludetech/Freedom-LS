"""Helpers shared by tests that need a registered learner."""

from __future__ import annotations

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)


def register_user_for_course(course: Course, user: User | None = None) -> User:
    """Register a user (creating one if not given) for `course`; return the user."""
    resolved_user: User = UserFactory() if user is None else user
    learner = LearnerFactory(user=resolved_user)
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=True)
    return resolved_user
