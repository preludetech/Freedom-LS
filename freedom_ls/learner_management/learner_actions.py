"""The single seam for each learner administration action: one transaction,
no request, webhook events on commit only when something changed."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from uuid import UUID, uuid4

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Model, TextChoices
from django.db.models.functions import Lower

from freedom_ls.accounts.account_setup import (
    EmailInUseOnAnotherSite,
    lookup_user,
    match_or_create_user,
    send_account_setup_email,
)
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.types import JSONValue
from freedom_ls.audit_log.writer import record_entry
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.models import (
    Cohort,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import require_course_open_to
from freedom_ls.learner_management.signals import cohort_membership_moved
from freedom_ls.learner_management.utils import (
    ensure_learner,
    fire_webhook_event_on_commit,
    learner_webhook_payload,
    record_cohort_entry,
)
from freedom_ls.organisations.models import Organisation


def _fire(
    event_type: str, learner: Learner, extra: dict[str, object] | None = None
) -> None:
    fire_webhook_event_on_commit(
        event_type, {**learner_webhook_payload(learner), **(extra or {})}, learner.site
    )


def _set_learner_active(learner: Learner, is_active: bool, event_type: str) -> bool:
    """Flip `Learner.is_active`; False when the learner was already in that state."""
    with transaction.atomic():
        locked = Learner._base_manager.select_for_update().get(pk=learner.pk)
        if locked.is_active == is_active:
            return False
        locked.is_active = is_active
        locked.save(update_fields=["is_active"])
        learner.is_active = is_active
        _fire(event_type, locked)
    return True


def record_learner_entry(
    learner: Learner,
    action: str,
    actor: User | None,
    *,
    reason: str = "",
    subjects: Iterable[Model] = (),
    details: Mapping[str, JSONValue] | None = None,
) -> None:
    """Write an entry whose target is the learner, labelled by their user's
    display name and scoped to their organisation."""
    record_entry(
        action=action,
        actor=actor,
        target=learner,
        target_label=learner.user.display_name,
        organisation=learner.organisation,
        subjects=subjects,
        reason=reason,
        details=details,
    )


def _change_learner_state(
    learner: Learner,
    is_active: bool,
    action: str,
    event_type: str,
    actor: User | None,
    reason: str,
) -> bool:
    """Flip `Learner.is_active` and record `action`, in one transaction;
    False, writing nothing, when the learner was already in that state."""
    with transaction.atomic():
        if not _set_learner_active(learner, is_active, event_type=event_type):
            return False
        record_learner_entry(learner, action, actor, reason=reason)
    return True


def deactivate_learner(
    learner: Learner, *, actor: User | None = None, reason: str = ""
) -> bool:
    """Remove the learner's access. Registrations, memberships and course
    progress records are kept."""
    return _change_learner_state(
        learner, False, "learner.deactivated", "learner.deactivated", actor, reason
    )


def reactivate_learner(
    learner: Learner, *, actor: User | None = None, reason: str = ""
) -> bool:
    return _change_learner_state(
        learner, True, "learner.reactivated", "learner.reactivated", actor, reason
    )


def _set_cohort_active(
    cohort: Cohort, is_active: bool, actor: User | None, reason: str
) -> bool:
    """Flip `Cohort.is_active` and record the change, in one transaction;
    False, writing nothing, when the cohort was already in that state.

    Works on `_base_manager` under a row lock, as `_set_learner_active` does:
    this also runs from a task, where no ambient site exists for the
    site-aware manager to read. The lock also stops two overlapping calls
    each writing an entry for the one change.
    """
    with transaction.atomic():
        locked = Cohort._base_manager.select_for_update().get(pk=cohort.pk)
        if locked.is_active == is_active:
            return False
        locked.is_active = is_active
        locked.save(update_fields=["is_active", "updated_at"])
        cohort.is_active = is_active
        record_cohort_entry(
            locked,
            "cohort.reactivated" if is_active else "cohort.deactivated",
            actor,
            reason=reason,
        )
    return True


def deactivate_cohort(
    cohort: Cohort, *, actor: User | None = None, reason: str = ""
) -> bool:
    """Stop the cohort's registrations giving access. Memberships and
    progress are kept."""
    return _set_cohort_active(cohort, False, actor, reason)


def reactivate_cohort(
    cohort: Cohort, *, actor: User | None = None, reason: str = ""
) -> bool:
    return _set_cohort_active(cohort, True, actor, reason)


def check_cohort_for(organisation_id: UUID, cohort: Cohort) -> None:
    """ValueError for an inactive cohort or one in another organisation."""
    if cohort.organisation_id != organisation_id:
        raise ValueError(
            "The cohort belongs to another organisation, so it is not an "
            "active cohort of the organisation."
        )
    if not cohort.is_active:
        raise ValueError(
            "The cohort is inactive, so it is not an active cohort of the organisation."
        )


def _check_cohort(learner: Learner, cohort: Cohort) -> None:
    check_cohort_for(learner.organisation_id, cohort)


def _cohort_payload(cohort: Cohort, move_id: str | None = None) -> dict[str, object]:
    return {"cohort_id": str(cohort.pk), "cohort_name": cohort.name, "move_id": move_id}


def remove_from_cohort(
    learner: Learner, cohort: Cohort, *, actor: User | None = None, reason: str = ""
) -> bool:
    """Take the learner out of an active cohort of their organisation; False
    when they were not a member. Course progress records are kept."""
    _check_cohort(learner, cohort)
    with transaction.atomic():
        deleted, _ = CohortMembership._base_manager.filter(
            learner=learner, cohort=cohort
        ).delete()
        if deleted:
            _fire("cohort_membership.removed", learner, _cohort_payload(cohort))
            record_learner_entry(
                learner,
                "cohort_membership.removed",
                actor,
                reason=reason,
                subjects=[cohort],
                details={"cohort": cohort.name},
            )
    return bool(deleted)


def _add_membership(learner: Learner, cohort: Cohort) -> bool:
    """Make the learner a member and fire the webhook; False when they
    already were. Writes no audit entry: callers decide what the change is."""
    _check_cohort(learner, cohort)
    with transaction.atomic():
        _, created = CohortMembership._base_manager.get_or_create(
            site=learner.site, learner=learner, cohort=cohort
        )
        if created:
            _fire("cohort_membership.added", learner, _cohort_payload(cohort))
    return created


def add_to_cohort(
    learner: Learner, cohort: Cohort, *, actor: User | None = None, reason: str = ""
) -> bool:
    """Make the learner a member of an active cohort of their organisation;
    False when they already were. Registrations the cohort holds start giving
    them access through the membership's own signals."""
    with transaction.atomic():
        created = _add_membership(learner, cohort)
        if created:
            record_learner_entry(
                learner,
                "cohort_membership.added",
                actor,
                reason=reason,
                subjects=[cohort],
                details={"cohort": cohort.name},
            )
    return created


