"""Course access backend contract objects, base class, and default implementation.

The base class (CourseAccessBackend) and contract objects (CourseAccessDecision,
DashboardContribution) define the extension point. FreeOnlyCourseAccessBackend is the
core "free courses only" implementation. The applications backend (ApplicationCourseAccessBackend)
lives in course_applications.backends and subclasses FreeOnlyCourseAccessBackend there —
course_access never imports course_applications.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, cast

from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from freedom_ls.learner_management.queries import (
    in_audience_expression,
    is_in_audience,
    is_registered_for_course_expression,
)
from freedom_ls.learner_management.utils import is_registered_for_course

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime
    from uuid import UUID

    from django.contrib.auth.models import AnonymousUser
    from django.db.models import QuerySet
    from django.http import HttpRequest

    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course
    from freedom_ls.deadlines.policy import ResolvedDeadlinePolicy
    from freedom_ls.deadlines.resolver import ResolvedDeadline

    type RequestUser = User | AnonymousUser


# ---------------------------------------------------------------------------
# Contract objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CourseAccessDecision:
    """Decision returned by CourseAccessBackend.get_access().

    All callers read only these fields — no caller may branch on
    Course.access_config directly (backend-private convention).
    """

    cta_label: (
        str | None
    )  # "Enrol for free", "Apply now", "Continue", …; None = no affordance
    cta_url: str | None  # None = not actionable
    can_self_register: bool
    can_access_content: bool
    # Acquisition-funnel copy for the course detail page, driven by the backend so
    # the template carries no access-type-specific marketing (a gated course must
    # not inherit the free "One click. No credit card." copy). None = omit that line.
    enrolment_summary: str | None = None  # hero stat-card "Enrolment" value
    acquisition_heading: str | None = None  # sign-up panel heading
    acquisition_subtext: str | None = None  # sign-up panel subtext
    is_accessible_for_free: bool = True  # honest free/gated signal for badge + JSON-LD
    # Set when a registered learner's access to the content has ended: the instant it
    # ended and what the course still shows them (an AfterAccessEnded value). Both are
    # None for every other decision, including one that never granted access.
    access_ended_at: datetime | None = None
    after_access_ended: str | None = None


@dataclass(frozen=True)
class AccessBadge:
    """Backend-owned at-a-glance access badge for course cards/rows.

    The backend owns both the copy and the chip styling so a new access type
    (e.g. "Paid") can add its own label/variant without learner_interface knowing
    any access-type copy. None from get_access_badge means "render no badge".
    """

    label: str  # e.g. "Free", "By application"
    variant: str = "primary"  # chip variant; backend owns the styling too


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
    # The id of the element a pager inside the panel swaps. An htmx request
    # naming it in HX-Target gets this contribution rendered on its own rather
    # than the whole dashboard. Empty when the panel has no swap of its own.
    swap_id: str = ""


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

    def get_access(self, *, user: RequestUser, course: Course) -> CourseAccessDecision:
        """Return an access decision for this user + course pair."""
        raise NotImplementedError

    def get_access_for_request(
        self, *, request: HttpRequest, course: Course
    ) -> CourseAccessDecision:
        """The access decision for whoever is making this request.

        The default reads nothing but the user, so a backend that decides by
        user alone overrides get_access only. A backend that also recognises an
        anonymous session overrides this.
        """
        return self.get_access(user=request.user, course=course)

    def get_access_many(
        self, *, user: RequestUser, courses: Sequence[Course]
    ) -> dict[UUID, CourseAccessDecision]:
        """The access decision for each of ``courses``, keyed by course id.

        The default asks get_access once per course. A backend that can answer for a
        whole listing with a fixed number of queries overrides this, so a page showing
        many courses does not pay for each one separately.
        """
        return {
            course.pk: self.get_access(user=user, course=course) for course in courses
        }

    def is_accessible_for_free(self, *, course: Course) -> bool:
        """User-independent free/gated signal for badges and JSON-LD.

        Config-only: issues no per-user queries, so listings can call it once per
        course without the registration lookups that get_access performs. The value
        must agree with the is_accessible_for_free field get_access sets.
        """
        raise NotImplementedError

    def get_access_badge(self, *, course: Course) -> AccessBadge | None:
        """Config-only display badge for course cards/rows. None = no badge.

        Config-only (no per-user queries) so listings can call it once per course.
        Sibling of is_accessible_for_free: that is the semantic boolean (badge +
        JSON-LD agree with it), this is the display badge itself. Each backend owns
        its own labels/variants, so a new access type never leaks copy into
        learner_interface.
        """
        raise NotImplementedError

    def get_access_type(self, *, course: Course) -> str:
        """Config-only machine name for how this course is entered, e.g. "free".

        A stable lowercase snake_case constant, for analytics. The badge label
        cannot stand in for it: that is display copy and may be translated, and
        Course.access_config is backend-private.
        """
        raise NotImplementedError

    def filter_visible(
        self, *, user: RequestUser, courses: QuerySet[Course]
    ) -> QuerySet[Course]:
        """Filter the queryset to courses visible to this user.

        Default: return unchanged (all courses visible). This seam exists for a
        future backend that hides courses a learner genuinely cannot reach (e.g.
        a subscription/paywall backend). Note application-gating does NOT use it:
        gated courses stay discoverable and are gated at the CTA + chokepoint level.

        ``user`` is a RequestUser (may be anonymous): discovery listings are
        available to anonymous visitors, so anon users genuinely flow through here.
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

    def get_dashboard_contributions(
        self, *, user: RequestUser
    ) -> list[DashboardContribution]:
        """Backend-owned panels for the learner dashboard. Default: nothing.

        The dashboard renders each generically and never names the backend — this is
        the seam that replaces a hard-coded learner_interface -> course_applications import.
        """
        return []

    def get_dashboard_contributions_for_request(
        self, *, request: HttpRequest
    ) -> list[DashboardContribution]:
        """Dashboard panels for whoever is making this request.

        Default: the signed-in user's, and nothing for a visitor, so a backend
        whose panels assume a signed-in user is never handed an anonymous one.
        A backend with something to show a visitor overrides this.
        """
        if not request.user.is_authenticated:
            return []
        return self.get_dashboard_contributions(user=request.user)


