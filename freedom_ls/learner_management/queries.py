from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, cast

from guardian.shortcuts import get_objects_for_user

from django.db.models import Exists, OuterRef, Q

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
    from django.db.models import QuerySet

    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course
    from freedom_ls.learner_management.models import (
        Cohort,
        CohortCourseRegistration,
        Learner,
        LearnerCourseRegistration,
    )
    from freedom_ls.organisations.models import Organisation

    type RequestUser = User | AnonymousUser | AbstractBaseUser


class ResolvedRegistration(NamedTuple):
    """Which Learner the work lands under, and the registration that decided it.

    The two travel together so no caller can resolve one and re-derive the
    other with a subtly different order.
    """

    learner: Learner
    registration: LearnerCourseRegistration | CohortCourseRegistration


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
            course=OuterRef("pk"),
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
            course=OuterRef("pk"),
            cohort__cohortmembership__learner__user=user,
            cohort__cohortmembership__learner__is_active=True,
            is_active=True,
        )
    )


def latest_registration(user: User, course: Course) -> LearnerCourseRegistration | None:
    """Most recent active registration, else most recent of any status.

    A learner can hold more than one registration for the same course, one
    per organisation. Callers that need a single row rather than the full
    set order by ``(-is_active, -learner__is_active, -registered_at)`` in one
    query: a descending boolean sorts every active row ahead of every
    inactive one, so recency only breaks ties within whichever group is
    present.

    ``learner__is_active`` sits second rather than being filtered on. The
    access checks require both flags, so sorting on both in that order puts
    an access-granting row first whenever one exists -- without it, a user
    holding an active registration through a live Learner and another
    through a removed one would resolve to whichever was registered later,
    and the record keying their work could land under the removed Learner.
    Filtering instead would cut a removed learner off from their own
    deadlines, which the individual branch deliberately still reaches.
    """
    from freedom_ls.learner_management.models import LearnerCourseRegistration

    return (
        LearnerCourseRegistration.objects.filter(learner__user=user, course=course)
        .select_related("learner__organisation")
        .order_by("-is_active", "-learner__is_active", "-registered_at")
        .first()
    )


def learner_for_course(user: User, course: Course) -> ResolvedRegistration | None:
    """Which Learner a piece of work for this (user, course) lands under, and
    the registration that decided it.

    Cohort registration wins over an individual one. Where a learner holds
    two cohort registrations for one course, the tiebreak below picks one
    deterministically -- without it a learner in two cohorts that both hold
    an active registration for this course would land on whichever record
    the query planner happened to return.
    """
    from freedom_ls.learner_management.models import CohortCourseRegistration, Learner

    cohort_registration = (
        CohortCourseRegistration.objects.filter(
            course=course,
            cohort__cohortmembership__learner__user=user,
            cohort__cohortmembership__learner__is_active=True,
            is_active=True,
        )
        .select_related("cohort__organisation")
        .order_by("-is_active", "-registered_at")
        .first()
    )
    if cohort_registration is not None:
        # .first(), not .get(): CohortMembership.clean() forbids a
        # cross-organisation membership, but factories never call
        # full_clean(), so a test-built row can link a Learner the
        # site-aware manager below cannot see. Falling through to the
        # individual branch is the safe answer there.
        learner = (
            Learner.objects.filter(
                user=user,
                is_active=True,
                cohortmembership__cohort_id=cohort_registration.cohort_id,
            )
            .select_related("organisation")
            .first()
        )
        if learner is not None:
            return ResolvedRegistration(learner, cohort_registration)

    registration = latest_registration(user, course)
    if registration is None:
        return None
    return ResolvedRegistration(registration.learner, registration)


def organisation_for_learner_course(user: User, course: Course) -> Organisation | None:
    """The organisation a learner is studying this course through.

    Re-expressed on top of learner_for_course so the two can never disagree
    on the tiebreak. This returns learner.organisation where the old cohort
    branch returned cohort.organisation -- the same organisation, since
    CohortMembership.clean() forbids a cross-organisation membership.
    """
    resolved = learner_for_course(user, course)
    return resolved.learner.organisation if resolved is not None else None


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


def learners_visible_to(
    user: RequestUser, organisation: Organisation
) -> QuerySet[Learner]:
    """Learners this person may see within an organisation.

    Built on cohorts_visible_to — cohort visibility is never re-derived here.
    Members of visible cohorts, plus, for an organisation-role holder only,
    learners associated with the organisation. A per-cohort guardian grant
    says nothing about people outside that cohort, so widening it to cover
    every learner in the organisation would hand a cohort-scoped educator the
    whole organisation's roster; only an organisation-role holder sees both.
    """
    from freedom_ls.learner_management.models import Learner

    if not user.is_authenticated:
        return Learner.objects.none()

    visible = Q(cohortmembership__cohort__in=cohorts_visible_to(user, organisation))
    if cast("User", user).has_perm(
        "freedom_ls_organisations.view_organisation", organisation
    ):
        visible |= Q(organisation=organisation)
    # is_active sits outside both branches: a removed learner must not
    # reappear just because they still hold a membership in a visible
    # cohort, or still belong to the organisation.
    return Learner.objects.filter(visible, is_active=True).distinct()