def move_between_cohorts(
    learner: Learner,
    source: Cohort,
    destination: Cohort,
    *,
    actor: User | None = None,
    reason: str = "",
) -> str:
    """Move the learner from one active cohort to another of their
    organisation in one transaction, and return the `move_id` that ties the
    removed and added events together. Raises ValueError, changing nothing,
    when the cohorts are the same, either is unusable, the learner is not in
    the source or is already in the destination."""
    if source.pk == destination.pk:
        raise ValueError("The source and destination cohorts are the same.")
    _check_cohort(learner, source)
    _check_cohort(learner, destination)
    move_id = str(uuid4())
    with transaction.atomic():
        Learner._base_manager.select_for_update().get(pk=learner.pk)
        deleted, _ = CohortMembership._base_manager.filter(
            learner=learner, cohort=source
        ).delete()
        if not deleted:
            raise ValueError("The learner is not a member of the source cohort.")
        # Checked before the create so the refusal is a ValueError, not an
        # integrity error.
        if CohortMembership._base_manager.filter(
            learner=learner, cohort=destination
        ).exists():
            raise ValueError(
                "The learner is already a member of the destination cohort."
            )
        CohortMembership._base_manager.create(
            site=learner.site, learner=learner, cohort=destination
        )
        cohort_membership_moved.send(
            sender=Learner, learner=learner, source=source, destination=destination
        )
        _fire("cohort_membership.removed", learner, _cohort_payload(source, move_id))
        _fire("cohort_membership.added", learner, _cohort_payload(destination, move_id))
        record_learner_entry(
            learner,
            "cohort_membership.moved",
            actor,
            reason=reason,
            subjects=[source, destination],
            details={
                "source": source.name,
                "destination": destination.name,
                "move_id": move_id,
            },
        )
    return move_id