# ---------------------------------------------------------------------------
# Core default backend
# ---------------------------------------------------------------------------


class CourseAccessType(models.TextChoices):
    FREE = "free", _("Free")
    # application_gated is NOT a core value — the applications backend
    # (course_applications.backends.ApplicationCourseAccessBackend) extends this.


# Acquisition-funnel copy for free courses, surfaced on the detail page via the
# CourseAccessDecision. Shared by the "Enrol for free" (unregistered) and Continue
# (registered) branches so the free funnel reads identically in both.
_FREE_ENROLMENT_SUMMARY = "Free · open"
_FREE_ACQUISITION_HEADING = "Free · open to everyone"
_FREE_ACQUISITION_SUBTEXT = "One click. No credit card."


def _free_access_decision(*, user: RequestUser, course: Course) -> CourseAccessDecision:
    """Canonical free/open decision, independent of the course's real access_config.

    Shared by FreeOnlyCourseAccessBackend.get_access (called after its own
    validate_course_config check) and VisibilityEnforcingBackend's access
    override (called directly, deliberately bypassing validate_course_config).
    """
    if is_registered_for_course(user, course):
        return CourseAccessDecision(
            cta_label="Continue",
            cta_url=reverse(
                "learner_interface:course_home",
                kwargs={"course_slug": course.slug},
            ),
            can_self_register=False,
            can_access_content=True,
            enrolment_summary=_FREE_ENROLMENT_SUMMARY,
            acquisition_heading=_FREE_ACQUISITION_HEADING,
            acquisition_subtext=_FREE_ACQUISITION_SUBTEXT,
        )

    return CourseAccessDecision(
        cta_label="Enrol for free",
        cta_url=reverse(
            "learner_interface:initiate_course_access",
            kwargs={"course_slug": course.slug},
        ),
        can_self_register=True,
        can_access_content=False,
        enrolment_summary=_FREE_ENROLMENT_SUMMARY,
        acquisition_heading=_FREE_ACQUISITION_HEADING,
        acquisition_subtext=_FREE_ACQUISITION_SUBTEXT,
    )


