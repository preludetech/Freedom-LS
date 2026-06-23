"""Course access backend contract objects, base class, and default implementation.

The base class (CourseAccessBackend) and contract objects (CourseAccessDecision,
DashboardContribution) define the extension point. FreeOnlyCourseAccessBackend is the
core "free courses only" implementation. The applications backend (ApplicationCourseAccessBackend)
lives in course_applications.backends and subclasses FreeOnlyCourseAccessBackend there —
course_access never imports course_applications.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from freedom_ls.student_management.utils import is_registered_for_course

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course


# ---------------------------------------------------------------------------
# Contract objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CourseAccessDecision:
    """Decision returned by CourseAccessBackend.get_access().

    All callers read only these four fields — no caller may branch on
    Course.access_config directly (backend-private convention).
    """

    cta_label: str | None  # "Start", "Apply now", "Continue", …; None = no affordance
    cta_url: str | None  # None = not actionable
    can_self_register: bool
    can_access_content: bool
    # Acquisition-funnel copy for the course detail page, driven by the backend so
    # the template carries no access-type-specific marketing (a gated course must
    # not inherit the free "One click. No credit card." copy). None = omit that line.
    enrolment_summary: str | None = None  # hero stat-card "Enrolment" value
    acquisition_heading: str | None = None  # sign-up panel heading
    acquisition_subtext: str | None = None  # sign-up panel subtext


@dataclass(frozen=True)
class DashboardContribution:
    """A backend-owned panel for the learner dashboard.

    The dashboard renders each contribution generically via render_to_string and
    never reads context keys — the contributing backend owns the partial + its data.
    """

    template_name: str  # a partial the contributing backend owns
    # Deliberate Any: context is an opaque render-ready dict whose keys are
    # backend-owned; course_access never inspects them.
    context: dict[str, Any]  # render-ready context for that partial


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class CourseAccessBackend:
    """Base class for course-access backends.

    Subclass this to implement custom access logic (e.g. application-gating,
    subscriptions, feature-unlocks).

    NOTE: has_feature(*, user, feature) is intentionally NOT defined here.
    It is the additive home for a future feature-unlock backend, which will add
    it here. Do not implement it now; do not delete this comment.
    """

    def get_access(self, *, user: User, course: Course) -> CourseAccessDecision:
        """Return an access decision for this user + course pair."""
        raise NotImplementedError

    def filter_visible(
        self, *, user: User, courses: QuerySet[Course]
    ) -> QuerySet[Course]:
        """Filter the queryset to courses visible to this user.

        Default: return unchanged (all courses visible). This seam exists for a
        future backend that hides courses a learner genuinely cannot reach (e.g.
        a subscription/paywall backend). Note application-gating does NOT use it:
        gated courses stay discoverable and are gated at the CTA + chokepoint level.
        """
        raise NotImplementedError

    def validate_course_config(
        self,
        # Deliberate Any: access_config is a genuinely opaque JSON blob whose
        # keys are backend-owned; the base class and callers never inspect them.
        raw: dict[str, Any],
        *,
        file_path: str = "",
    ) -> dict[str, Any]:
        """Validate & normalise this backend's slice of Course.access_config.

        Single implementation; called at content-load (fail loud), by a Django
        system check (after a backend swap), and defensively in get_access().
        Raise ValueError on invalid config.
        """
        raise NotImplementedError

    def get_dashboard_contributions(self, *, user: User) -> list[DashboardContribution]:
        """Backend-owned panels for the learner dashboard. Default: nothing.

        The dashboard renders each generically and never names the backend — this is
        the seam that replaces a hard-coded student_interface -> course_applications import.
        """
        return []


# ---------------------------------------------------------------------------
# Core default backend
# ---------------------------------------------------------------------------


class CourseAccessType(models.TextChoices):
    FREE = "free", _("Free")
    # application_gated is NOT a core value — the applications backend
    # (course_applications.backends.ApplicationCourseAccessBackend) extends this.


# Acquisition-funnel copy for free courses, surfaced on the detail page via the
# CourseAccessDecision. Shared by the Start (unregistered) and Continue (registered)
# branches so the free funnel reads identically in both.
_FREE_ENROLMENT_SUMMARY = "Free · open"
_FREE_ACQUISITION_HEADING = "Free · open to everyone"
_FREE_ACQUISITION_SUBTEXT = "One click. No credit card."


class FreeOnlyCourseAccessBackend(CourseAccessBackend):
    """Core free-only access backend.

    Knows nothing about applications. All application-gated logic lives in the
    ApplicationCourseAccessBackend subclass (course_applications app).
    """

    # Access type values this backend accepts. Subclasses (e.g. the applications
    # backend) widen the vocabulary by overriding this attribute — the shared
    # validate_course_config below reads it through self, so no method override.
    _ALLOWED_ACCESS_TYPES: frozenset[str] = frozenset(CourseAccessType.values)

    def validate_course_config(
        self,
        raw: dict[str, Any],
        *,
        file_path: str = "",
    ) -> dict[str, Any]:
        """Validate & normalise access_config against ``self._ALLOWED_ACCESS_TYPES``.

        Accepts only the access_type key; an absent access_type defaults to 'free'.
        Returns the normalised dict {"access_type": <value>}. Raises ValueError with
        file_path context on an unknown key or an unrecognised access_type.
        """
        allowed_keys = {"access_type"}
        extra_keys = set(raw.keys()) - allowed_keys
        if extra_keys:
            context = f" in {file_path!r}" if file_path else ""
            raise ValueError(
                f"Course access_config has unknown key(s){context}: "
                f"{sorted(extra_keys)!r}. Allowed keys: {sorted(allowed_keys)!r}"
            )

        access_type = raw.get("access_type", "free")
        if access_type not in self._ALLOWED_ACCESS_TYPES:
            context = f" in {file_path!r}" if file_path else ""
            raise ValueError(
                f"Course access_config has invalid access_type={access_type!r}{context}. "
                f"Valid values for this backend: {sorted(self._ALLOWED_ACCESS_TYPES)!r}."
            )
        return {"access_type": access_type}

    def get_access(self, *, user: User, course: Course) -> CourseAccessDecision:
        """Return a CourseAccessDecision for this user + course.

        Registered (direct or cohort) → Continue/content.
        Free, not registered → Start/self-register.
        Invalid config → safe no-action decision.
        """
        try:
            self.validate_course_config(course.access_config)
        except ValueError:
            return CourseAccessDecision(
                cta_label=None,
                cta_url=None,
                can_self_register=False,
                can_access_content=False,
            )

        if is_registered_for_course(user, course):
            return CourseAccessDecision(
                cta_label="Continue",
                cta_url=reverse(
                    "student_interface:course_home",
                    kwargs={"course_slug": course.slug},
                ),
                can_self_register=False,
                can_access_content=True,
                enrolment_summary=_FREE_ENROLMENT_SUMMARY,
                acquisition_heading=_FREE_ACQUISITION_HEADING,
                acquisition_subtext=_FREE_ACQUISITION_SUBTEXT,
            )

        # At this point, config is valid and access_type is CourseAccessType.FREE
        # (the only core value). Registered case handled above.
        return CourseAccessDecision(
            cta_label="Start",
            cta_url=reverse(
                "student_interface:initiate_course_access",
                kwargs={"course_slug": course.slug},
            ),
            can_self_register=True,
            can_access_content=False,
            enrolment_summary=_FREE_ENROLMENT_SUMMARY,
            acquisition_heading=_FREE_ACQUISITION_HEADING,
            acquisition_subtext=_FREE_ACQUISITION_SUBTEXT,
        )

    def filter_visible(
        self, *, user: User, courses: QuerySet[Course]
    ) -> QuerySet[Course]:
        """Return courses unchanged — all courses are visible with the default backend."""
        return courses