def register_for_course(
    learner: Learner, course: Course, *, actor: User | None = None, reason: str = ""
) -> bool:
    """Give the learner an individual registration for the course,
    reactivating an inactive one; False when an active one already exists.
    The `registration.added` or `registration.reactivated` webhook comes from
    the registration's `post_save` receiver. Raises CourseNotOpenError when
    the course is not open to the learner's organisation."""
    require_course_open_to(course, learner.organisation)
    with transaction.atomic():
        change = _ensure_registration(learner, course, self_registered=False)
        if change is None:
            return False
        record_learner_entry(
            learner, change, actor, reason=reason, details={"course": course.title}
        )
    return True


def _ensure_registration(
    learner: Learner, course: Course, *, self_registered: bool
) -> str | None:
    """Give the learner an active individual registration for the course and
    name what changed: `registration.added`, `registration.reactivated`, or
    None when an active one already existed. Runs inside the caller's
    transaction. `self_registered` only applies to a row created here:
    reactivating an admin's registration doesn't change who made it."""
    # Locked so two overlapping calls cannot each see no active
    # registration and each write an entry for the one change.
    Learner._base_manager.select_for_update().get(pk=learner.pk)
    registration, created = LearnerCourseRegistration._base_manager.get_or_create(
        site=learner.site,
        learner=learner,
        course=course,
        defaults={"self_registered": self_registered},
    )
    if created:
        return "registration.added"
    if registration.is_active:
        return None
    registration.is_active = True
    registration.save(update_fields=["is_active"])
    return "registration.reactivated"


def self_register(user: User, organisation: Organisation, course: Course) -> bool:
    """The learner's own registration for a course open to the organisation:
    makes them a learner of it, reactivating a deactivated one, and gives
    them an individual registration, reactivating an inactive one. True when
    the registration was created. The log records staff actions, so a new
    self-registration writes nothing; a reactivation undoes a staff action,
    so it is written, as the system. Raises CourseNotOpenError when the
    course is not open to the organisation."""
    require_course_open_to(course, organisation)
    details: dict[str, JSONValue] = {"course": course.title, "self_service": True}
    with transaction.atomic():
        existing = Learner._base_manager.filter(
            user=user, organisation=organisation
        ).first()
        learner = ensure_learner(user, organisation)
        if existing is not None and not existing.is_active:
            record_learner_entry(learner, "learner.reactivated", None, details=details)
        change = _ensure_registration(learner, course, self_registered=True)
        if change == "registration.reactivated":
            record_learner_entry(learner, change, None, details=details)
    return change == "registration.added"


def deactivate_registration(
    learner: Learner, course: Course, *, actor: User | None = None, reason: str = ""
) -> bool:
    """Deactivate the learner's individual registration for the course; False
    when they hold no active one. Course progress records are kept. The
    `registration.deactivated` webhook comes from the registration's
    `post_save` receiver."""
    with transaction.atomic():
        Learner._base_manager.select_for_update().get(pk=learner.pk)
        registration = LearnerCourseRegistration._base_manager.filter(
            learner=learner, course=course, is_active=True
        ).first()
        if registration is None:
            return False
        registration.is_active = False
        registration.save(update_fields=["is_active"])
        record_learner_entry(
            learner,
            "registration.deactivated",
            actor,
            reason=reason,
            details={"course": course.title},
        )
    return True


@dataclass(frozen=True)
class LearnerEntry:
    email: str
    first_name: str = ""
    last_name: str = ""


class AddOutcome(TextChoices):
    CREATED = "created", "Account created and setup email sent"
    JOINED = "joined", "Joined the organisation"
    REACTIVATED = "reactivated", "Reactivated"
    ALREADY_LEARNER = "already_learner", "Already a learner here"
    INVALID_EMAIL = "invalid_email", "Not a valid email address"
    EMAIL_IN_USE_ELSEWHERE = (
        "email_in_use_elsewhere",
        "This address is in use on another site",
    )


