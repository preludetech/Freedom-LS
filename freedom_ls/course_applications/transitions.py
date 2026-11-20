"""The only code that changes a CourseApplication's state.

Each function locks the row, refuses a move the current state does not allow,
writes the new state and its timestamp, and copies what it wrote onto the
instance it was given. A refused call writes nothing.
"""

from __future__ import annotations

from collections.abc import Mapping

from django.db import transaction
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.audit_log.writer import record_entry
from freedom_ls.course_applications.exceptions import (
    ApplicationStateError,
    UnclaimedApplicationError,
)
from freedom_ls.course_applications.models import OPEN_STATES, CourseApplication

State = CourseApplication.State

ALLOWED_FROM: Mapping[CourseApplication.State, frozenset[CourseApplication.State]] = {
    State.SUBMITTED: frozenset({State.DRAFT}),
    State.WITHDRAWN: OPEN_STATES,
    State.APPROVED: frozenset({State.SUBMITTED}),
    State.REJECTED: frozenset({State.SUBMITTED}),
}

# The one timestamp each move writes; approve and reject share decided_at and
# the state says which decision it was.
STAMP_FIELD: Mapping[CourseApplication.State, str] = {
    State.SUBMITTED: "submitted_at",
    State.WITHDRAWN: "withdrawn_at",
    State.APPROVED: "decided_at",
    State.REJECTED: "decided_at",
}


def _move(
    application: CourseApplication,
    to: CourseApplication.State,
    *,
    extra: Mapping[str, str] | None = None,
    actor: User | None = None,
    require_user: bool = False,
) -> CourseApplication:
    with transaction.atomic():
        # _base_manager so the lock works with no request site (reviewer tools,
        # management commands); the pk comes from an instance the caller already
        # fetched through a site-scoped lookup. No select_related: FOR UPDATE
        # refuses the nullable joins.
        locked = CourseApplication._base_manager.select_for_update().get(
            pk=application.pk
        )
        if locked.state not in ALLOWED_FROM[to]:
            raise ApplicationStateError(current_state=locked.state)
        if require_user and locked.user_id is None:
            raise UnclaimedApplicationError
        from_state = locked.state
        stamp_field = STAMP_FIELD[to]
        locked.state = to
        setattr(locked, stamp_field, timezone.now())
        for name, value in (extra or {}).items():
            setattr(locked, name, value)
        written = ["state", stamp_field, *(extra or {}), "updated_at"]
        locked.save(update_fields=written)
        for name in written:
            setattr(application, name, getattr(locked, name))
        if actor is not None:
            record_entry(
                action=f"application.{to}",
                actor=actor,
                target=application,
                target_label=f"{application.course.title} application {application.pk}",
                organisation=application.organisation,
                subjects=(application.course,),
                details={"from": from_state, "to": to},
            )
    return application


def submit_application(application: CourseApplication) -> CourseApplication:
    """Move a draft to submitted."""
    return _move(application, State.SUBMITTED)


def withdraw_application(application: CourseApplication) -> CourseApplication:
    """Close an open application on the applicant's behalf."""
    return _move(application, State.WITHDRAWN)
