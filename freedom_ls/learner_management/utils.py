from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course
    from freedom_ls.learner_management.models import Learner
    from freedom_ls.organisations.models import Organisation

    type RequestUser = User | AnonymousUser | AbstractBaseUser


def is_registered_for_course(user: RequestUser, course: Course) -> bool:
    """Check if user is registered for the course (directly or via cohort).

    Extracted from learner_interface.utils.get_is_registered so that
    course_access.backends can call it without creating a dependency cycle
    (learner_interface → course_access would be cyclic).

    learner_interface.get_is_registered delegates to this function.
    """
    from freedom_ls.learner_management.models import (
        CohortCourseRegistration,
        LearnerCourseRegistration,
    )

    if not user.is_authenticated:
        return False
    direct = LearnerCourseRegistration.objects.filter(
        learner__user=user, learner__is_active=True, course=course, is_active=True
    ).exists()
    if direct:
        return True
    # Both cohort conditions must sit in one filter() call: several conditions
    # on a multi-valued relation within one filter() apply to the same joined
    # row, but split across two calls they can match different rows of the
    # cohort's memberships -- so a cohort holding this user's removed Learner
    # alongside a second, active Learner would otherwise grant access.
    cohort = CohortCourseRegistration.objects.filter(
        cohort__cohortmembership__learner__user=user,
        cohort__cohortmembership__learner__is_active=True,
        course=course,
        is_active=True,
    ).exists()
    return cohort


def ensure_learner(user: User, organisation: Organisation) -> Learner:
    """Get or create the Learner recording a user's association with an organisation.

    Idempotent, and reactivates a row that was previously removed: a fresh
    enrolment is a live signal of re-association.

    _base_manager, not objects: SiteAwareManager.get_queryset() ANDs the
    ambient thread-local site onto every lookup when a request exists, and
    the organisation being handled here is not always the Site the current
    request is for. Using the site-aware manager would make the lookup half
    of update_or_create miss an existing row under a foreign ambient site,
    attempting a second INSERT and hitting unique_learner_per_organisation
    instead of finding the row that already exists.
    """
    from freedom_ls.learner_management.models import Learner

    learner, _ = Learner._base_manager.update_or_create(
        site=organisation.site,
        user=user,
        organisation=organisation,
        defaults={"is_active": True},
    )
    return learner
