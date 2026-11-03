"""The registry of audit actions: the codes an `AuditLogEntry` may carry and
how each one reads."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

from freedom_ls.audit_log.config import config

if TYPE_CHECKING:
    from freedom_ls.audit_log.models import AuditLogEntry


#: The headings the audit log's "What" filter groups actions under, in order.
AUDIT_ACTION_GROUPS: tuple[str, ...] = (
    "Learners",
    "Cohort membership",
    "Course registrations",
    "Cohorts",
    "Staff and roles",
    "Other",
)


@dataclass(frozen=True)
class AuditAction:
    """One kind of audited change.

    `code` is a `noun.verb` string. `describe`, when set, renders the entry's
    details line from the entry itself. `group` is the heading the "What"
    filter lists the action under, one of `AUDIT_ACTION_GROUPS`.
    """

    code: str
    label: str
    describe: Callable[[AuditLogEntry], str] | None = None
    group: str = "Other"


_ADDED_OUTCOMES = {
    "created": "Account created and setup email sent",
    "joined": "Joined the organisation",
}


def _describe_cohort(entry: AuditLogEntry) -> str:
    return str(entry.details.get("cohort", ""))


def _describe_joined_cohort(entry: AuditLogEntry) -> str:
    """The cohort a learner joined in the same change, when there was one,
    or the course a learner's own registration reactivated them for."""
    course = entry.details.get("course")
    if course:
        return f"Self-registered for {course}"
    cohort = entry.details.get("cohort")
    return f"Added to {cohort}" if cohort else ""


def _describe_course(entry: AuditLogEntry) -> str:
    course = str(entry.details.get("course", ""))
    if entry.details.get("self_service"):
        return f"{course} (self-registered)"
    return course


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


def _describe_role(entry: AuditLogEntry) -> str:
    # The code stands in for entries written before the label was stored.
    role = entry.details.get("role_label") or entry.details.get("role", "")
    return f"{role} on {entry.details.get('scope', '')}"


def _describe_run_summary(entry: AuditLogEntry) -> str:
    counts = entry.details.get("counts")
    if not isinstance(counts, dict):
        return ""
    return (
        f"{counts.get('changed', 0)} changed, {counts.get('skipped', 0)} skipped, "
        f"{counts.get('failed', 0)} failed"
    )


def _describe_export(entry: AuditLogEntry) -> str:
    """The scope label when the export was one learner's or cohort's
    history, the row count, and the filters that narrowed it."""
    count = int(entry.details.get("count", 0))
    parts = [f"{count} {'entry' if count == 1 else 'entries'}"]
    scope_label = entry.details.get("scope_label")
    if scope_label:
        parts[0] = f"{scope_label}: {parts[0]}"
    filters = entry.details.get("filters")
    if filters:
        parts.append(f"filtered by {filters}")
    return ", ".join(parts)


#: Actions that summarise a bulk run rather than change one object.
SUMMARY_ACTIONS = frozenset({"bulk_action.completed", "import.committed"})

FLS_AUDIT_ACTIONS: tuple[AuditAction, ...] = (
    AuditAction(
        "learner.added", "Learner added", _describe_learner_added, group="Learners"
    ),
    AuditAction(
        "learner.renamed", "Learner renamed", _describe_rename, group="Learners"
    ),
    AuditAction("learner.deactivated", "Learner deactivated", group="Learners"),
    AuditAction(
        "learner.reactivated",
        "Learner reactivated",
        _describe_joined_cohort,
        group="Learners",
    ),
    AuditAction("learner.setup_email_resent", "Setup email resent", group="Learners"),
    AuditAction(
        "cohort_membership.added",
        "Learner added to cohort",
        _describe_cohort,
        group="Cohort membership",
    ),
    AuditAction(
        "cohort_membership.removed",
        "Learner removed from cohort",
        _describe_cohort,
        group="Cohort membership",
    ),
    AuditAction(
        "cohort_membership.moved",
        "Learner moved between cohorts",
        _describe_move,
        group="Cohort membership",
    ),
    AuditAction(
        "registration.added",
        "Learner registered for course",
        _describe_course,
        group="Course registrations",
    ),
    AuditAction(
        "registration.reactivated",
        "Learner course registration reactivated",
        _describe_course,
        group="Course registrations",
    ),
    AuditAction(
        "registration.deactivated",
        "Learner course registration deactivated",
        _describe_course,
        group="Course registrations",
    ),
    AuditAction("cohort.created", "Cohort created", group="Cohorts"),
    AuditAction("cohort.renamed", "Cohort renamed", _describe_rename, group="Cohorts"),
    AuditAction("cohort.deactivated", "Cohort deactivated", group="Cohorts"),
    AuditAction("cohort.reactivated", "Cohort reactivated", group="Cohorts"),
    AuditAction("cohort.deleted", "Cohort deleted", group="Cohorts"),
    AuditAction(
        "cohort_registration.added",
        "Cohort registered for course",
        _describe_course,
        group="Cohorts",
    ),
    AuditAction(
        "cohort_registration.reactivated",
        "Cohort course registration reactivated",
        _describe_course,
        group="Cohorts",
    ),
    AuditAction(
        "cohort_registration.deactivated",
        "Cohort course registration deactivated",
        _describe_course,
        group="Cohorts",
    ),
    AuditAction(
        "role.assigned", "Role assigned", _describe_role, group="Staff and roles"
    ),
    AuditAction(
        "role.deactivated", "Role deactivated", _describe_role, group="Staff and roles"
    ),
    AuditAction(
        "role.removed", "Role removed", _describe_role, group="Staff and roles"
    ),
    AuditAction(
        "staff_member.deactivated", "Staff member deactivated", group="Staff and roles"
    ),
    AuditAction(
        "staff_member.reactivated", "Staff member reactivated", group="Staff and roles"
    ),
    AuditAction(
        "bulk_action.completed", "Bulk action completed", _describe_run_summary
    ),
    AuditAction("import.committed", "Import committed", _describe_run_summary),
    AuditAction("conversation.viewed", "Conversation viewed"),
    AuditAction("api_key.issued", "API key issued"),
    AuditAction("api_key.revoked", "API key revoked"),
    AuditAction("audit_log.exported", "Audit log exported", _describe_export),
)


@cache
def _registry(extra: tuple[tuple[str, str], ...]) -> dict[str, AuditAction]:
    actions = {action.code: action for action in FLS_AUDIT_ACTIONS}
    # Downstream-defined actions follow FLS's own, so FLS codes keep their order and win any collision.
    for code, label in extra:
        actions.setdefault(code, AuditAction(code, label))
    return actions


def audit_actions() -> dict[str, AuditAction]:
    """Every registered audit action, FLS's own first. Built once per value
    of the extra-actions setting and shared, so callers must not change it."""
    return _registry(tuple(config.AUDIT_LOG_EXTRA_ACTIONS.items()))


def audit_actions_by_group() -> list[tuple[str, list[AuditAction]]]:
    """Every registered action under its group heading, in
    `AUDIT_ACTION_GROUPS` order; a group with no action is left out."""
    actions = list(audit_actions().values())
    return [
        (group, members)
        for group in AUDIT_ACTION_GROUPS
        if (members := [action for action in actions if action.group == group])
    ]


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
