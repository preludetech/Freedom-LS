"""The registry of audit actions: the codes an `AuditLogEntry` may carry and
how each one reads."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from freedom_ls.audit_log.models import AuditLogEntry


@dataclass(frozen=True)
class AuditAction:
    """One kind of audited change.

    `code` is a `noun.verb` string. `describe`, when set, renders the entry's
    details line from the entry itself.
    """

    code: str
    label: str
    describe: Callable[[AuditLogEntry], str] | None = None


_ADDED_OUTCOMES = {
    "created": "Account created and setup email sent",
    "joined": "Joined the organisation",
    "reactivated": "Reactivated",
}


def _describe_cohort(entry: AuditLogEntry) -> str:
    return str(entry.details.get("cohort", ""))


def _describe_course(entry: AuditLogEntry) -> str:
    return str(entry.details.get("course", ""))


def _describe_move(entry: AuditLogEntry) -> str:
    return f"From {entry.details.get('source', '')} to {entry.details.get('destination', '')}"


def _describe_rename(entry: AuditLogEntry) -> str:
    return f"From {entry.details.get('old', '')} to {entry.details.get('new', '')}"


def _describe_learner_added(entry: AuditLogEntry) -> str:
    text = _ADDED_OUTCOMES.get(str(entry.details.get("outcome", "")), "")
    cohort = entry.details.get("cohort")
    if cohort:
        text = f"{text}, added to {cohort}" if text else f"Added to {cohort}"
    return text


#: Actions that summarise a bulk run rather than change one object.
SUMMARY_ACTIONS = frozenset({"bulk_action.completed", "import.committed"})

FLS_AUDIT_ACTIONS: tuple[AuditAction, ...] = (
    AuditAction("learner.added", "Learner added", _describe_learner_added),
    AuditAction("learner.renamed", "Learner renamed", _describe_rename),
    AuditAction("learner.deactivated", "Learner deactivated"),
    AuditAction("learner.reactivated", "Learner reactivated"),
    AuditAction("learner.setup_email_resent", "Setup email resent"),
    AuditAction("cohort_membership.added", "Added to cohort", _describe_cohort),
    AuditAction("cohort_membership.removed", "Removed from cohort", _describe_cohort),
    AuditAction("cohort_membership.moved", "Moved between cohorts", _describe_move),
    AuditAction("registration.added", "Registered for course", _describe_course),
    AuditAction(
        "registration.reregistered", "Re-registered for course", _describe_course
    ),
    AuditAction(
        "registration.unregistered", "Unregistered from course", _describe_course
    ),
    AuditAction("cohort.created", "Cohort created"),
    AuditAction("cohort.renamed", "Cohort renamed", _describe_rename),
    AuditAction("cohort.deactivated", "Cohort deactivated"),
    AuditAction("cohort.reactivated", "Cohort reactivated"),
    AuditAction("cohort.deleted", "Cohort deleted"),
    AuditAction(
        "cohort_registration.added", "Cohort registered for course", _describe_course
    ),
    AuditAction(
        "cohort_registration.reregistered",
        "Cohort re-registered for course",
        _describe_course,
    ),
    AuditAction(
        "cohort_registration.unregistered",
        "Cohort unregistered from course",
        _describe_course,
    ),
    AuditAction("role.granted", "Role granted"),
    AuditAction("role.removed", "Role removed"),
    AuditAction("member.suspended", "Member suspended"),
    AuditAction("member.reactivated", "Member reactivated"),
    AuditAction("bulk_action.completed", "Bulk action completed"),
    AuditAction("import.committed", "Import committed"),
)


def audit_actions() -> dict[str, AuditAction]:
    """Every registered audit action, FLS's own first."""
    return {action.code: action for action in FLS_AUDIT_ACTIONS}


def validate_action(code: str) -> None:
    """Raise ValueError for a code no registry knows, naming the valid codes."""
    registered = audit_actions()
    if code not in registered:
        valid = ", ".join(sorted(registered))
        raise ValueError(f"Unknown audit action {code!r}. Valid codes: {valid}")


def get_audit_action(code: str) -> AuditAction:
    """The registered action, or a fallback labelled by its code so an entry
    written under a code since removed from the settings still renders."""
    return audit_actions().get(code) or AuditAction(code, code)
