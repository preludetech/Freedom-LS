from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.db import transaction

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
    from django.contrib.sites.models import Site

    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course
    from freedom_ls.learner_management.models import (
        Cohort,
        CohortCourseRegistration,
        Learner,
        OrganisationMember,
    )
    from freedom_ls.organisations.models import Organisation

    type RequestUser = User | AnonymousUser | AbstractBaseUser


def is_registered_for_course(user: RequestUser, course: Course) -> bool:
    """Check if user is registered for the course (directly or via cohort).

    Extracted from learner_interface.utils.get_is_registered so that
    course_access.backends can call it without creating a dependency cycle
    (learner_interface → course_access would be cyclic).

    learner_interface.get_is_registered delegates to this function.
    """
    from freedom_ls.learner_management.models import LearnerCourseRegistration
    from freedom_ls.learner_management.queries import (
        access_granting_cohort_registrations,
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
    cohort = (
        access_granting_cohort_registrations()
        .filter(
            cohort__cohortmembership__learner__user=cast("User", user),
            cohort__cohortmembership__learner__is_active=True,
            course=course,
        )
        .exists()
    )
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


def ensure_organisation_member(
    user: User, organisation: Organisation
) -> OrganisationMember:
    """Get or create the OrganisationMember recording that a user helps run
    an organisation's learners.

    Idempotent, but unlike ensure_learner it never reactivates an existing
    row: a deactivated member must stay deactivated until someone explicitly
    reactivates them, so a fresh grant on the organisation cannot silently
    undo that decision.

    _base_manager, not objects: SiteAwareManager.get_queryset() ANDs the
    ambient thread-local site onto every lookup when a request exists, and
    the organisation being handled here is not always the Site the current
    request is for. Using the site-aware manager would make the lookup half
    of get_or_create miss an existing row under a foreign ambient site,
    attempting a second INSERT and hitting unique_member_per_organisation
    instead of finding the row that already exists.
    """
    from freedom_ls.learner_management.models import OrganisationMember

    member, _ = OrganisationMember._base_manager.get_or_create(
        site=organisation.site,
        user=user,
        organisation=organisation,
        defaults={"is_active": True},
    )
    return member


def learner_webhook_payload(learner: Learner) -> dict[str, object]:
    """The fields every learner event's payload opens with."""
    user = learner.user
    return {
        "user_id": user.pk,
        "user_email": user.email,
        "organisation_id": str(learner.organisation_id),
        "learner_id": str(learner.pk),
    }


def fire_webhook_event_on_commit(
    event_type: str, payload: dict[str, object], site: Site
) -> None:
    """Every learner-management event fires once the transaction it belongs
    to has committed, so an integrator never hears about a rolled-back change."""
    from freedom_ls.webhooks.events import fire_webhook_event

    transaction.on_commit(lambda: fire_webhook_event(event_type, payload, site=site))


def announce_cohort_registration_change(registration: CohortCourseRegistration) -> None:
    """Tell integrators a cohort registration changed. Called only by a
    change, never by a no-op save."""
    cohort = registration.cohort
    event_type = (
        "cohort.course_registered"
        if registration.is_active
        else "cohort.course_unregistered"
    )
    fire_webhook_event_on_commit(
        event_type,
        {
            "organisation_id": str(cohort.organisation_id),
            "cohort_id": str(cohort.pk),
            "course_id": str(registration.course_id),
            "course_title": registration.course.title,
        },
        cohort.site,
    )


def register_cohort_for_course(
    cohort: Cohort, course: Course
) -> CohortCourseRegistration:
    """Register, or re-register, the cohort for the course.

    Reuses the row the unique constraint allows per cohort and course,
    and saves through save() so the post_save fan-out mints a course
    progress record for every member the row does not yet cover.
    """
    from freedom_ls.learner_management.models import CohortCourseRegistration
    from freedom_ls.learner_management.queries import (
        COURSE_NOT_OPEN_MESSAGE,
        is_course_open_to_organisation,
    )

    if not is_course_open_to_organisation(course, cohort.organisation):
        raise ValueError(COURSE_NOT_OPEN_MESSAGE)
    # _base_manager with an explicit site, as ensure_learner does: the
    # site-aware manager only fills site from an ambient request, and this
    # runs from commands and tests as well as views.
    registration, created = CohortCourseRegistration._base_manager.get_or_create(
        site=cohort.site, cohort=cohort, course=course
    )
    reactivated = not created and not registration.is_active
    if reactivated:
        registration.is_active = True
        registration.save(update_fields=["is_active"])
    if created or reactivated:
        announce_cohort_registration_change(registration)
    return registration


def unregister_cohort_from_course(registration: CohortCourseRegistration) -> None:
    """Withdraw the registration. Reversible: the row and every course
    progress record it minted stay."""
    was_active = registration.is_active
    registration.is_active = False
    registration.save(update_fields=["is_active"])
    if was_active:
        announce_cohort_registration_change(registration)
