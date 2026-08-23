from __future__ import annotations

from typing import TYPE_CHECKING, cast

from guardian.shortcuts import get_objects_for_user

from django.db.models import Exists, OuterRef, Q

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
    from django.db.models import QuerySet

    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course
    from freedom_ls.learner_management.models import Cohort, LearnerCourseRegistration
    from freedom_ls.organisations.models import Organisation

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
    from freedom_ls.learner_management.models import (
        CohortCourseRegistration,
        LearnerCourseRegistration,
    )

    return Exists(
        LearnerCourseRegistration.objects.filter(
            collection=OuterRef("pk"),
            learner__user=user,
            learner__is_active=True,
            is_active=True,
        )
    ) | Exists(
        # Both cohort conditions must sit in this one filter() call -- see
        # is_registered_for_course (utils.py) for why a split would leak
        # access through a cohort holding both a removed and an active
        # Learner for this user.
        CohortCourseRegistration.objects.filter(
            collection=OuterRef("pk"),
            cohort__cohortmembership__learner__user=user,
            cohort__cohortmembership__learner__is_active=True,
            is_active=True,
        )
    )


def latest_registration(user: User, course: Course) -> LearnerCourseRegistration | None:
    """Most recent active registration, else most recent of any status.

    A learner can hold more than one registration for the same course, one
    per organisation. Callers that need a single row rather than the full
    set order by ``(-is_active, -registered_at)`` in one query: a descending
    boolean sorts every active row ahead of every inactive one, so recency
    only breaks ties within whichever group is present.
    """
    from freedom_ls.learner_management.models import LearnerCourseRegistration

    return (
        LearnerCourseRegistration.objects.filter(learner__user=user, collection=course)
        .select_related("learner__organisation")
        .order_by("-is_active", "-registered_at")
        .first()
    )


def organisation_for_learner_course(user: User, course: Course) -> Organisation | None:
    """The organisation a learner is studying this course through.

    Cohort registration wins over an individual one. CohortCourseRegistration
    has no organisation FK of its own, so it is reached through the cohort.
    Where a learner holds two individual registrations for one course through
    two organisations, latest_registration's tiebreak picks one.

    One query per path, with select_related — never one per render.
    """
    from freedom_ls.learner_management.models import CohortCourseRegistration

    cohort_registration: CohortCourseRegistration | None = (
        CohortCourseRegistration.objects.filter(
            collection=course,
            cohort__cohortmembership__learner__user=user,
            cohort__cohortmembership__learner__is_active=True,
            is_active=True,
        )
        .select_related("cohort__organisation")
        .first()
    )
    if cohort_registration is not None:
        return cohort_registration.cohort.organisation

    registration = latest_registration(user, course)
    return registration.learner.organisation if registration is not None else None


def organisations_accessible_to(user: RequestUser) -> QuerySet[Organisation]:
    """Organisations this user may enter.

    Union of two paths: an organisation role, or a per-cohort guardian grant
    on any cohort inside the organisation. The second half is load-bearing —
    without it, an educator holding only per-cohort grants would have no way
    to reach an organisation-scoped interface at all, no matter how many
    cohorts they hold a grant on.
    """
    from freedom_ls.learner_management.models import Cohort
    from freedom_ls.organisations.models import Organisation

    if not user.is_authenticated:
        return Organisation.objects.none()

    by_role = get_objects_for_user(
        user, "freedom_ls_organisations.view_organisation", klass=Organisation
    )
    granted_cohorts = get_objects_for_user(user, "view_cohort", klass=Cohort)
    return Organisation.objects.filter(
        Q(pk__in=by_role.values("pk"))
        | Q(pk__in=granted_cohorts.values("organisation_id"))
    ).order_by("name")


def cohorts_visible_to(
    user: RequestUser, organisation: Organisation
) -> QuerySet[Cohort]:
    """Cohorts within this organisation visible to this user: every cohort
    for an organisation-role holder, otherwise only the ones carrying a
    per-cohort guardian grant.

    This is the explicit join guardian cannot express on its own.
    sync_user_object_permissions filters a role's permissions down to the
    ones matching the *target object's* content type
    (role_based_permissions/utils.py), so a role assigned on an Organisation
    can only ever sync freedom_ls_organisations.* permissions onto guardian —
    never freedom_ls_learner_management.view_cohort. "An organisation role
    grants every cohort inside it" is therefore performed here, in Python,
    rather than by widening what guardian syncs.
    """
    from freedom_ls.learner_management.models import Cohort

    if not user.is_authenticated:
        return Cohort.objects.none()

    within = Cohort.objects.filter(organisation=organisation)
    # is_authenticated guard above excludes AnonymousUser too (its
    # is_authenticated is a hardcoded False), so this is a real User.
    if cast("User", user).has_perm(
        "freedom_ls_organisations.view_organisation", organisation
    ):
        return within
    return within.filter(
        pk__in=get_objects_for_user(user, "view_cohort", klass=Cohort).values("pk")
    )


def all_cohorts_visible_to(user: RequestUser) -> QuerySet[Cohort]:
    """Every cohort this user may see, across every organisation.

    The organisation-unscoped sibling of cohorts_visible_to, for surfaces that
    have no organisation in scope to pass it -- the Django admin, which is
    site-wide. The two must stay in lockstep: same two paths, same answer for
    any one cohort.
    """
    from freedom_ls.learner_management.models import Cohort
    from freedom_ls.organisations.models import Organisation as OrganisationModel

    if not user.is_authenticated:
        return Cohort.objects.none()

    by_role_organisations = get_objects_for_user(
        user, "freedom_ls_organisations.view_organisation", klass=OrganisationModel
    )
    return Cohort.objects.filter(
        Q(organisation__in=by_role_organisations)
        | Q(pk__in=get_objects_for_user(user, "view_cohort", klass=Cohort).values("pk"))
    )


def can_view_cohort(user: RequestUser, cohort: Cohort) -> bool:
    """Whether this user may see one cohort, by either path.

    Expressed through all_cohorts_visible_to rather than repeating its two
    branches, so a per-object check can never disagree with the queryset that
    populates a list or a dropdown.
    """
    return all_cohorts_visible_to(user).filter(pk=cohort.pk).exists()


def users_visible_to(user: RequestUser, organisation: Organisation) -> QuerySet[User]:
    """Users this person may see within an organisation.

    Built on cohorts_visible_to — cohort visibility is never re-derived here.
    Members of visible cohorts, plus, for an organisation-role holder only,
    learners who hold an individual registration in the organisation and
    belong to no cohort at all. A per-cohort guardian grant says nothing
    about people outside that cohort, so widening it to cover individual
    learners would hand a cohort-scoped educator the whole organisation's
    roster of individually-registered learners; only an organisation-role
    holder sees both.
    """
    from freedom_ls.accounts.models import User

    if not user.is_authenticated:
        return User.objects.none()

    visible = Q(cohortmembership__cohort__in=cohorts_visible_to(user, organisation))
    if cast("User", user).has_perm(
        "freedom_ls_organisations.view_organisation", organisation
    ):
        visible |= Q(usercourseregistration__organisation=organisation)
    return User.objects.filter(visible).distinct()
