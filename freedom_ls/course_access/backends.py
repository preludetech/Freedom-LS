"""Course access backend contract objects, base class, and default implementation.

The base class (CourseAccessBackend) and contract objects (CourseAccessDecision,
DashboardContribution) define the extension point. DefaultCourseAccessBackend is the
core "free courses only" implementation. The applications backend (ApplicationCourseAccessBackend)
lives in course_applications.backends and subclasses DefaultCourseAccessBackend there —
course_access never imports course_applications.

Task A.3 — contract objects + base class.
Task A.5 — DefaultCourseAccessBackend + CourseAccessType.
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
# Contract objects (Task A.3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CourseAccessDecision:
    """Decision returned by CourseAccessBackend.get_access().

    All callers read only these four fields — no caller may branch on
    Course.access_config directly (backend-private convention, spec §4.1/§10).
    """

    cta_label: str | None  # "Start", "Apply now", "Continue", …; None = no affordance
    cta_url: str | None  # None = not actionable
    can_self_register: bool
    can_access_content: bool


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
# Base class (Task A.3)
# ---------------------------------------------------------------------------


class CourseAccessBackend:
    """Base class for course-access backends.

    Subclass this to implement custom access logic (e.g. application-gating,
    subscriptions, feature-unlocks).

    NOTE: has_feature(*, user, feature) is intentionally NOT defined here.
    It is the additive home for feature-unlock backends (spec §4.3, §11).
    A future feature-unlock backend will add it here. Do not implement it now;
    do not delete this comment.
    """

    def get_access(self, *, user: User, course: Course) -> CourseAccessDecision:
        """Return an access decision for this user + course pair."""
        raise NotImplementedError

    def filter_visible(
        self, *, user: User, courses: QuerySet[Course]
    ) -> QuerySet[Course]:
        """Filter the queryset to courses visible to this user.

        Default: return unchanged (all courses visible). Override to hide
        application-gated courses from learners who have not applied.
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
# Core default backend (Task A.5)
# ---------------------------------------------------------------------------


class CourseAccessType(models.TextChoices):
    FREE = "free", _("Free")
    # application_gated is NOT a core value — the applications backend
    # (course_applications.backends.ApplicationCourseAccessBackend) extends this.


class DefaultCourseAccessBackend(CourseAccessBackend):
    """Core free-only access backend.

    Knows nothing about applications. All application-gated logic lives in the
    ApplicationCourseAccessBackend subclass (course_applications app, batch 3+).
    """

    def validate_course_config(
        self,
        raw: dict[str, Any],
        *,
        file_path: str = "",
    ) -> dict[str, Any]:
        """Accept only access_type key; only 'free' is valid in core.

        Returns the normalised dict {"access_type": <value>}.
        Raises ValueError with file_path context on invalid config.
        """
        allowed_keys = {"access_type"}
        extra_keys = set(raw.keys()) - allowed_keys
        if extra_keys:
            context = f" in {file_path!r}" if file_path else ""
            raise ValueError(
                f"Course access_config has unknown key(s){context}: "
                f"{sorted(extra_keys)!r}. Allowed keys: {sorted(allowed_keys)!r}"
            )

        # Note: the absent-key branch yields an enum member (CourseAccessType.FREE),
        # while the present-key branch yields a plain str. Both paths are valid:
        # the `in CourseAccessType.values` check and the returned dict both accept
        # either form, and test_empty_config_defaults_to_free asserts the dict value
        # equals the plain string "free". Verified correct.
        access_type = raw.get("access_type", CourseAccessType.FREE)
        if access_type not in CourseAccessType.values:
            context = f" in {file_path!r}" if file_path else ""
            raise ValueError(
                f"Course access_config has invalid access_type={access_type!r}{context}. "
                f"Valid values for this backend: {CourseAccessType.values!r}. "
                f"(application_gated requires the ApplicationCourseAccessBackend.)"
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
            )

        # At this point, config is valid and access_type is CourseAccessType.FREE
        # (the only core value). Registered case handled above.
        return CourseAccessDecision(
            cta_label="Start",
            cta_url=reverse(
                "student_interface:register_for_course",
                kwargs={"course_slug": course.slug},
            ),
            can_self_register=True,
            can_access_content=False,
        )

    def filter_visible(
        self, *, user: User, courses: QuerySet[Course]
    ) -> QuerySet[Course]:
        """Return courses unchanged — all courses are visible with the default backend."""
        return courses