class CohortOutcome(TextChoices):
    ADDED = "added", "Added to the cohort"
    ALREADY_MEMBER = "already_member", "Already in the cohort"


@dataclass(frozen=True)
class AddLearnerResult:
    email: str
    outcome: AddOutcome
    learner: Learner | None = None
    cohort_outcome: CohortOutcome | None = None


def decide_add(
    *,
    user: User | None,
    learner: Learner | None,
    learner_is_active: bool,
    is_member: bool,
    cohort_given: bool,
) -> tuple[AddOutcome, CohortOutcome | None]:
    """What adding a valid address does, from what already exists: the matched
    user (none when the address is new), the organisation's learner row for
    them (none when they have never been one), whether that row is active and
    whether they are already in the cohort. Pure, so the preview and the
    commit cannot disagree."""
    if user is None:
        outcome = AddOutcome.CREATED
    elif learner is None:
        outcome = AddOutcome.JOINED
    elif not learner_is_active:
        outcome = AddOutcome.REACTIVATED
    else:
        outcome = AddOutcome.ALREADY_LEARNER
    if not cohort_given:
        return outcome, None
    if is_member:
        return outcome, CohortOutcome.ALREADY_MEMBER
    return outcome, CohortOutcome.ADDED


@dataclass(frozen=True)
class ImportLookup:
    """Everything `decide_add` needs for a whole file, loaded in a fixed number
    of queries and keyed by lower-cased email."""

    users: dict[str, User]
    learners: dict[int, Learner]
    member_user_ids: set[int]

    @classmethod
    def build(
        cls,
        organisation: Organisation,
        emails: Iterable[str],
        cohort: Cohort | None,
    ) -> ImportLookup:
        # Users are matched across every site on purpose: an address on another
        # site must be refused, which lookup_user does one address at a time.
        # Learners and memberships are filtered on the organisation, which fixes
        # the site, so the same builder serves the request and a task.
        addresses = {email.strip().lower() for email in emails}
        users: dict[str, User] = {
            user.email.lower(): user
            for user in User._base_manager.annotate(lowered=Lower("email")).filter(
                lowered__in=addresses
            )
        }
        learners = {
            learner.user_id: learner
            for learner in Learner._base_manager.filter(
                organisation=organisation, user__in=users.values()
            )
        }
        member_user_ids: set[int] = set()
        if cohort is not None:
            member_user_ids = set(
                CohortMembership._base_manager.filter(
                    cohort=cohort, learner__in=learners.values()
                ).values_list("learner__user_id", flat=True)
            )
        return cls(users, learners, member_user_ids)


