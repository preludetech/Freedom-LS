"""The single seam for each learner administration action: one transaction,
no request, webhook events on commit only when something changed."""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import TextChoices

from freedom_ls.accounts.account_setup import (
    EmailInUseOnAnotherSite,
    match_or_create_user,
    send_account_setup_email,
)
from freedom_ls.learner_management.models import Cohort, CohortMembership, Learner
from freedom_ls.learner_management.utils import (
    ensure_learner,
    fire_webhook_event_on_commit,
)
from freedom_ls.organisations.models import Organisation


def _learner_payload(learner: Learner) -> dict[str, object]:
    user = learner.user
    return {
        "user_id": user.pk,
        "user_email": user.email,
        "organisation_id": str(learner.organisation_id),
        "learner_id": str(learner.pk),
    }


def _fire(
    event_type: str, learner: Learner, extra: dict[str, object] | None = None
) -> None:
    fire_webhook_event_on_commit(
        event_type, {**_learner_payload(learner), **(extra or {})}, learner.site
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


def deactivate_learner(learner: Learner) -> bool:
    """Remove the learner's access. Registrations, memberships and course
    progress records are kept."""
    return _set_learner_active(learner, False, "learner.deactivated")


def reactivate_learner(learner: Learner) -> bool:
    return _set_learner_active(learner, True, "learner.reactivated")


def _check_cohort(learner: Learner, cohort: Cohort) -> None:
    if cohort.organisation_id != learner.organisation_id:
        raise ValueError("The cohort belongs to another organisation.")
    if not cohort.is_active:
        raise ValueError("The cohort is inactive.")


def _cohort_payload(cohort: Cohort, move_id: str | None = None) -> dict[str, object]:
    return {"cohort_id": str(cohort.pk), "cohort_name": cohort.name, "move_id": move_id}


def remove_from_cohort(learner: Learner, cohort: Cohort) -> bool:
    """Take the learner out of an active cohort of their organisation; False
    when they were not a member. Course progress records are kept."""
    _check_cohort(learner, cohort)
    with transaction.atomic():
        deleted, _ = CohortMembership._base_manager.filter(
            learner=learner, cohort=cohort
        ).delete()
        if deleted:
            _fire("cohort.member_removed", learner, _cohort_payload(cohort))
    return bool(deleted)


def add_to_cohort(learner: Learner, cohort: Cohort) -> bool:
    """Make the learner a member of an active cohort of their organisation;
    False when they already were. Registrations the cohort holds start giving
    them access through the membership's own signals."""
    _check_cohort(learner, cohort)
    with transaction.atomic():
        _, created = CohortMembership._base_manager.get_or_create(
            site=learner.site, learner=learner, cohort=cohort
        )
        if created:
            _fire("cohort.member_added", learner, _cohort_payload(cohort))
    return created


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


def _add_one(
    organisation: Organisation, entry: LearnerEntry, cohort: Cohort | None
) -> AddLearnerResult:
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
    if existing is not None and existing.is_active:
        learner, outcome = existing, AddOutcome.ALREADY_LEARNER
    else:
        learner = ensure_learner(user, organisation)
        if existing is None:
            outcome = AddOutcome.CREATED if account_created else AddOutcome.JOINED
            _fire("learner.added", learner, {"account_created": account_created})
        else:
            outcome = AddOutcome.REACTIVATED
            _fire("learner.reactivated", learner)
    if account_created:
        send_account_setup_email(user, organisation.name)

    cohort_outcome = None
    if cohort is not None:
        added = add_to_cohort(learner, cohort)
        cohort_outcome = CohortOutcome.ADDED if added else CohortOutcome.ALREADY_MEMBER
    return AddLearnerResult(email, outcome, learner, cohort_outcome)


def add_learners(
    organisation: Organisation,
    entries: list[LearnerEntry],
    cohort: Cohort | None = None,
) -> list[AddLearnerResult]:
    """Make each address a learner of the organisation, creating a pending
    account where none exists, and put them in the cohort when one is given.
    An address repeated in the list is handled once. Raises ValueError, before
    touching any entry, when the cohort is not an active cohort of the
    organisation."""
    if cohort is not None and (
        cohort.organisation_id != organisation.pk or not cohort.is_active
    ):
        raise ValueError("The cohort must be an active cohort of the organisation.")
    results: list[AddLearnerResult] = []
    seen: set[str] = set()
    with transaction.atomic():
        for entry in entries:
            key = entry.email.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            results.append(_add_one(organisation, entry, cohort))
    return results
