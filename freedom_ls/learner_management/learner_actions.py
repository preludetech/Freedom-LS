"""The single seam for each learner administration action: one transaction,
no request, webhook events on commit only when something changed."""

from __future__ import annotations

from django.db import transaction

from freedom_ls.learner_management.models import Cohort, CohortMembership, Learner
from freedom_ls.learner_management.utils import fire_webhook_event_on_commit


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