def add_learner(
    organisation: Organisation,
    entry: LearnerEntry,
    cohort: Cohort | None,
    *,
    actor: User | None = None,
    reason: str = "",
) -> AddLearnerResult:
    """Make one address a learner of the organisation and put them in the
    cohort when one is given. Raises ValueError, before touching anything,
    when the cohort is not an active cohort of the organisation."""
    if cohort is not None:
        check_cohort_for(organisation.pk, cohort)
    email = entry.email.strip()
    try:
        validate_email(email)
    except ValidationError:
        return AddLearnerResult(email, AddOutcome.INVALID_EMAIL)
    try:
        user, account_created = match_or_create_user(
            organisation.site, email, entry.first_name, entry.last_name
        )
    except EmailInUseOnAnotherSite:
        return AddLearnerResult(email, AddOutcome.EMAIL_IN_USE_ELSEWHERE)

    existing = Learner._base_manager.filter(
        user=user, organisation=organisation
    ).first()
    is_member = (
        cohort is not None
        and existing is not None
        and CohortMembership._base_manager.filter(
            learner=existing, cohort=cohort
        ).exists()
    )
    outcome, cohort_outcome = decide_add(
        user=None if account_created else user,
        learner=existing,
        learner_is_active=existing is not None and existing.is_active,
        is_member=is_member,
        cohort_given=cohort is not None,
    )
    if existing is None:
        learner = ensure_learner(user, organisation)
        _fire("learner.added", learner, {"account_created": account_created})
    else:
        learner = existing
        if outcome == AddOutcome.REACTIVATED:
            _set_learner_active(existing, True, event_type="learner.reactivated")
    if account_created:
        send_account_setup_email(user, organisation.name)
    if cohort is not None:
        _add_membership(learner, cohort)
    # One entry whatever changed, named like the webhook it fired: a learner
    # new here is "added", one switched back on is "reactivated", each with
    # the cohort named when they joined it too; one already active here
    # changed only if they joined the cohort.
    joined_cohort = cohort if cohort_outcome == CohortOutcome.ADDED else None
    cohort_subjects = [joined_cohort] if joined_cohort else []
    if outcome == AddOutcome.REACTIVATED:
        details: dict[str, JSONValue] = {}
        if joined_cohort:
            details["cohort"] = joined_cohort.name
        record_learner_entry(
            learner,
            "learner.reactivated",
            actor,
            reason=reason,
            subjects=cohort_subjects,
            details=details,
        )
    elif outcome != AddOutcome.ALREADY_LEARNER:
        details = {"outcome": outcome.value}
        if joined_cohort:
            details["cohort"] = joined_cohort.name
        record_learner_entry(
            learner,
            "learner.added",
            actor,
            reason=reason,
            subjects=cohort_subjects,
            details=details,
        )
    elif joined_cohort:
        record_learner_entry(
            learner,
            "cohort_membership.added",
            actor,
            reason=reason,
            subjects=cohort_subjects,
            details={"cohort": joined_cohort.name},
        )
    return AddLearnerResult(email, outcome, learner, cohort_outcome)


def classify_learner_entry(
    organisation: Organisation,
    entry: LearnerEntry,
    cohort: Cohort | None,
    lookup: ImportLookup | None = None,
) -> AddLearnerResult:
    """Read-only twin of `add_learner`. Without a lookup it queries for the one
    address; with one it reads the preloaded facts, so a preview of a whole
    file costs no query per row."""
    email = entry.email.strip()
    try:
        validate_email(email)
    except ValidationError:
        return AddLearnerResult(email, AddOutcome.INVALID_EMAIL)
    try:
        if lookup is None:
            user = lookup_user(organisation.site, email)
        else:
            user = lookup.users.get(email.lower())
            if user is not None and user.site_id != organisation.site_id:
                raise EmailInUseOnAnotherSite(email)
    except EmailInUseOnAnotherSite:
        return AddLearnerResult(email, AddOutcome.EMAIL_IN_USE_ELSEWHERE)

    learner: Learner | None = None
    is_member = False
    if user is not None:
        if lookup is None:
            learner = Learner._base_manager.filter(
                user=user, organisation=organisation
            ).first()
            is_member = (
                cohort is not None
                and learner is not None
                and CohortMembership._base_manager.filter(
                    learner=learner, cohort=cohort
                ).exists()
            )
        else:
            learner = lookup.learners.get(user.pk)
            is_member = user.pk in lookup.member_user_ids
    outcome, cohort_outcome = decide_add(
        user=user,
        learner=learner,
        learner_is_active=learner is not None and learner.is_active,
        is_member=is_member,
        cohort_given=cohort is not None,
    )
    return AddLearnerResult(email, outcome, learner, cohort_outcome)


def add_learners(
    organisation: Organisation,
    entries: list[LearnerEntry],
    cohort: Cohort | None = None,
    *,
    actor: User | None = None,
    reason: str = "",
) -> list[AddLearnerResult]:
    """Make each address a learner of the organisation, creating a pending
    account where none exists, and put them in the cohort when one is given.
    An address repeated in the list is handled once. Raises ValueError, before
    touching any entry, when the cohort is not an active cohort of the
    organisation."""
    if cohort is not None:
        check_cohort_for(organisation.pk, cohort)
    results: list[AddLearnerResult] = []
    seen: set[str] = set()
    with transaction.atomic():
        for entry in entries:
            key = entry.email.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            results.append(
                add_learner(organisation, entry, cohort, actor=actor, reason=reason)
            )
    return results