class FreeOnlyCourseAccessBackend(CourseAccessBackend):
    """Core free-only access backend.

    Knows nothing about applications. All application-gated logic lives in the
    ApplicationCourseAccessBackend subclass (course_applications app).
    """

    # Access type values this backend accepts. Subclasses (e.g. the applications
    # backend) widen the vocabulary by overriding this attribute — the shared
    # validate_course_config below reads it through self, so no method override.
    _ALLOWED_ACCESS_TYPES: frozenset[str] = frozenset(CourseAccessType.values)

    # access_config keys this backend understands. Subclasses widen it exactly as
    # they widen _ALLOWED_ACCESS_TYPES; the shared validate_course_config below
    # reads it through self, so no method override is needed to add a key.
    _ALLOWED_CONFIG_KEYS: frozenset[str] = frozenset({"access_type"})

    def validate_course_config(
        self,
        raw: dict[str, Any],
        *,
        file_path: str = "",
    ) -> dict[str, Any]:
        """Validate & normalise access_config against this backend's allowed sets.

        Accepts only ``self._ALLOWED_CONFIG_KEYS``; an absent access_type defaults
        to 'free' and must be in ``self._ALLOWED_ACCESS_TYPES``. Returns the
        normalised dict: every allowed key that was present, plus the defaulted
        access_type. Raises ValueError with file_path context on an unknown key or
        an unrecognised access_type.

        Allowed keys other than access_type are returned untouched, because the
        content loader reads them back off the schema item after this runs.
        """
        extra_keys = set(raw.keys()) - self._ALLOWED_CONFIG_KEYS
        if extra_keys:
            context = f" in {file_path!r}" if file_path else ""
            raise ValueError(
                f"Course access_config has unknown key(s){context}: "
                f"{sorted(extra_keys)!r}. "
                f"Allowed keys: {sorted(self._ALLOWED_CONFIG_KEYS)!r}"
            )

        access_type = raw.get("access_type", "free")
        if access_type not in self._ALLOWED_ACCESS_TYPES:
            context = f" in {file_path!r}" if file_path else ""
            raise ValueError(
                f"Course access_config has invalid access_type={access_type!r}{context}. "
                f"Valid values for this backend: {sorted(self._ALLOWED_ACCESS_TYPES)!r}."
            )
        normalised = {k: v for k, v in raw.items() if k in self._ALLOWED_CONFIG_KEYS}
        normalised["access_type"] = access_type
        return normalised

    def get_access(self, *, user: RequestUser, course: Course) -> CourseAccessDecision:
        """Return a CourseAccessDecision for this user + course.

        Registered (direct or cohort) → Continue/content.
        Free, not registered → Enrol for free/self-register.
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

        # At this point, config is valid and access_type is CourseAccessType.FREE
        # (the only core value).
        return _free_access_decision(user=user, course=course)

    def is_accessible_for_free(self, *, course: Course) -> bool:
        """Always free — the only valid access type for this backend is FREE."""
        return True

    def get_access_badge(self, *, course: Course) -> AccessBadge | None:
        """Every course is free, so the badge always reads "Free"."""
        return AccessBadge(label="Free")

    def get_access_type(self, *, course: Course) -> str:
        """Always free, the only access type this backend allows."""
        return str(CourseAccessType.FREE)

    def filter_visible(
        self, *, user: RequestUser, courses: QuerySet[Course]
    ) -> QuerySet[Course]:
        """Return courses unchanged — all courses are visible with the default backend."""
        return courses


# ---------------------------------------------------------------------------
# Visibility-enforcing wrapper
# ---------------------------------------------------------------------------

# Acquisition-funnel copy for coming-soon courses, surfaced on the detail page via
# CourseAccessDecision. Does NOT promise a launch notification: nothing sends one.
_COMING_SOON_ENROLMENT_SUMMARY = "Coming soon"
_COMING_SOON_ACQUISITION_HEADING = "Coming soon"
_COMING_SOON_ACQUISITION_SUBTEXT = (
    "Register your interest and we'll let you know when the course is ready."
)


def _closed_decision() -> CourseAccessDecision:
    """The decision for a course the user may not see: no call to action, no access."""
    return CourseAccessDecision(
        cta_label=None,
        cta_url=None,
        can_self_register=False,
        can_access_content=False,
    )


class VisibilityEnforcingBackend(CourseAccessBackend):
    """Applies Course.visibility around any inner backend.

    Applied by the loader so no backend (present or future) can bypass
    coming-soon / hidden. The inner backend handles all published-course logic;
    this wrapper intercepts coming_soon and hidden before the inner sees them.

    Both coming_soon and hidden exempt users already registered for the course:
    a registered learner keeps full access and delegates to the inner backend,
    so mid-course learners are never disrupted by a visibility change.
    """

    def __init__(self, inner: CourseAccessBackend) -> None:
        self._inner = inner

    def _visibility_decision(
        self, *, user: RequestUser, course: Course
    ) -> CourseAccessDecision | None:
        """The decision visibility forces, or None when the inner backend decides."""
        from freedom_ls.content_engine.models import CourseVisibility
        from freedom_ls.course_access.overrides import (
            override_access_to_free,
            override_visibility_to_visible,
        )

        if not override_visibility_to_visible() and not is_in_audience(user, course):
            return _closed_decision()
        if (
            course.visibility == CourseVisibility.COMING_SOON
            and not is_registered_for_course(user, course)
            and not override_visibility_to_visible()
        ):
            return CourseAccessDecision(
                cta_label="I'm interested",
                cta_url=reverse(
                    "course_interest:express_interest",
                    kwargs={"course_slug": course.slug},
                ),
                can_self_register=False,
                can_access_content=False,
                enrolment_summary=_COMING_SOON_ENROLMENT_SUMMARY,
                acquisition_heading=_COMING_SOON_ACQUISITION_HEADING,
                acquisition_subtext=_COMING_SOON_ACQUISITION_SUBTEXT,
            )
        if (
            course.visibility == CourseVisibility.HIDDEN
            and not is_registered_for_course(user, course)
            and not override_visibility_to_visible()
        ):
            return _closed_decision()
        if override_access_to_free():
            # Dev/staging preview: replace the inner backend's real decision with
            # the canonical free decision, ignoring the course's actual access_config.
            return _free_access_decision(user=user, course=course)
        return None

    def get_access(self, *, user: RequestUser, course: Course) -> CourseAccessDecision:
        forced = self._visibility_decision(user=user, course=course)
        if forced is not None:
            return forced
        return self._inner.get_access(user=user, course=course)

    def get_access_for_request(
        self, *, request: HttpRequest, course: Course
    ) -> CourseAccessDecision:
        forced = self._visibility_decision(user=request.user, course=course)
        if forced is not None:
            return forced
        return self._inner.get_access_for_request(request=request, course=course)

    def get_access_many(
        self, *, user: RequestUser, courses: Sequence[Course]
    ) -> dict[UUID, CourseAccessDecision]:
        decisions: dict[UUID, CourseAccessDecision] = {}
        unforced: list[Course] = []
        for course in courses:
            forced = self._visibility_decision(user=user, course=course)
            if forced is None:
                unforced.append(course)
            else:
                decisions[course.pk] = forced
        decisions.update(self._inner.get_access_many(user=user, courses=unforced))
        return decisions

    def is_accessible_for_free(self, *, course: Course) -> bool:
        from freedom_ls.course_access.overrides import override_access_to_free

        if override_access_to_free():
            return True
        # Visibility does not change the access model; delegate to the inner backend.
        return self._inner.is_accessible_for_free(course=course)

    def get_access_badge(self, *, course: Course) -> AccessBadge | None:
        from freedom_ls.course_access.overrides import override_access_to_free

        if override_access_to_free():
            # Dev/staging preview: badge reads "Free" regardless of the real
            # access model. Delegated, not inlined, so the "Free" copy stays
            # owned by FreeOnlyCourseAccessBackend.
            return FreeOnlyCourseAccessBackend().get_access_badge(course=course)
        # The access-model badge is owned by the inner backend; the visibility
        # wrapper never mints its own badge copy.
        return self._inner.get_access_badge(course=course)

    def get_access_type(self, *, course: Course) -> str:
        from freedom_ls.course_access.overrides import override_access_to_free

        if override_access_to_free():
            # Agrees with get_access, which hands out the free decision here.
            return FreeOnlyCourseAccessBackend().get_access_type(course=course)
        return self._inner.get_access_type(course=course)

    def filter_visible(
        self, *, user: RequestUser, courses: QuerySet[Course]
    ) -> QuerySet[Course]:
        from freedom_ls.content_engine.models import CourseVisibility
        from freedom_ls.course_access.overrides import override_visibility_to_visible

        courses = self._inner.filter_visible(user=user, courses=courses)
        if override_visibility_to_visible():
            return courses
        # Anonymous users never see hidden courses; authenticated users see a
        # hidden course only if registered for it (Exists() subquery, no joins).
        if not user.is_authenticated:
            return courses.exclude(visibility=CourseVisibility.HIDDEN).filter(
                in_audience_expression(user)
            )
        return (
            courses.annotate(_is_registered=is_registered_for_course_expression(user))
            .exclude(Q(visibility=CourseVisibility.HIDDEN) & Q(_is_registered=False))
            .filter(in_audience_expression(user, registered=Q(_is_registered=True)))
        )

    def validate_course_config(
        self,
        raw: dict[str, Any],
        *,
        file_path: str = "",
    ) -> dict[str, Any]:
        return self._inner.validate_course_config(raw, file_path=file_path)

    def get_dashboard_contributions(
        self, *, user: RequestUser
    ) -> list[DashboardContribution]:
        return self._inner.get_dashboard_contributions(user=user)

    def get_dashboard_contributions_for_request(
        self, *, request: HttpRequest
    ) -> list[DashboardContribution]:
        return self._inner.get_dashboard_contributions_for_request(request=request)


# ---------------------------------------------------------------------------
# Deadline-enforcing wrapper
# ---------------------------------------------------------------------------


def _ended_or_none(
    inner_decision: CourseAccessDecision,
    time_limit: ResolvedDeadline,
    policy: ResolvedDeadlinePolicy,
) -> CourseAccessDecision | None:
    """The inner decision with content withdrawn if the learner's access has ended by now,
    else None. The funnel copy stays: the detail page's stats strip still describes the
    course."""
    from freedom_ls.deadlines.consequences import access_end_instant, has_access_ended

    if not has_access_ended(time_limit, policy, timezone.now()):
        return None
    return replace(
        inner_decision,
        cta_label=None,
        cta_url=None,
        can_self_register=False,
        can_access_content=False,
        access_ended_at=access_end_instant(time_limit, policy),
        after_access_ended=policy.after_access_ended,
    )


class DeadlineEnforcingBackend(CourseAccessBackend):
    """Ends a learner's content access once their course deadline policy says it has ended.

    Wraps any inner backend: the inner backend decides who may enter, this wrapper
    withdraws content access from a registered learner who is past the time limit plus
    the grace window under a policy that ends access. Nothing is written: the decision is
    recomputed on every call, so a later deadline override restores access at once.
    """

    def __init__(self, inner: CourseAccessBackend) -> None:
        self._inner = inner

    def _ended_decision(
        self, *, user: User, course: Course, inner_decision: CourseAccessDecision
    ) -> CourseAccessDecision | None:
        """The decision for a learner whose access has ended, or None when the inner
        decision stands.

        Deadlines are read only once the inner backend has granted content, so a refused
        decision costs nothing extra. The imports are function-local: deadlines depends on
        learner_progress, and a module-level import here would pull both in at import time.
        """
        from freedom_ls.deadlines.loader import get_deadline_policy
        from freedom_ls.deadlines.resolver import course_deadlines
        from freedom_ls.learner_progress.queries import course_progress_for

        if not inner_decision.can_access_content:
            return None
        record = course_progress_for(user, course)
        # A finished course never ends.
        if record is None or record.completed_time is not None:
            return None
        policy = get_deadline_policy().resolve(record)
        # Nothing can end, so the time limit is not read.
        if not policy.end_course_access:
            return None
        return _ended_or_none(
            inner_decision, course_deadlines(record).time_limit, policy
        )

    def get_access(self, *, user: RequestUser, course: Course) -> CourseAccessDecision:
        inner = self._inner.get_access(user=user, course=course)
        if not user.is_authenticated:
            return inner
        ended = self._ended_decision(
            user=cast("User", user), course=course, inner_decision=inner
        )
        return ended or inner

    def get_access_for_request(
        self, *, request: HttpRequest, course: Course
    ) -> CourseAccessDecision:
        inner = self._inner.get_access_for_request(request=request, course=course)
        if not request.user.is_authenticated:
            return inner
        ended = self._ended_decision(
            user=cast("User", request.user), course=course, inner_decision=inner
        )
        return ended or inner

    def get_access_many(
        self, *, user: RequestUser, courses: Sequence[Course]
    ) -> dict[UUID, CourseAccessDecision]:
        """Every course's decision with the records, policies and time limits read in bulk.

        Only courses the inner backend grants content for are looked at, and a time limit
        is read only for a record whose policy ends access.
        """
        from freedom_ls.deadlines.loader import get_deadline_policy
        from freedom_ls.deadlines.resolver import course_deadlines_for
        from freedom_ls.learner_progress.queries import course_progress_by_course_for

        decisions = self._inner.get_access_many(user=user, courses=courses)
        if not user.is_authenticated:
            return decisions
        granted = [c for c in courses if decisions[c.pk].can_access_content]
        records = {
            course_id: record
            for course_id, record in course_progress_by_course_for(
                cast("User", user), granted
            ).items()
            if record.completed_time is None
        }
        policies = get_deadline_policy().resolve_for(list(records.values()))
        ending = [r for r in records.values() if policies[r.pk].end_course_access]
        deadlines = course_deadlines_for(ending)
        for record in ending:
            ended = _ended_or_none(
                decisions[record.course_id],
                deadlines[record.pk].time_limit,
                policies[record.pk],
            )
            if ended is not None:
                decisions[record.course_id] = ended
        return decisions

    def is_accessible_for_free(self, *, course: Course) -> bool:
        return self._inner.is_accessible_for_free(course=course)

    def get_access_badge(self, *, course: Course) -> AccessBadge | None:
        return self._inner.get_access_badge(course=course)

    def get_access_type(self, *, course: Course) -> str:
        return self._inner.get_access_type(course=course)

    def filter_visible(
        self, *, user: RequestUser, courses: QuerySet[Course]
    ) -> QuerySet[Course]:
        return self._inner.filter_visible(user=user, courses=courses)

    def validate_course_config(
        self,
        raw: dict[str, Any],
        *,
        file_path: str = "",
    ) -> dict[str, Any]:
        return self._inner.validate_course_config(raw, file_path=file_path)

    def get_dashboard_contributions(
        self, *, user: RequestUser
    ) -> list[DashboardContribution]:
        return self._inner.get_dashboard_contributions(user=user)

    def get_dashboard_contributions_for_request(
        self, *, request: HttpRequest
    ) -> list[DashboardContribution]:
        return self._inner.get_dashboard_contributions_for_request(request=request)
