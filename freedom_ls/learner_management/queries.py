from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, cast

from django.db.models import Exists, Model, OuterRef, Q, QuerySet

from freedom_ls.learner_management.capabilities import (
    _active_role_assignments,
    _current_site,
    _granted_cohorts,
    _granted_organisations,
    _site_grants,
    roles_granting,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
    OrganisationMember,
)
from freedom_ls.organisations.models import Organisation

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
    from django.contrib.sites.models import Site
    from django.db.models import QuerySet

    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course

    type RequestUser = User | AnonymousUser | AbstractBaseUser

VIEW_ORGANISATION = "freedom_ls_organisations.view_organisation"
VIEW_COHORT = "freedom_ls_learner_management.view_cohort"
VIEW_LEARNER = "freedom_ls_learner_management.view_learner"


class ResolvedRegistration(NamedTuple):
    """Which Learner the work lands under, and the registration that decided it.

    The two travel together so no caller can resolve one and re-derive the
    other with a subtly different order.
    """

    learner: Learner
    registration: LearnerCourseRegistration | CohortCourseRegistration


def access_granting_cohort_registrations() -> QuerySet[CohortCourseRegistration]:
    """Cohort registrations that give their members course access.

    CohortCourseRegistration.is_active and Cohort.is_active are checked
    here and nowhere else, so no read site can honour one and forget the
    other.
    """
    return CohortCourseRegistration.objects.filter(
        is_active=True, cohort__is_active=True
    )


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
    from freedom_ls.learner_management.models import LearnerCourseRegistration

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
        access_granting_cohort_registrations().filter(
            course=OuterRef("pk"),
            cohort__cohortmembership__learner__user=cast("User", user),
            cohort__cohortmembership__learner__is_active=True,
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
    cohort_registration = (
        access_granting_cohort_registrations()
        .filter(
            course=course,
            cohort__cohortmembership__learner__user=user,
            cohort__cohortmembership__learner__is_active=True,
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


def _resolved_or_none[ModelT: Model](
    user: RequestUser, everything: QuerySet[ModelT]
) -> QuerySet[ModelT] | None:
    """The prologue every visibility helper below shares: `.none()` for an
    inactive or anonymous user, `everything` for a superuser, or `None` to
    tell the caller to keep resolving through role assignments.
    """
    if not user.is_authenticated or not user.is_active:
        return everything.none()
    if cast("User", user).is_superuser:
        return everything
    return None


def organisations_accessible_to(user: RequestUser) -> QuerySet[Organisation]:
    """Organisations this user may enter.

    Union of two paths: an organisation-level role granting
    freedom_ls_organisations.view_organisation, or a role assignment on any
    cohort inside the organisation granting view_cohort. The second half is
    load-bearing — without it, an educator holding only per-cohort role
    assignments would have no way to reach an organisation-scoped interface
    at all, no matter how many cohorts they hold one on.
    """
    resolved = _resolved_or_none(user, Organisation.objects.all())
    if resolved is not None:
        return resolved.order_by("name")
    user = cast("User", user)

    site = _current_site()
    if site is None:
        return Organisation.objects.none()

    organisation_roles = roles_granting(VIEW_ORGANISATION, site)
    if _site_grants(user, organisation_roles, site).exists():
        return Organisation.objects.filter(site=site).order_by("name")

    cohort_roles = roles_granting(VIEW_COHORT, site)
    return Organisation.objects.filter(
        Q(pk__in=_granted_organisations(user, organisation_roles).values("pk"))
        | Q(pk__in=_granted_cohorts(user, cohort_roles).values("organisation_id"))
    ).order_by("name")


def cohorts_visible_to(
    user: RequestUser, organisation: Organisation
) -> QuerySet[Cohort]:
    """Cohorts within this organisation visible to this user: every cohort
    for a role holder whose role grants view_cohort at site or organisation
    level, otherwise only the ones carrying a role assignment of their own.

    "An organisation role grants every cohort inside it" is an implication no
    row on the covered cohorts themselves can express -- nothing is written
    onto them when the organisation grant is made -- so it is resolved here,
    by checking the organisation itself, rather than by writing a row per
    cohort at grant time.
    """
    within = Cohort.objects.filter(organisation=organisation)
    resolved = _resolved_or_none(user, within)
    if resolved is not None:
        return resolved
    user = cast("User", user)

    roles = roles_granting(VIEW_COHORT, organisation.site)
    if (
        _site_grants(user, roles, organisation.site).exists()
        or _granted_organisations(user, roles).filter(pk=organisation.pk).exists()
    ):
        return within
    return within.filter(pk__in=_granted_cohorts(user, roles).values("pk"))


def all_cohorts_visible_to(user: RequestUser) -> QuerySet[Cohort]:
    """Every cohort this user may see, across every organisation.

    The organisation-unscoped sibling of cohorts_visible_to, for surfaces that
    have no organisation in scope to pass it -- the Django admin, which is
    site-wide. The two must stay in lockstep: same two paths, same answer for
    any one cohort.
    """
    resolved = _resolved_or_none(user, Cohort.objects.all())
    if resolved is not None:
        return resolved
    user = cast("User", user)

    site = _current_site()
    if site is None:
        return Cohort.objects.none()

    roles = roles_granting(VIEW_COHORT, site)
    if _site_grants(user, roles, site).exists():
        return Cohort.objects.filter(site=site)
    return Cohort.objects.filter(
        Q(organisation__in=_granted_organisations(user, roles))
        | Q(pk__in=_granted_cohorts(user, roles).values("pk"))
    )


def can_view_cohort(user: RequestUser, cohort: Cohort) -> bool:
    """Whether this user may see one cohort, by either path.

    Expressed through all_cohorts_visible_to rather than repeating its two
    branches, so a per-object check can never disagree with the queryset that
    populates a list or a dropdown.
    """
    return all_cohorts_visible_to(user).filter(pk=cohort.pk).exists()


def visible_learners_expression(user: User, roles: frozenset[str], site: Site) -> Q:
    """Q on a Learner queryset: rows `user` reaches through an active grant of `roles`.

    A site grant reaches every row on the site and is never gated; an organisation
    or cohort grant counts only through an active OrganisationMember, which the
    _granted_* builders already enforce. The cohort branch goes through pk__in on
    CohortMembership rather than a join, so no caller needs distinct().
    """
    if _site_grants(user, roles, site).exists():
        return Q(site=site)
    return Q(organisation__in=_granted_organisations(user, roles)) | Q(
        pk__in=CohortMembership.objects.filter(
            site=site, cohort__in=_granted_cohorts(user, roles)
        ).values("learner_id")
    )


def learners_visible_to(
    user: RequestUser, organisation: Organisation
) -> QuerySet[Learner]:
    """Learners this person may see within an organisation.

    Every learner in the organisation for a role holder whose role grants
    view_learner at site or organisation level; otherwise only the members of
    cohorts that same role granted them, within this organisation. A
    per-cohort role assignment says nothing about people outside that cohort,
    so widening it to cover every learner in the organisation would hand a
    cohort-scoped educator the whole organisation's roster; only a
    site/organisation-level grant sees both.
    """
    # is_active sits outside the visibility Q: a removed learner must not
    # reappear just because they still hold a membership in a granted cohort,
    # or still belong to the organisation.
    within = Learner.objects.filter(organisation=organisation, is_active=True)
    resolved = _resolved_or_none(user, within)
    if resolved is not None:
        return resolved
    user = cast("User", user)

    roles = roles_granting(VIEW_LEARNER, organisation.site)
    return within.filter(visible_learners_expression(user, roles, organisation.site))


def educators_of(
    learner: Learner,
    *,
    roles: frozenset[str] | None = None,
    through_cohorts: QuerySet | None = None,
    through_organisation_and_site: bool = True,
) -> QuerySet[User]:
    """Active users who are educators of this learner, the inverse of
    learners_visible_to minus its superuser branch.

    `roles` defaults to every role granting VIEW_LEARNER on the learner's site; a
    caller may narrow it to a subset. `through_cohorts` (a values("pk") queryset)
    restricts the cohort branch to those cohorts, and `through_organisation_and_site`
    False drops the organisation and site branches. Narrowing can only remove users,
    so every narrowed answer is a subset of the full one.

    Built from the same grant builders as the forward direction, so a change to the
    gate changes both directions at once. Like the forward direction it ignores the
    learner's own User.is_active and does not exclude the learner's own user.
    """
    from freedom_ls.accounts.models import User

    if not learner.is_active:
        return User.objects.none()
    site = learner.site
    if roles is None:
        roles = roles_granting(VIEW_LEARNER, site)
    # Each _granted_* queryset is the direct argument of an Exists, and inside it
    # _grant_exists and _member_organisations sit one level deeper, so the User row
    # under test is two levels up. Wrapping a builder in a further subquery would
    # silently move `holder` one level too high.
    holder = OuterRef(OuterRef("pk"))
    cohorts = _granted_cohorts(holder, roles).filter(
        site=site, cohortmembership__learner=learner
    )
    if through_cohorts is not None:
        cohorts = cohorts.filter(pk__in=through_cohorts)
    condition: Q | Exists = Exists(cohorts)
    if through_organisation_and_site:
        condition |= Exists(_site_grants(OuterRef("pk"), roles, site)) | Exists(
            _granted_organisations(holder, roles).filter(
                site=site, pk=learner.organisation_id
            )
        )
    return User.objects.filter(site=site, is_active=True).filter(condition)


def colleagues_of(user: User, site: Site) -> QuerySet[User]:
    """Active users, other than `user`, holding an organisation- or cohort-scoped
    VIEW_LEARNER-granting role in an organisation where `user` holds one too.

    A site-scoped role makes nobody a colleague, because one site can hold
    unrelated organisations. Both sides go through the OrganisationMember gate,
    which the _granted_* builders enforce.
    """
    from freedom_ls.accounts.models import User

    roles = roles_granting(VIEW_LEARNER, site)
    shared = Organisation.objects.filter(site=site).filter(
        Q(pk__in=_granted_organisations(user, roles).values("pk"))
        | Q(pk__in=_granted_cohorts(user, roles).values("organisation_id"))
    )
    # Two separate Exists, each wrapping a builder directly, for the nesting reason
    # educators_of explains.
    holder = OuterRef(OuterRef("pk"))
    holds_role_there = Exists(
        _granted_organisations(holder, roles).filter(pk__in=shared.values("pk"))
    ) | Exists(
        _granted_cohorts(holder, roles).filter(organisation__in=shared.values("pk"))
    )
    return (
        User.objects.filter(site=site, is_active=True)
        .exclude(pk=user.pk)
        .filter(holds_role_there)
    )


def is_in_cohort_expression(site: Site, cohorts: QuerySet) -> Exists:
    """Exists() for a Learner queryset: the outer row is a member of one of `cohorts`
    (a values() queryset of cohort ids)."""
    return Exists(
        CohortMembership.objects.filter(
            site=site, learner=OuterRef("pk"), cohort__in=cohorts
        )
    )


def holds_registration_for_any_expression(site: Site, courses: QuerySet) -> Q:
    """Q for a Learner queryset: the outer row holds an active registration for one
    of `courses` (a values() queryset of course ids), individually or through a
    cohort it belongs to.

    Both cohort conditions sit in one filter() call, for the reason
    is_registered_for_course_expression gives: split across two calls, the
    membership and the registration could match different cohorts.
    """
    return Exists(
        LearnerCourseRegistration.objects.filter(
            site=site, learner=OuterRef("pk"), course__in=courses, is_active=True
        )
    ) | Exists(
        CohortCourseRegistration.objects.filter(
            site=site,
            course__in=courses,
            cohort__cohortmembership__learner=OuterRef("pk"),
            is_active=True,
        )
    )


def registrations_of(
    learner: Learner,
) -> tuple[QuerySet[LearnerCourseRegistration], QuerySet[CohortCourseRegistration]]:
    """This learner's active registrations by each path: its own, and those of the
    cohorts it is a member of. Returned separately because each kind carries its
    own configuration."""
    site = learner.site
    return (
        LearnerCourseRegistration.objects.filter(
            site=site, learner=learner, is_active=True
        ),
        CohortCourseRegistration.objects.filter(
            site=site, cohort__cohortmembership__learner=learner, is_active=True
        ),
    )


def peers_through(
    learner: Learner,
    *,
    cohorts: QuerySet,
    own_courses: QuerySet,
    cohort_courses: QuerySet,
) -> QuerySet[Learner]:
    """Other users' active Learner rows in this learner's organisation that are
    members of one of `cohorts`, or hold an active registration for one of
    `own_courses` or `cohort_courses` (each a values() queryset of ids).

    peers_of passes every cohort and course the learner has; a caller that has
    filtered them, by configuration say, passes the survivors and gets the same
    composition, so the two cannot drift. Course peers are restricted to the
    organisation: a course is not owned by one, so without this a client's
    learners would see another client's. All three conditions sit in one
    filter() call, for the reason holds_registration_for_any_expression gives.
    """
    site = learner.site
    return (
        Learner.objects.filter(
            site=site, organisation_id=learner.organisation_id, is_active=True
        )
        .exclude(user_id=learner.user_id)
        .filter(
            is_in_cohort_expression(site, cohorts)
            | holds_registration_for_any_expression(site, own_courses)
            | holds_registration_for_any_expression(site, cohort_courses)
        )
    )


def peers_of(learner: Learner) -> QuerySet[Learner]:
    """Other users' active Learner rows in this learner's organisation that share
    a cohort with it, or share a course both hold an active registration for."""
    if not learner.is_active:
        return Learner.objects.none()
    cohorts = CohortMembership.objects.filter(
        site=learner.site, learner=learner
    ).values("cohort_id")
    own, through_cohorts = registrations_of(learner)
    return peers_through(
        learner,
        cohorts=cohorts,
        own_courses=own.values("course_id"),
        cohort_courses=through_cohorts.values("course_id"),
    )


def active_organisation_admins(organisation: Organisation) -> QuerySet[User]:
    """Active organisation_admin role holders currently helping run this
    organisation, ordered by name.

    Gated on an active OrganisationMember the same way can() gates every
    organisation- or cohort-level grant: a deactivated member must not be
    named as someone to ask just because their role assignment is still
    active.
    """
    from freedom_ls.accounts.models import User

    grants = _active_role_assignments(
        Organisation, frozenset({"organisation_admin"})
    ).filter(object_id=str(organisation.pk))
    members = OrganisationMember.objects.filter(
        organisation=organisation, is_active=True
    )
    return (
        User.objects.filter(is_active=True)
        .filter(pk__in=grants.values("user_id"))
        .filter(pk__in=members.values("user_id"))
        .order_by("first_name", "last_name")
    )
