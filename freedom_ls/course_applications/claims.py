"""Which unclaimed applications a browser holds.

An unclaimed application has no owner yet, so the only proof a visitor may
see it is that their session remembers its id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from allauth.account.models import EmailAddress

from django.db import IntegrityError, transaction
from django.http import HttpRequest

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.learner_management.utils import is_registered_for_course

UNCLAIMED_APPLICATIONS_SESSION_KEY = "course_applications_unclaimed_ids"
CLAIM_REPORT_SESSION_KEY = "course_applications_claim_report"

ClaimOutcome = Literal["claimed", "collided", "mismatched", "dropped"]


def unclaimed_application_ids(request: HttpRequest) -> list[str]:
    """The ids this browser may still claim. Strings, because the session is JSON."""
    ids: list[str] = request.session.get(UNCLAIMED_APPLICATIONS_SESSION_KEY, [])
    return list(ids)


def remember_unclaimed_application(
    request: HttpRequest, application: CourseApplication
) -> None:
    # Reassigned rather than appended in place: the session only notices a
    # change when the key is set.
    ids = unclaimed_application_ids(request)
    if str(application.pk) not in ids:
        request.session[UNCLAIMED_APPLICATIONS_SESSION_KEY] = [
            *ids,
            str(application.pk),
        ]


def unclaimed_application_for_course(
    request: HttpRequest, course: Course
) -> CourseApplication | None:
    """This browser's unclaimed application to the course, if it holds one."""
    ids = unclaimed_application_ids(request)
    if not ids:
        return None
    return (
        CourseApplication.objects.filter(pk__in=ids, user__isnull=True, course=course)
        .select_related("course", "form_progress__form")
        .first()
    )


@dataclass(frozen=True)
class ClaimReport:
    """What one or more claim runs did, as application pks."""

    claimed: list[str] = field(default_factory=list)
    collided: list[str] = field(default_factory=list)
    mismatched: list[str] = field(default_factory=list)

    @classmethod
    def from_session(cls, data: dict[str, list[str]] | None) -> ClaimReport:
        data = data or {}
        return cls(
            claimed=list(data.get("claimed", [])),
            collided=list(data.get("collided", [])),
            mismatched=list(data.get("mismatched", [])),
        )

    def as_session(self) -> dict[str, list[str]]:
        return {
            "claimed": list(self.claimed),
            "collided": list(self.collided),
            "mismatched": list(self.mismatched),
        }

    def merged_with(self, other: ClaimReport) -> ClaimReport:
        """This report followed by `other`, without repeating a pk.

        A later run supersedes an earlier mismatch for the same application.
        """
        claimed = _unique([*self.claimed, *other.claimed])
        collided = _unique([*self.collided, *other.collided])
        mismatched = [
            pk
            for pk in _unique([*self.mismatched, *other.mismatched])
            if pk not in claimed and pk not in collided
        ]
        return ClaimReport(claimed=claimed, collided=collided, mismatched=mismatched)

    def is_empty(self) -> bool:
        return not (self.claimed or self.collided or self.mismatched)


def _unique(pks: list[str]) -> list[str]:
    return list(dict.fromkeys(pks))


def claim_unclaimed_applications(request: HttpRequest, user: User) -> ClaimReport:
    """Attach the applications this browser holds to the account that just signed in.

    One transaction per application, so a collision on one never undoes
    another. An unsubmitted draft has no email to check, so possession of
    the session that created it is the whole credential. A submitted one
    also needs the typed address verified on this account: the session proves
    the browser, the verified address proves the person.
    """
    ids = unclaimed_application_ids(request)
    if not ids:
        return ClaimReport()
    outcomes = {pk: _claim_one(pk, user) for pk in ids}
    report = ClaimReport(
        claimed=[pk for pk, (outcome, _) in outcomes.items() if outcome == "claimed"],
        collided=[
            reported for outcome, reported in outcomes.values() if outcome == "collided"
        ],
        mismatched=[
            pk for pk, (outcome, _) in outcomes.items() if outcome == "mismatched"
        ],
    )
    request.session[UNCLAIMED_APPLICATIONS_SESSION_KEY] = report.mismatched
    if not report.is_empty():
        earlier = ClaimReport.from_session(
            request.session.get(CLAIM_REPORT_SESSION_KEY)
        )
        request.session[CLAIM_REPORT_SESSION_KEY] = earlier.merged_with(
            report
        ).as_session()
    return report


def _claim_one(pk: str, user: User) -> tuple[ClaimOutcome, str]:
    """Decide and apply the claim of one application: the outcome and the pk to report.

    The row is locked for the check and the write, so two requests claiming the
    same application cannot both attach it.
    """
    with transaction.atomic():
        application = (
            CourseApplication.objects.select_for_update(of=("self",))
            .select_related("course", "form_progress")
            .filter(pk=pk)
            .first()
        )
        if application is None:
            return "dropped", pk
        if application.user_id is not None:
            return ("claimed" if application.user_id == user.pk else "dropped"), pk
        course = application.course
        if course.visibility == CourseVisibility.HIDDEN and not (
            is_registered_for_course(user, course)
        ):
            return "dropped", pk
        existing = _existing_application(user, course)
        if existing is not None:
            return "collided", str(existing.pk)
        if application.email and not _has_verified_address(user, application.email):
            return "mismatched", pk
        return _attach(application, user)


def _existing_application(user: User, course: Course) -> CourseApplication | None:
    return CourseApplication.objects.filter(user=user, course=course).first()


def _has_verified_address(user: User, email: str) -> bool:
    verified: bool = EmailAddress.objects.filter(
        user=user, verified=True, email__iexact=email
    ).exists()
    return verified


def _attach(application: CourseApplication, user: User) -> tuple[ClaimOutcome, str]:
    """Set the owner, inside a savepoint so a lost race is a collision, not an error."""
    application.user = user
    if not application.email:
        application.email = user.email
    try:
        with transaction.atomic():
            application.save(update_fields=["user", "email", "updated_at"])
    except IntegrityError:
        winner = _existing_application(user, application.course)
        if winner is None:
            raise
        return "collided", str(winner.pk)
    return "claimed", str(application.pk)
