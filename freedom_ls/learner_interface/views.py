from __future__ import annotations

import contextlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, cast

from pydantic import ValidationError as PydanticValidationError

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import Site
from django.db import transaction
from django.db.models import Q
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
    QueryDict,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.vary import vary_on_headers

from freedom_ls.accounts.decorators import acquisition_login_required
from freedom_ls.accounts.utils import get_client_ip
from freedom_ls.content_engine.course_details import course_details_context
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CourseCategory,
    CourseVisibility,
    Topic,
)
from freedom_ls.content_engine.models.courses import live_collection_items
from freedom_ls.course_access.analytics_events import (
    record_course_completed,
    record_course_self_registered,
    record_course_started,
)
from freedom_ls.course_access.loader import get_course_access_backend
from freedom_ls.course_access.overrides import (
    is_coming_soon_for_display,
    override_visibility_to_visible,
)
from freedom_ls.course_access.visibility import raise_404_if_unavailable
from freedom_ls.course_interest.queries import stamp_interest
from freedom_ls.course_recommendations.models import RecommendedCourse
from freedom_ls.course_recommendations.queries import get_recommended_courses
from freedom_ls.deadlines.consequences import (
    is_closed,
)
from freedom_ls.deadlines.loader import get_deadline_policy
from freedom_ls.deadlines.models import AfterAccessEnded
from freedom_ls.deadlines.policy import ResolvedDeadlinePolicy
from freedom_ls.deadlines.queries import pauses_for
from freedom_ls.deadlines.resolver import (
    CourseDeadlines,
    course_deadlines,
    course_deadlines_for,
)
from freedom_ls.form_engine.conditions import (
    SittingPath,
    current_path,
    sitting_path,
)
from freedom_ls.form_engine.declarations import (
    form_requires_declaration,
    sitting_needs_declaration,
)
from freedom_ls.form_engine.enums import CompletionReason
from freedom_ls.form_engine.live_tree import live_options
from freedom_ls.form_engine.models import (
    TIME_UP_LEAD,
    Form,
    FormDeclaration,
    FormProgress,
    FormQuestion,
    FormStrategy,
)
from freedom_ls.form_engine.page_flow import (
    CurrentPage,
    PageSubmission,
    off_path_landing,
    page_at,
    page_context,
    render_form_page,
    resolve_page,
    submit_page,
)
from freedom_ls.form_engine.paging import (
    answered_counts,
    first_page_number_with_unanswered_required,
    resume_page_number,
    unanswered_required_in_form,
    unanswered_required_message,
)
from freedom_ls.form_engine.queries import (
    count_sitting_pages,
    count_sitting_questions,
    stored_score_outdated,
)
from freedom_ls.form_engine.served_paper import ensure_served_paper
from freedom_ls.learner_management.learner_actions import self_register
from freedom_ls.learner_management.queries import (
    is_course_open_to_organisation,
    learner_for_course,
    own_organisation_for_course,
)
from freedom_ls.learner_progress.attempts import (
    close_left_signed_sitting,
    completed_attempts,
    finalise_stale_incomplete,
    get_latest_incomplete,
    sittings_at_placement,
    start_attempt,
)
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.learner_progress.queries import (
    completed_collection_item_ids,
    course_progress_by_course_for,
    course_progress_for,
)
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.referral_tracking.conversions import record_conversion
from freedom_ls.referral_tracking.models import ConversionKind
from freedom_ls.revision.models import RevisionReview
from freedom_ls.revision.queries import (
    bank_questions,
    question_sections,
    ready_count,
    section_first_placement,
)
from freedom_ls.revision.services import (
    GuessRefused,
    RevisionSessionState,
    build_session,
    mark_guessed,
    record_answer,
    session_reviews,
    session_summary,
    shuffled_options,
)
from freedom_ls.site_aware_models.models import get_cached_site
from freedom_ls.site_aware_models.time_zones import shows_time_zone_to_learners

from .dashboard_sections import (
    BuiltInSection,
    DashboardSection,
    htmx_target,
    page_for,
    requested_section_slug,
)
from .forms import FormDeclarationForm
from .utils import (
    BLOCKED,
    CLOSED,
    IN_PROGRESS,
    READY,
    UNRESOLVED,
    CourseListingStatus,
    OutlineMode,
    Unresolved,
    card_deadline_line,
    course_reference_topics,
    current_entry,
    current_entry_status,
    derive_listing_status,
    form_start_page_buttons,
    get_all_courses,
    get_completed_courses,
    get_course_index,
    get_course_listing,
    get_course_registrations,
    get_current_courses,
    get_form_collection_item_for_index,
    get_is_registered,
    get_item_part,
    get_resume_index,
    item_rows,
    next_deadline_card,
    next_entry,
    outstanding_items,
    previous_entry,
    reference_outline,
    reference_topic_url,
    stamp_card_organisation,
    stamp_course_access_badge,
)


def _annotate_next_up(
    course: Course,
    user,
    *,
    can_access_content: bool,
    course_progress: CourseProgress | None | Unresolved,
    course_deadlines: CourseDeadlines | None,
    deadline_policy: ResolvedDeadlinePolicy | None,
    now: datetime,
) -> None:
    """Pick the first IN_PROGRESS child (then READY) and stamp it on the course.

    Walks at most two levels of ``get_course_index`` (top-level children plus
    their direct children — which matches the depth ``get_course_index``
    itself produces). Sets empty strings when nothing is actionable so the
    template never renders ``Next up:`` with a blank tail.

    ``can_access_content`` is passed through from the dashboard's per-course
    backend decision so that get_course_index is not called with a stale value.

    ``course_progress``, ``course_deadlines`` and ``deadline_policy`` are the resolved
    record, its deadlines and its policy, handed on so none is resolved again per course. The same walk
    stamps the card's deadline line.
    """
    children = get_course_index(
        user=user,
        course=course,
        can_access_content=can_access_content,
        course_progress=course_progress,
        course_deadlines=course_deadlines,
        deadline_policy=deadline_policy,
        now=now,
    )
    flat = []
    for c in children:
        flat.append(c)
        flat.extend(c.get("children", []))
    next_item = next(
        (c for c in flat if c["status"] == IN_PROGRESS and c.get("url")),
        None,
    ) or next(
        (c for c in flat if c["status"] == READY and c.get("url")),
        None,
    )
    setattr(course, "next_up_title", next_item["title"] if next_item else "")  # noqa: B010
    setattr(course, "next_up_url", next_item["url"] if next_item else "")  # noqa: B010
    line = card_deadline_line(children, course_deadlines, deadline_policy, now)
    setattr(course, "missed_deadline", line.missed)  # noqa: B010
    setattr(course, "next_deadline", line.next)  # noqa: B010
    setattr(course, "access_ends_at", line.access_ends_at)  # noqa: B010


def _detail_start_url(course: Course, *, is_registered: bool, has_items: bool) -> str:
    """URL the detail page's CTA button should target.

    Unregistered learners go through ``initiate_course_access`` (idempotent
    registration + redirect). Already-registered, 0-progress learners skip
    that step and land directly on the first course item; if the course has
    no items, fall back to ``course_home``.

    A completed learner (CTA label "Review course", see ``_detail_cta_label``)
    intentionally reuses the first-item target — reviewing starts from the
    beginning — so the two functions stay in sync without branching on
    completion here.
    """
    if not is_registered:
        return reverse(
            "learner_interface:initiate_course_access",
            kwargs={"course_slug": course.slug},
        )
    if has_items:
        return reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    return reverse(
        "learner_interface:course_home",
        kwargs={"course_slug": course.slug},
    )


def _detail_cta_label(progress: CourseProgress | None) -> str:
    """Progress-aware CTA label for a registered learner on the course detail page.

    Reads the resolved record the caller passes — does not scan
    TopicProgress/FormProgress. Only call this for registered learners;
    unregistered paths use decision.cta_label.

    "Start course" is keyed on the percentage, never on the row existing: a
    record is minted by the registration, so a learner who has never opened the
    course still has one.
    """
    if progress is None or progress.completed_time is None:
        if progress is not None and progress.progress_percentage > 0:
            return "Continue"
        return "Start course"
    return "Review course"


def _visible_recommendations(
    user, backend: CourseAccessBackend
) -> list[RecommendedCourse]:
    """Recommended courses for the user, minus any the visibility gate hides.

    Route recommendations through the shared visibility gate rather than
    re-implementing the hidden rule here: filter_visible drops hidden courses the
    user is not registered for (and keeps coming-soon), so a hidden course can
    never leak as a clickable recommendation card and this path cannot drift from
    the wrapper's rule. Only pks are queried; the already-fetched rec.course
    instances are reused for rendering.
    """
    recs = list(get_recommended_courses(user))
    visible_rec_ids = set(
        backend.filter_visible(
            user=user,
            courses=Course.objects.filter(pk__in=[rec.course_id for rec in recs]),
        ).values_list("pk", flat=True)
    )
    visible_recs = [rec for rec in recs if rec.course_id in visible_rec_ids]
    # created_at alone is not a total order: a form submission that
    # recommends several courses at once writes them all inside one
    # transaction, so ties fall back to the course slug.
    visible_recs.sort(key=lambda rec: (-rec.created_at.timestamp(), rec.course.slug))
    return visible_recs


def _stamp_single_organisation(course: Course) -> None:
    stamp_card_organisation(course, course.single_organisation())


def _annotate_registered_courses(
    courses: list[Course], user, backend: CourseAccessBackend
) -> None:
    """Stamp registration status, listing status, the next-up item and the deadline line.

    ``get_current_courses`` already excludes completed courses and stamps
    ``progress_percentage``, so the listing status here is only ever registered
    (0%) or in_progress (>0%).
    """
    records = course_progress_by_course_for(user, courses)
    now = timezone.now()
    decisions = backend.get_access_many(user=user, courses=courses)
    # Without content access the index carries no progress, so a finished item would
    # read as missed: deadlines are only resolved for records the learner can open.
    open_records = [
        record
        for course_id, record in records.items()
        if decisions[course_id].can_access_content
    ]
    deadlines_by_record = course_deadlines_for(open_records, now=now)
    policies_by_record = get_deadline_policy().resolve_for(open_records)
    for course in courses:
        setattr(course, "is_registered", True)  # noqa: B010
        setattr(  # noqa: B010
            course,
            "listing_status",
            derive_listing_status(
                is_registered=True,
                is_coming_soon=course.visibility == CourseVisibility.COMING_SOON,
                is_complete=False,
                progress_percentage=getattr(course, "progress_percentage", 0),
            ),
        )
        # Pass can_access_content from the backend decision so a future
        # backend (e.g. subscription-gated) could revoke access without a
        # separate check.
        course_decision = decisions[course.pk]
        setattr(course, "access_ended_at", course_decision.access_ended_at)  # noqa: B010
        setattr(course, "paused_at", course_decision.paused_at)  # noqa: B010
        setattr(  # noqa: B010
            course, "planned_resume_on", course_decision.planned_resume_on
        )
        record = records.get(course.pk)
        _annotate_next_up(
            course,
            user,
            can_access_content=course_decision.can_access_content,
            course_progress=record,
            course_deadlines=(
                deadlines_by_record.get(record.pk) if record is not None else None
            ),
            deadline_policy=(
                policies_by_record.get(record.pk) if record is not None else None
            ),
            now=now,
        )


def _annotate_completed_courses(courses: list[Course]) -> None:
    """Stamp the complete listing status onto each finished course.

    ``get_completed_courses`` only returns courses with a ``completed_time``, so
    every course here is complete regardless of visibility or progress.
    """
    for course in courses:
        setattr(  # noqa: B010
            course,
            "listing_status",
            derive_listing_status(
                is_registered=True,
                is_coming_soon=False,
                is_complete=True,
                progress_percentage=100,
            ),
        )


def _annotate_recommendations(recommendations: list[RecommendedCourse]) -> None:
    """Stamp is_registered and the listing status onto each recommendation's course.

    Recommendations are by definition not yet registered, so the status is
    coming_soon (coming-soon courses) or not_registered. The dashboard renders
    both through the same course_card.html, a plain detail link with no
    express-interest CTA, so no per-course interest lookup is needed here.
    """
    for rec in recommendations:
        setattr(rec.course, "is_registered", False)  # noqa: B010
        _stamp_single_organisation(rec.course)
        setattr(  # noqa: B010
            rec.course,
            "listing_status",
            derive_listing_status(
                is_registered=False,
                is_coming_soon=is_coming_soon_for_display(rec.course),
                is_complete=False,
                progress_percentage=0,
            ),
        )


def _discovery_courses(
    user: RequestUser, backend: CourseAccessBackend, excluded_ids: set[uuid.UUID]
) -> QuerySet[Course]:
    """Visible courses the user is neither registered for nor recommended.

    The shared base every discovery section filters further, so
    ``select_related("dashboard_category")`` is declared once here rather than
    at each section's call site. Runs for both auth states — anonymous visitors
    simply arrive with an empty registration half of ``excluded_ids``.
    """
    return (
        backend.filter_visible(user=user, courses=get_all_courses())
        .exclude(pk__in=excluded_ids)
        .select_related("dashboard_category")
    )


def _discovery_pools(
    courses: QuerySet[Course],
) -> tuple[QuerySet[Course], QuerySet[Course]]:
    """The Coming soon roll-up and the pool every other discovery section draws from.

    The two overlap deliberately: a coming-soon course whose dashboard category
    is shown belongs in both, so it flows into ``rest`` as well as the first
    queryset, and ``_category_section`` picks it up the same way it picks up
    any published course. A coming-soon course with no category, or a hidden
    one, has nowhere else to render and stays out of ``rest`` entirely.

    Reads the override rather than ``visibility`` alone, so the visibility
    preview keeps presenting every course as published: with it on, nothing is
    coming soon and the section disappears.
    """
    if override_visibility_to_visible():
        return courses.none(), courses
    is_coming_soon = Q(visibility=CourseVisibility.COMING_SOON)
    has_shown_category = Q(
        dashboard_category__show_on_dashboard=True,
        dashboard_category__retired_at__isnull=True,
    )
    return (
        courses.filter(is_coming_soon),
        courses.filter(~is_coming_soon | has_shown_category),
    )


def _annotate_discovery_courses(
    courses: list[Course], backend: CourseAccessBackend
) -> None:
    """Stamp the access badge and listing status onto each discovery course."""
    for course in courses:
        setattr(course, "is_registered", False)  # noqa: B010
        _stamp_single_organisation(course)
        stamp_course_access_badge(course, badge=backend.get_access_badge(course=course))
        setattr(  # noqa: B010
            course,
            "listing_status",
            derive_listing_status(
                is_registered=False,
                is_coming_soon=is_coming_soon_for_display(course),
                is_complete=False,
                progress_percentage=0,
            ),
        )


def _in_progress_section(
    request: HttpRequest,
    registered_courses: list[Course],
    user: RequestUser,
    backend: CourseAccessBackend,
) -> DashboardSection:
    """The In progress section. Always built, because it owns an empty state."""
    page_obj = page_for(request, BuiltInSection.IN_PROGRESS, registered_courses)
    courses = list(page_obj.object_list)
    _annotate_registered_courses(courses, user, backend)
    return DashboardSection(
        slug=BuiltInSection.IN_PROGRESS,
        heading="In progress",
        wrapper_id="current-courses",
        page_obj=page_obj,
        courses=courses,
    )


def _browse_all_url() -> str:
    """The catalogue link behind every Browse all courses button.

    Unparameterised: a section's button lands on the whole catalogue, not on
    that section's own slice of it.
    """
    return reverse("learner_interface:courses")


def _recommended_section(
    request: HttpRequest, recommendations: list[RecommendedCourse]
) -> DashboardSection:
    page_obj = page_for(request, BuiltInSection.RECOMMENDED, recommendations)
    page_recommendations = list(page_obj.object_list)
    _annotate_recommendations(page_recommendations)
    return DashboardSection(
        slug=BuiltInSection.RECOMMENDED,
        heading="Recommended courses",
        wrapper_id="recommended-courses",
        page_obj=page_obj,
        courses=[rec.course for rec in page_recommendations],
        browse_all_url=_browse_all_url(),
    )


def _category_section(
    request: HttpRequest,
    category: CourseCategory,
    rest: QuerySet[Course],
    backend: CourseAccessBackend,
) -> DashboardSection:
    page_obj = page_for(
        request, category.slug, rest.filter(dashboard_category=category)
    )
    courses = list(page_obj.object_list)
    _annotate_discovery_courses(courses, backend)
    return DashboardSection(
        slug=category.slug,
        heading=category.title,
        wrapper_id=f"category-{category.slug}",
        page_obj=page_obj,
        courses=courses,
        description=category.description,
        browse_all_url=_browse_all_url(),
    )


def _available_section(
    request: HttpRequest, rest: QuerySet[Course], backend: CourseAccessBackend
) -> DashboardSection:
    """The catch-all: uncategorised courses, plus those in a hidden category.

    Only ``dashboard_category`` decides this — a course whose dashboard
    category is hidden or retired lands here rather than in whichever of its other
    categories happens to have a section on screen. A coming-soon course can
    never reach this catch-all: ``rest`` only ever holds one with a shown
    category, so the filter below has nothing coming-soon left to exclude.
    """
    page_obj = page_for(
        request,
        BuiltInSection.AVAILABLE,
        rest.filter(
            Q(dashboard_category__isnull=True)
            | Q(dashboard_category__show_on_dashboard=False)
            | Q(dashboard_category__retired_at__isnull=False)
        ),
    )
    courses = list(page_obj.object_list)
    _annotate_discovery_courses(courses, backend)
    return DashboardSection(
        slug=BuiltInSection.AVAILABLE,
        heading="Available courses",
        wrapper_id="available-courses",
        page_obj=page_obj,
        courses=courses,
        browse_all_url=_browse_all_url(),
    )


def _coming_soon_section(
    request: HttpRequest, coming_soon: QuerySet[Course], backend: CourseAccessBackend
) -> DashboardSection:
    page_obj = page_for(request, BuiltInSection.COMING_SOON, coming_soon)
    courses = list(page_obj.object_list)
    _annotate_discovery_courses(courses, backend)
    return DashboardSection(
        slug=BuiltInSection.COMING_SOON,
        heading="Coming soon",
        wrapper_id="coming-soon-courses",
        page_obj=page_obj,
        courses=courses,
        browse_all_url=_browse_all_url(),
    )


def _history_section(
    request: HttpRequest, completed_courses: list[Course]
) -> DashboardSection:
    page_obj = page_for(request, BuiltInSection.HISTORY, completed_courses)
    courses = list(page_obj.object_list)
    _annotate_completed_courses(courses)
    return DashboardSection(
        slug=BuiltInSection.HISTORY,
        heading="Learning history",
        wrapper_id="learning-history",
        page_obj=page_obj,
        courses=courses,
    )


@dataclass(frozen=True)
class _DashboardInputs:
    """The per-request work every section is built from.

    Assembled once whichever branch runs: the category and catch-all sections
    exclude registered and recommended courses, so even a single-section htmx
    response needs all three lists.
    """

    is_auth: bool
    backend: CourseAccessBackend
    registered_courses: list[Course]
    completed_courses: list[Course]
    recommended_courses: list[RecommendedCourse]
    coming_soon: QuerySet[Course]
    rest: QuerySet[Course]


def _dashboard_inputs(
    request: HttpRequest, backend: CourseAccessBackend
) -> _DashboardInputs:
    is_auth = request.user.is_authenticated

    # These helpers are all anonymous-safe (return empty lists / querysets for
    # unauthenticated users), so they run unconditionally.
    registered_courses = get_current_courses(request.user)
    completed_courses = get_completed_courses(request.user)
    recommended_courses = _visible_recommendations(request.user, backend)

    excluded_ids = (
        {c.id for c in get_course_registrations(request.user)} if is_auth else set()
    ) | {rec.course_id for rec in recommended_courses}
    coming_soon, rest = _discovery_pools(
        _discovery_courses(request.user, backend, excluded_ids)
    )
    return _DashboardInputs(
        is_auth=is_auth,
        backend=backend,
        registered_courses=registered_courses,
        completed_courses=completed_courses,
        recommended_courses=recommended_courses,
        coming_soon=coming_soon,
        rest=rest,
    )


def _dashboard_sections(
    request: HttpRequest, inputs: _DashboardInputs
) -> list[DashboardSection]:
    """Every section this visitor sees, in the order they are rendered.

    The first category section is the site's headline group and sits above
    Recommended courses. In progress leads the page when it holds something and
    otherwise drops to just above Learning history, where its "waiting in your
    Learning History below" copy sits next to the history it names.
    """
    category_sections = [
        section
        for category in CourseCategory.objects.not_retired().filter(
            show_on_dashboard=True
        )
        if not (
            section := _category_section(request, category, inputs.rest, inputs.backend)
        ).is_empty
    ]
    in_progress = (
        _in_progress_section(
            request, inputs.registered_courses, request.user, inputs.backend
        )
        if inputs.is_auth
        else None
    )

    sections: list[DashboardSection] = []
    if in_progress is not None and not in_progress.is_empty:
        sections.append(in_progress)
    sections.extend(category_sections[:1])
    sections.append(_recommended_section(request, inputs.recommended_courses))
    sections.extend(category_sections[1:])
    sections.append(_available_section(request, inputs.rest, inputs.backend))
    sections.append(_coming_soon_section(request, inputs.coming_soon, inputs.backend))
    sections = [section for section in sections if not section.is_empty]
    if in_progress is not None and in_progress.is_empty:
        sections.append(in_progress)
    history = _history_section(request, inputs.completed_courses)
    if not history.is_empty:
        sections.append(history)
    return sections


def _requested_section(
    request: HttpRequest, inputs: _DashboardInputs, slug: str
) -> DashboardSection:
    """The one section an htmx page request asked for.

    Building only this section is the point of the swap: the other eight
    sections' page queries and per-course annotation are never paid for.
    A slug this visitor has no section for is a 404.
    """
    if (
        slug in {BuiltInSection.IN_PROGRESS, BuiltInSection.HISTORY}
        and not inputs.is_auth
    ):
        raise Http404("No such dashboard section.")
    if slug == BuiltInSection.IN_PROGRESS:
        return _in_progress_section(
            request, inputs.registered_courses, request.user, inputs.backend
        )
    if slug == BuiltInSection.HISTORY:
        return _history_section(request, inputs.completed_courses)
    if slug == BuiltInSection.RECOMMENDED:
        return _recommended_section(request, inputs.recommended_courses)
    if slug == BuiltInSection.AVAILABLE:
        return _available_section(request, inputs.rest, inputs.backend)
    if slug == BuiltInSection.COMING_SOON:
        return _coming_soon_section(request, inputs.coming_soon, inputs.backend)
    category = get_object_or_404(
        CourseCategory.objects.not_retired(), slug=slug, show_on_dashboard=True
    )
    return _category_section(request, category, inputs.rest, inputs.backend)


def _section_page_response(
    request: HttpRequest, inputs: _DashboardInputs, slug: str
) -> HttpResponse:
    """One section's page fragment, or its exit when nothing is left in it.

    A section that has drained since the page rendered (a course registered in
    another tab, a category hidden) leaves the page the way a reload shows it:
    the whole wrapper goes, or for In progress, gives way to its empty-state
    copy. Retargeting to the wrapper takes the heading with it.
    """
    section = _requested_section(request, inputs, slug)
    if not section.is_empty:
        return render(
            request,
            "learner_interface/partials/course_list.html#section-page-response",
            {"section": section, **_time_zone_context(request)},
        )
    response = render(
        request,
        "learner_interface/partials/course_list.html#section-gone-response",
        {"section": section, "has_history": bool(inputs.completed_courses)},
    )
    response["HX-Retarget"] = f"#{section.wrapper_id}"
    response["HX-Reswap"] = "outerHTML" if section.renders_when_empty else "delete"
    return response


def _time_zone_context(request: HttpRequest) -> dict[str, bool]:
    """Whether the cards' dates carry the site's zone label for this viewer."""
    return {
        "show_time_zone_to_learners": request.user.is_authenticated
        and shows_time_zone_to_learners(cast(Site, get_cached_site(request)))
    }


def _deadline_policy_or_none(
    course_progress: CourseProgress | None,
) -> ResolvedDeadlinePolicy | None:
    """The record's resolved deadline policy, or None when nothing grants the course."""
    if course_progress is None:
        return None
    return get_deadline_policy().resolve(course_progress)


def _deadlines_or_none(
    course_progress: CourseProgress | None, now: datetime | None = None
) -> CourseDeadlines | None:
    """The record's resolved deadlines at ``now``, or None when nothing grants the course."""
    return (
        course_deadlines(course_progress, now=now)
        if course_progress is not None
        else None
    )


def _requested_panel(
    request: HttpRequest, contributions: list[DashboardContribution]
) -> DashboardContribution | None:
    """The backend panel whose own swap an htmx request names in ``HX-Target``."""
    target = htmx_target(request)
    if target is None:
        return None
    return next((c for c in contributions if c.swap_id == target), None)


@vary_on_headers("HX-Request", "HX-Target")
def dashboard(request: HttpRequest) -> HttpResponse:
    """Dashboard view — authenticated or anonymous, whole page or one fragment.

    Authenticated users see their personalised course lists, backend-contributed
    panels, and the welcome greeting. Anonymous users see a hero, any panel the
    backend contributes for their session, and the discovery sections. An htmx
    request naming a section's swap target in ``HX-Target`` gets that section's
    page fragment, and one naming a backend panel's swap id gets that panel on
    its own; any other htmx request, a boosted navigation included, gets the
    whole page.
    """
    backend = get_course_access_backend()
    slug = requested_section_slug(request)
    if slug is not None:
        return _section_page_response(
            request, _dashboard_inputs(request, backend), slug
        )

    # Panels come from the active backend, for every visitor: the backend decides
    # what an anonymous session may see of its own.
    contributions = backend.get_dashboard_contributions_for_request(request=request)
    panel = _requested_panel(request, contributions)
    if panel is not None:
        return render(request, panel.template_name, panel.context)

    inputs = _dashboard_inputs(request, backend)
    dashboard_panels = [
        render_to_string(c.template_name, c.context, request=request)
        for c in contributions
    ]

    context = {
        "sections": _dashboard_sections(request, inputs),
        "dashboard_panels": dashboard_panels,
        "has_history": bool(inputs.completed_courses),
        **_time_zone_context(request),
    }
    return render(request, "learner_interface/dashboard.html", context)


def all_courses(request: HttpRequest) -> HttpResponse:
    """Flat list of all courses — public, no login required.

    Anonymous visitors see every site course with an access badge ("Free" or
    "By application"). Authenticated visitors additionally see their registration
    status and progress. The badge label is stamped once here (from the listing
    builder) so row/card templates never call the backend or read access_config.
    """
    backend = get_course_access_backend()
    entries = get_course_listing(
        request.user,
        visible_courses=backend.filter_visible(
            user=request.user, courses=get_all_courses()
        ),
    )
    courses_with_attrs = []
    now = timezone.now()
    in_player = (CourseListingStatus.REGISTERED, CourseListingStatus.IN_PROGRESS)
    decisions = backend.get_access_many(
        user=request.user,
        courses=[entry.course for entry in entries if entry.status in in_player],
    )
    for entry in entries:
        course = entry.course
        setattr(course, "listing_status", entry.status)  # noqa: B010
        setattr(course, "progress_percentage", entry.progress_percentage)  # noqa: B010
        stamp_course_access_badge(course, badge=entry.access_badge)
        _stamp_single_organisation(course)
        if entry.status in in_player:
            decision = decisions[course.pk]
            setattr(course, "access_ended_at", decision.access_ended_at)  # noqa: B010
            setattr(course, "paused_at", decision.paused_at)  # noqa: B010
            setattr(course, "planned_resume_on", decision.planned_resume_on)  # noqa: B010
            # The listing resolved the record already; the catalogue shows no
            # deadline line, so none are resolved here.
            _annotate_next_up(
                course,
                request.user,
                can_access_content=decision.can_access_content,
                course_progress=entry.course_progress,
                course_deadlines=None,
                deadline_policy=None,
                now=now,
            )
        courses_with_attrs.append(course)

    # JSON-LD for schema.org/ItemList — each item carries its absolute detail URL.
    catalogue_json_ld: dict[str, object] = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": idx + 1,
                "url": request.build_absolute_uri(
                    reverse(
                        "learner_interface:course_detail",
                        kwargs={"course_slug": c.slug},
                    )
                ),
                "name": c.title,
            }
            for idx, c in enumerate(courses_with_attrs)
        ],
    }

    return render(
        request,
        "learner_interface/all_courses.html",
        {
            "all_courses": courses_with_attrs,
            "catalogue_json_ld": catalogue_json_ld,
        },
    )


def course_detail(request: HttpRequest, course_slug: str) -> HttpResponse:
    """Canonical course detail page — accessible on all screen sizes."""
    course = get_object_or_404(
        Course.objects.select_related("dashboard_category").prefetch_related(
            "organisations"
        ),
        slug=course_slug,
    )
    # Two distinct registration signals, intentionally both fetched: is_registered
    # drives the template (TOC partialdef) and the three-state CTA vocabulary, while
    # decision.can_access_content drives the content gate. They diverge for an
    # invalid-config course, so neither can be derived from the other.
    is_registered = get_is_registered(user=request.user, course=course)
    # Hidden courses 404 for anyone not registered, matching the wrapper's
    # filter_visible rule (coming_soon and published detail pages stay accessible).
    raise_404_if_unavailable(request.user, course)
    decision = get_course_access_backend().get_access_for_request(
        request=request, course=course
    )
    # get_course_index is anonymous-safe (it fetches user-scoped progress
    # only behind its own is_authenticated / can_access_content guards).
    course_progress = (
        course_progress_for(cast("User", request.user), course)
        if is_registered
        else None
    )
    shows_ended_outline = _shows_ended_outline(decision)
    paused = decision.paused_at is not None
    # Deadlines are resolved so a closed item reads Closed here as it does in the
    # player; the template shows none of their dates, which belong to the player.
    # Only an open row can close, so the lookups are skipped where no row is open:
    # without content access every row is locked, and so is every unfinished row of
    # an ended learner's outline. A policy that closes nothing needs no deadlines.
    deadline_policy = (
        _deadline_policy_or_none(course_progress)
        if decision.can_access_content
        else None
    )
    course_deadlines = (
        _deadlines_or_none(course_progress)
        if deadline_policy is not None and deadline_policy.close_items
        else None
    )
    children = (
        []
        if decision.access_ended_at is not None and not shows_ended_outline
        else get_course_index(
            user=request.user,
            course=course,
            can_access_content=decision.can_access_content,
            course_progress=course_progress,
            course_deadlines=course_deadlines,
            deadline_policy=deadline_policy,
            outline_mode=_outline_mode(decision),
        )
    )
    start_url: str | None
    cta_label: str | None
    secondary_cta_label: str | None = None
    secondary_cta_url: str | None = None
    access_ended = decision.access_ended_at is not None
    if access_ended or paused:
        # An ended or paused learner is offered nothing to start, continue or register for.
        start_url = None
        cta_label = None
    elif is_registered:
        # Registered learners get the richer progress-aware helpers: "Start course",
        # "Continue", "Review course". Do NOT route registered learners through
        # decision.cta_label — it would regress the three-state vocabulary to "Continue".
        start_url = _detail_start_url(
            course, is_registered=True, has_items=bool(children)
        )
        cta_label = _detail_cta_label(course_progress)
    else:
        # Not-registered: use the backend's acquisition affordance (e.g. "Enrol for free"
        # for free courses, "Apply now" for application-gated courses). May be None for
        # backends that provide no CTA (e.g. invalid config) — <c-button href=""> renders disabled.
        start_url = decision.cta_url
        cta_label = decision.cta_label
        secondary_cta_label = decision.secondary_cta_label
        secondary_cta_url = decision.secondary_cta_url
    # Coming-soon courses render the shared express-interest control in the
    # not-registered branch instead of the generic enrol anchor (which would
    # GET a POST-only endpoint and can't reflect existing interest). Stamp the
    # course's current interest state so the partial picks the right variant.
    is_coming_soon = is_coming_soon_for_display(course)
    if is_coming_soon and not is_registered:
        stamp_interest(request.user, [course])
    # meta_description: derived once here; reused by JSON-LD (never re-derived there).
    meta_description: str = (
        course.description
        or course.subtitle
        or "Explore this course and expand your skills."
    )

    # JSON-LD for schema.org/Course — only honestly-sourced fields; no provider/image/author.
    course_url = request.build_absolute_uri(
        reverse("learner_interface:course_detail", kwargs={"course_slug": course.slug})
    )
    json_ld: dict[str, object] = {
        "@context": "https://schema.org",
        "@type": "Course",
        "name": course.title,
        "description": meta_description,
        "url": course_url,
        "isAccessibleForFree": decision.is_accessible_for_free,
    }
    if course.get_difficulty_display():
        json_ld["educationalLevel"] = course.get_difficulty_display()
    iso_duration = course.iso_estimated_duration()
    if iso_duration:
        json_ld["timeRequired"] = iso_duration
    if course.learning_outcomes:
        json_ld["teaches"] = course.learning_outcomes
    price = course.current_price()
    offers = price.offers_json_ld() if price else None
    if offers:
        json_ld["offers"] = offers

    return render(
        request,
        "learner_interface/course_detail.html",
        {
            "course": course,
            **course_details_context(course),
            # The reference pages need a signed-in learner, so a backend that
            # grants an anonymous request content access gets the titles alone.
            "reference_outline": reference_outline(
                course,
                linked=request.user.is_authenticated and decision.can_access_content,
            ),
            "extra_stats": (
                [
                    {
                        "icon": "check",
                        "label": "Enrolment",
                        "value": decision.enrolment_summary,
                    }
                ]
                if decision.enrolment_summary
                else []
            ),
            "children": children,
            "is_registered": is_registered,
            "is_coming_soon": is_coming_soon,
            "start_url": start_url,
            "cta_label": cta_label,
            "secondary_cta_label": secondary_cta_label,
            "secondary_cta_url": secondary_cta_url,
            "access_ended_at": decision.access_ended_at,
            "paused_at": decision.paused_at,
            "planned_resume_on": decision.planned_resume_on,
            **_time_zone_context(request),
            # Acquisition-funnel copy is access-type-specific and comes from the
            # backend decision (not the CTA-state helpers above), so it is correct
            # for gated courses as well as free ones.
            "acquisition_heading": decision.acquisition_heading,
            "acquisition_subtext": decision.acquisition_subtext,
            "meta_description": meta_description,
            "json_ld": json_ld,
        },
    )


@login_required
def course_home(request, course_slug):
    """Resume redirector for the bare course URL.

    Never renders a start page. Anonymous users hit the login flow via
    ``login_required``. Learners without content access (per the access
    backend) go to the loop-free detail page.
    Learners with content access 302 to their resume item (first item with no progress,
    last-accessed item otherwise) — a different canonical URL, with nothing in
    the player linking back here, so the browser Back button cannot loop.
    """
    course = get_object_or_404(Course, slug=course_slug)
    # Hidden courses 404 for anyone not registered, matching every other slug
    # chokepoint — never leak existence via a 302-vs-404 divergence.
    raise_404_if_unavailable(request.user, course)

    if (
        not get_course_access_backend()
        .get_access(user=request.user, course=course)
        .can_access_content
    ):
        return redirect("learner_interface:course_detail", course_slug=course_slug)

    index = get_resume_index(request.user, course)
    return redirect(
        "learner_interface:view_course_item",
        course_slug=course_slug,
        index=index,
    )


@acquisition_login_required
def initiate_course_access(request, course_slug):
    """Act on a learner's intent to get into a course.

    The single server-side chokepoint for self-service course access. Consults
    the active access backend, which decides what the action resolves to: for a
    free course it self-registers the learner; for a gated course (e.g.
    application-backed) it redirects to the backend's CTA (the apply page).
    Admin/cohort registration paths are untouched by this gate.
    """

    course = get_object_or_404(Course, slug=course_slug)

    # Enforce course visibility, mirroring the apply view: hidden courses 404 for
    # unregistered users, and coming-soon courses are not enrollable — route to the
    # detail page's express-interest CTA. (The coming-soon decision's cta_url is the
    # POST-only express-interest endpoint, so redirecting the browser there would 405.)
    # The visibility preview override lifts the coming-soon gate so the course flows
    # through to the backend's free self-registration.
    raise_404_if_unavailable(request.user, course)
    if (
        course.visibility == CourseVisibility.COMING_SOON
        and not override_visibility_to_visible()
    ):
        return redirect("learner_interface:course_detail", course_slug=course.slug)

    # Chokepoint gate: consult the active backend before allowing self-registration.
    # If the backend does not permit self-registration (e.g. application-gated courses),
    # redirect to the backend's CTA URL (e.g. the apply page) or to course_detail
    # as the loop-free fallback.
    decision = get_course_access_backend().get_access(user=request.user, course=course)
    if not decision.can_self_register:
        target = decision.cta_url
        return (
            redirect(target)
            if target
            else redirect("learner_interface:course_detail", course_slug=course_slug)
        )

    # The registration lands on the organisation of this course the learner
    # already belongs to, so their card and player chip carry it. Without such
    # a row it lands on the Site's default Organisation, guaranteed to exist by
    # the post_save receiver that gives every Site one. That fallback is reached
    # for a public organisation course and a course with no organisations; the
    # audience gate already 404s everyone else. self_register reactivates a
    # deactivated learner, so re-registering is a live signal of
    # re-association.
    organisation = own_organisation_for_course(
        request.user, course
    ) or get_default_organisation(
        # get_cached_site's RequestSite branch only applies with the Sites
        # framework absent, which FLS always has installed.
        cast(Site, get_cached_site(request))
    )
    # The audience gate and the free backend stop everyone else before this
    # point, but the visibility preview override lifts the audience gate and
    # another access backend may let a registered user self-register. Either
    # would otherwise register the learner through an organisation the course
    # is not open to.
    if not is_course_open_to_organisation(course, organisation):
        return redirect("learner_interface:course_detail", course_slug=course.slug)
    registration = self_register(request.user, organisation, course)
    # Only a new registration. Reactivating one an admin had switched off is
    # not a second registration, and a repeat visit to this URL is not one either.
    if registration is not None:
        record_course_self_registered(request, course)
        record_conversion(
            user=cast("User", request.user),
            kind=ConversionKind.COURSE_REGISTRATION,
            target=registration,
            occurred_at=registration.registered_at,
            target_label=course.title,
        )

    # Redirect into the player. course_home is now a resume redirector, so a
    # freshly registered (0-progress) learner lands on the first course item.
    return redirect("learner_interface:course_home", course_slug=course_slug)


class PlayerRoute(StrEnum):
    """The kinds of player route, which an ended learner may or may not still reach."""

    ITEM = "item"
    FORM_RESULTS = "form_results"
    SUBMIT_AND_EXIT = "submit_and_exit"
    FINISH = "finish"
    REVISION = "revision"


def _course_access_decision(user: RequestUser, course: Course) -> CourseAccessDecision:
    """A retired or hidden course 404s before the backend is asked, so a redirect never confirms it exists."""
    raise_404_if_unavailable(user, course)
    return get_course_access_backend().get_access(user=user, course=course)


@dataclass(frozen=True)
class OpenSitting:
    """A learner's open sitting at a placement and the record it belongs to."""

    course_progress: CourseProgress
    sitting: FormProgress


def _open_sitting_at(
    user: User, course: Course, collection_item: ContentCollectionItem
) -> OpenSitting | None:
    """The learner's open sitting at the placement, read-only.

    Reads the course progress record without minting one, so a learner who has
    never started the course is not given one by a request that only looks.
    """
    record = course_progress_for(user, course)
    if record is None:
        return None
    sitting = get_latest_incomplete(record, collection_item)
    return None if sitting is None else OpenSitting(record, sitting)


def _complete_expired_sitting(found: OpenSitting | None, now: datetime) -> bool:
    """Complete the open sitting if its time has run out, and say whether it did.

    Runs ahead of every access gate: the clock does not stop for a pause, a
    closed item or ended access, so those learners' sittings end here too.
    """
    if found is None or not found.sitting.is_expired(now):
        return False  # the common path takes no lock
    with transaction.atomic():
        # Record first, then sitting: the order start_attempt takes them in.
        CourseProgress.objects.select_for_update().get(pk=found.course_progress.pk)
        return found.sitting.complete_if_expired(now)


def _expired_sitting_redirect(
    user: User,
    course: Course,
    collection_item: ContentCollectionItem,
    index: int,
    found: OpenSitting | None = None,
) -> HttpResponseRedirect | None:
    """The results redirect for a sitting this request just completed as expired.

    A caller that has already looked the open sitting up passes it as `found`,
    so the request reads it once.
    """
    if found is None:
        found = _open_sitting_at(user, course, collection_item)
    if not _complete_expired_sitting(found, timezone.now()):
        return None
    return redirect(
        "learner_interface:course_form_complete",
        course_slug=course.slug,
        index=index,
    )


def _save_page_and_complete(
    course_progress: CourseProgress,
    sitting: FormProgress,
    page_number: int | None,
    post_data: QueryDict,
    now: datetime,
    *,
    time_up: bool,
) -> bool:
    """Save the posted page to a sitting whose time has just run out, then
    complete it, as one step no other request can come between.

    `time_up` says the countdown sent the post, which is believed from just
    before the sitting expiry; any other post only from the expiry on. The window
    is checked on the locked row, so it is closed for a sitting another request
    completed meanwhile, and nothing is saved then.
    """
    in_window = FormProgress.accepts_time_up if time_up else FormProgress.in_grace
    with transaction.atomic():
        # Record first, then sitting: the order start_attempt takes them in.
        # complete()'s receivers write the record while the sitting is held.
        CourseProgress.objects.select_for_update().get(pk=course_progress.pk)
        locked = FormProgress.objects.select_for_update(of=("self",)).get(pk=sitting.pk)
        if not in_window(locked, now):
            return False
        # An unsigned sitting was served nothing, so it has no page to save.
        if page_number is not None and not sitting_needs_declaration(locked):
            ensure_served_paper(locked)
            page = page_at(current_path(locked), page_number)
            if page is not None:
                # Rejected answers are dropped: the valid ones are stored, and a
                # rejection must not re-render the page or leave the sitting open.
                submit_page(page, post_data, locked, require_answers=False)
        locked.complete(
            CompletionReason.TIME_EXPIRED,
            time_up_lead=TIME_UP_LEAD if time_up else timedelta(0),
        )
        return locked.completed_time is not None


def _course_access_redirect(
    decision: CourseAccessDecision,
    course: Course,
    *,
    route: PlayerRoute,
    collection_item: ContentCollectionItem | None = None,
    course_progress: CourseProgress | None = None,
) -> HttpResponseRedirect | None:
    """Turn away anyone the course is closed to, or None if this route is open to them.

    The same gate for every route that serves or accepts a course item: the access
    backend decides whether this learner may see content at all. A learner whose access
    ended is turned away too, and so is a learner whose course is paused, except from the
    routes ``_read_only_route_redirect`` leaves open to each.
    """
    if decision.can_access_content:
        return None
    paused = decision.paused_at is not None
    if not paused and decision.access_ended_at is None:
        return redirect("learner_interface:course_detail", course_slug=course.slug)
    # A pause freezes work in flight, so nothing that writes stays open; a learner whose
    # access ended may still finalise an open attempt.
    return _read_only_route_redirect(
        course,
        route=route,
        collection_item=collection_item,
        course_progress=course_progress,
        submit_open=not paused,
        finished_items_open=paused or _shows_ended_outline(decision),
    )


def _is_complete_for_learner(
    course_progress: CourseProgress | None, collection_item: ContentCollectionItem
) -> bool:
    """One rule for "this item is complete for this learner": the stored one the percentage reads."""
    return (
        course_progress is not None
        and collection_item.pk in completed_collection_item_ids(course_progress)
    )


def _is_closed_for_learner(
    course_progress: CourseProgress | None,
    collection_item: ContentCollectionItem,
    now: datetime,
) -> bool:
    """Whether this placement has closed for this learner: its own deadline and the
    record's policy, with no course index built."""
    if course_progress is None:
        return False
    resolved = course_deadlines(course_progress, now=now).items.get(collection_item.pk)
    if resolved is None:
        return False
    return is_closed(
        resolved,
        get_deadline_policy().resolve(course_progress),
        _is_complete_for_learner(course_progress, collection_item),
        now,
    )


def _read_only_route_redirect(
    course: Course,
    *,
    route: PlayerRoute,
    collection_item: ContentCollectionItem | None,
    course_progress: CourseProgress | None,
    submit_open: bool,
    finished_items_open: bool,
) -> HttpResponseRedirect | None:
    """What a learner without content access may still reach, else a redirect to the
    detail page.

    The results of a completed attempt always stay open: a learner is entitled to the
    score they earned, and a completed attempt is not the same as a completed item (a
    failed sitting still has a score to show). ``submit_open`` keeps submit-and-exit open
    so an open attempt can be finalised; ``finished_items_open`` keeps a finished item
    readable. A form's start and fill-in routes stay shut, so nothing is re-sat.
    """
    if submit_open and route is PlayerRoute.SUBMIT_AND_EXIT:
        return None
    if (
        route is PlayerRoute.FORM_RESULTS
        and course_progress is not None
        and collection_item is not None
        and completed_attempts(course_progress, collection_item).exists()
    ):
        return None
    if (
        route is PlayerRoute.ITEM
        and finished_items_open
        and collection_item is not None
        and _is_complete_for_learner(course_progress, collection_item)
    ):
        return None
    return redirect("learner_interface:course_detail", course_slug=course.slug)


def _latest_pause_start(course_progress: CourseProgress) -> datetime | None:
    """When the record's most recent pause began, or None if it was never paused. A
    sitting untouched since then was interrupted by the pause, not left."""
    pauses = pauses_for([course_progress]).get(course_progress.pk, [])
    return max((pause.started_at for pause in pauses), default=None)


def _outline_mode(decision: CourseAccessDecision) -> OutlineMode:
    """How much of the outline this learner sees beyond what content access decides."""
    if decision.paused_at is not None:
        return OutlineMode.PAUSED
    if _shows_ended_outline(decision):
        return OutlineMode.ENDED
    return OutlineMode.FULL


def _shows_ended_outline(decision: CourseAccessDecision) -> bool:
    """Whether a learner whose access ended still sees the course outline and results."""
    return (
        decision.access_ended_at is not None
        and decision.after_access_ended == AfterAccessEnded.OUTLINE_AND_RESULTS
    )


def _blocked_item_redirect(
    user: RequestUser,
    course: Course,
    index: int,
    *,
    course_index: list[dict] | None = None,
    course_progress: CourseProgress | None | Unresolved = UNRESOLVED,
    refuse_closed: bool = False,
) -> HttpResponseRedirect | None:
    """Turn away an item the course index shows as BLOCKED, or None if it is open.

    With ``refuse_closed`` a CLOSED item is sent to its own player page, which renders
    the closed notice instead of the item. The routes that start or fill in a form set
    it; the player page does not, since it is the page that draws the notice.

    Sequential unlock used to live only in the table of contents, which drew a
    locked item as unlinked text and left its URL open. Reading the decision off
    the same index the template renders is what keeps the two in step.

    Callers that have already built the index pass it in; it is not cached, and
    the view builds it for the player chrome anyway. Callers that have already
    resolved the record pass that too, so it is not resolved twice.
    """
    if course_index is None:
        course_index = get_course_index(
            user=user,
            course=course,
            current_index=index,
            can_access_content=True,
            course_progress=course_progress,
        )
    status = current_entry_status(course_index)
    if status == BLOCKED:
        # course_detail, never course_home: course_home resumes to the last item
        # accessed, which would bounce straight back here.
        return redirect("learner_interface:course_detail", course_slug=course.slug)
    if refuse_closed and status == CLOSED:
        # The item's own page draws the closed notice, with the submit button for
        # an open attempt. It records no visit, so nothing resumes back here.
        return redirect(
            "learner_interface:view_course_item", course_slug=course.slug, index=index
        )
    return None


@dataclass(frozen=True)
class PlayerCourseIndex:
    """The outline the player gates and chrome both read, with what it was resolved from, so
    the deadline the panel names is picked from the same rows and instants as the gates."""

    rows: list[dict]
    course_deadlines: CourseDeadlines | None
    deadline_policy: ResolvedDeadlinePolicy | None
    now: datetime

    @classmethod
    def empty(cls) -> PlayerCourseIndex:
        """An outline with no rows: what the chrome draws when the policy keeps nothing."""
        return cls(
            rows=[], course_deadlines=None, deadline_policy=None, now=timezone.now()
        )


def _player_course_index(
    user: RequestUser,
    course: Course,
    index: int,
    course_progress: CourseProgress | None,
    *,
    outline_mode: OutlineMode = OutlineMode.FULL,
) -> PlayerCourseIndex:
    """The outline the player gates and chrome both read, with deadlines resolved from the
    record so every gate sees blocking and closing as the learner's table of contents does.

    ``outline_mode`` withholds rows as ``OutlineMode`` describes; a paused outline
    resolves no deadline or policy."""
    now = timezone.now()
    if outline_mode is OutlineMode.PAUSED:
        rows = get_course_index(
            user=user,
            course=course,
            current_index=index,
            can_access_content=False,
            course_progress=course_progress,
            now=now,
            outline_mode=outline_mode,
        )
        return PlayerCourseIndex(rows, None, None, now)
    course_deadlines = _deadlines_or_none(course_progress, now)
    deadline_policy = _deadline_policy_or_none(course_progress)
    rows = get_course_index(
        user=user,
        course=course,
        current_index=index,
        can_access_content=True,
        course_progress=course_progress,
        course_deadlines=course_deadlines,
        deadline_policy=deadline_policy,
        now=now,
        outline_mode=outline_mode,
    )
    return PlayerCourseIndex(rows, course_deadlines, deadline_policy, now)


def _unlocked_next_url(next_url: str | None, course_index: list[dict]) -> str | None:
    """``next_url``, unless the outline shows the row after the current one as BLOCKED.

    A closed item unlocks nothing after it, so a Next or Continue to that row would only
    bounce the learner to the course detail page."""
    after = next_entry(course_index)
    return None if after is not None and after["status"] == BLOCKED else next_url


def _unlocked_previous_url(
    previous_url: str | None, course_index: list[dict]
) -> str | None:
    """``previous_url``, unless the outline shows the row before the current one as
    BLOCKED.

    A closed item can be reachable while the item before it is still locked, so a
    Previous to that row would only bounce the learner to the course detail page."""
    before = previous_entry(course_index)
    return None if before is not None and before["status"] == BLOCKED else previous_url


def _render_closed_notice(
    request: HttpRequest,
    *,
    course: Course,
    entry: dict,
    current_item: Topic | Form,
    collection_item: ContentCollectionItem,
    course_progress: CourseProgress | None,
    index: int,
    next_url: str | None,
    previous_url: str | None,
    player_context: dict,
) -> HttpResponse:
    """Render the notice an item shows once it has closed, in place of its content.

    Writes nothing: opening a closed item is not a visit, so it moves neither the resume
    point nor the course's start time. A form with an open attempt also carries the URL
    that submits the attempt as it stands, since continuing it is refused. A form with a
    completed attempt carries its results URL, since a learner is always entitled to the
    score they earned."""
    submit_and_exit_url = None
    results_url = None
    if isinstance(current_item, Form) and course_progress is not None:
        sittings = sittings_at_placement(course_progress, collection_item)
        if sittings.has_open:
            submit_and_exit_url = reverse(
                "learner_interface:form_submit_and_exit",
                kwargs={"course_slug": course.slug, "index": index},
            )
        if sittings.has_completed:
            results_url = reverse(
                "learner_interface:course_form_complete",
                kwargs={"course_slug": course.slug, "index": index},
            )
    return render(
        request,
        "learner_interface/course_item_closed.html",
        {
            "course": course,
            "entry": entry,
            "submit_and_exit_url": submit_and_exit_url,
            "results_url": results_url,
            "next_url": next_url,
            "previous_url": previous_url,
            **player_context,
        },
    )


@login_required
def view_course_item(request, course_slug, index):
    course = get_object_or_404(Course, slug=course_slug)
    # Hidden-course 404 plus the content-access gate. Closes the hole where an
    # unregistered learner could view a free course's content by guessing the URL
    # (the TOC hides the links as BLOCKED, but the URL was previously unguarded).
    decision = _course_access_decision(request.user, course)

    viewable_collection_items = course.viewable_collection_items()
    if index < 1 or index > len(viewable_collection_items):
        raise Http404("No course item at this index.")
    current_collection_item = viewable_collection_items[index - 1]
    if isinstance(current_collection_item.child, Form):
        expired = _expired_sitting_redirect(
            cast("User", request.user), course, current_collection_item, index
        )
        if expired is not None:
            return expired
    paused = decision.paused_at is not None
    # Only an ended or paused learner's gate reads the record; everyone else is
    # decided by the decision alone, so nothing is fetched for them.
    gated_record = (
        course_progress_for(cast("User", request.user), course)
        if decision.access_ended_at is not None or paused
        else None
    )
    no_access = _course_access_redirect(
        decision,
        course,
        route=PlayerRoute.ITEM,
        collection_item=current_collection_item,
        course_progress=gated_record,
    )
    if no_access is not None:
        return no_access
    current_item = current_collection_item.child
    viewable_items = [item.child for item in viewable_collection_items]

    # The record every write below lands in, minted from the registration if it
    # is missing. This is the self-healing path: a registration made before
    # course progress records existed gets one the first time the learner opens
    # the course, which is why no backfill is needed. A paused learner's record
    # exists already and nothing is written to it.
    course_progress = (
        gated_record if paused else _ensure_player_course_progress(request.user, course)
    )

    # Sequential-unlock gate. Built here rather than inside _player_chrome_context
    # so the decision is made before anything is written, then handed on to the
    # chrome so the index is built once.
    player_index = _player_course_index(
        request.user,
        course,
        index,
        course_progress,
        outline_mode=_outline_mode(decision),
    )
    course_index = player_index.rows
    blocked = _blocked_item_redirect(
        request.user, course, index, course_index=course_index
    )
    if blocked is not None:
        return blocked

    total = len(viewable_items)
    is_last_item = index >= total
    next_url = (
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course_slug, "index": index + 1},
        )
        if index < total and not paused
        else None
    )
    previous_url = (
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course_slug, "index": index - 1},
        )
        if index > 1 and not paused
        else None
    )

    entry = current_entry(course_index)
    closed = entry is not None and entry["status"] == CLOSED

    # Finalise a stale open attempt at a submit-on-exit form (a no-op for
    # save-on-exit forms) only once the gates above have let the learner in and
    # the item is open, then rebuild the outline so it shows the finalised state.
    if (
        isinstance(current_item, Form)
        and course_progress is not None
        and not paused
        and not closed
        and finalise_stale_incomplete(
            course_progress,
            current_collection_item,
            kept_if_untouched_since=_latest_pause_start(course_progress),
        )
        is not None
    ):
        player_index = _player_course_index(
            request.user,
            course,
            index,
            course_progress,
            outline_mode=_outline_mode(decision),
        )
        course_index = player_index.rows

    # Player chrome context shared by topic and form item pages: the outline
    # with the current item marked, the containing part (for breadcrumb / title),
    # the CourseProgress (for the header progress bar / %), and the 1-based index.
    # Reuse the viewable_items already resolved above so the chrome helper does
    # not re-traverse the course a second time. It only reads, so a closed item
    # can render it before anything is written.
    player_context = _player_chrome_context(
        request,
        course,
        current_item,
        index,
        viewable_items=viewable_items,
        course_index=player_index,
        course_progress=course_progress,
        outline_mode=_outline_mode(decision),
        reference_linked=decision.can_access_content,
        decision=decision,
    )

    if entry is not None and closed:
        return _render_closed_notice(
            request,
            entry=entry,
            next_url=_unlocked_next_url(next_url, course_index),
            previous_url=_unlocked_previous_url(previous_url, course_index),
            player_context=player_context,
            course=course,
            current_item=current_item,
            collection_item=current_collection_item,
            course_progress=course_progress,
            index=index,
        )

    # Record this collection item as the resume target. This is the single
    # write point for both topics and forms, so resume no longer depends on
    # per-item progress timestamps. The sequential-unlock
    # branch returns above, so a locked item is never recorded.
    #
    # last_accessed_time is written here rather than by auto_now, so a
    # background percentage recalculation never looks like a visit. started_at
    # is stamped once, on first content access, and never re-stamped.
    if course_progress is not None and not paused:
        now = timezone.now()
        course_progress.last_accessed_item = current_collection_item
        course_progress.last_accessed_time = now
        if course_progress.started_at is None:
            course_progress.started_at = now
            record_course_started(
                request,
                course,
                via_cohort=course_progress.cohort_registration_id is not None,
            )
        course_progress.save(
            update_fields=["last_accessed_item", "last_accessed_time", "started_at"]
        )

    if isinstance(current_item, Topic):
        return view_topic(
            request,
            topic=current_item,
            course=course,
            next_url=next_url,
            previous_url=previous_url,
            is_last_item=is_last_item,
            player_context=player_context,
            collection_item=current_collection_item,
            course_progress=course_progress,
            paused=paused,
        )

    if isinstance(current_item, Form):
        return view_form(
            request,
            form=current_item,
            course=course,
            index=index,
            is_last_item=is_last_item,
            next_url=next_url,
            previous_url=previous_url,
            player_context=player_context,
            collection_item=current_collection_item,
            course_progress=course_progress,
            paused=paused,
        )

    raise Http404("Unsupported course item type.")


def _ensure_player_course_progress(
    user: RequestUser, course: Course
) -> CourseProgress | None:
    """The record the player's writes land in, minted from the registration.

    None when nothing grants this learner the course. Core FLS cannot reach
    that state -- every ``can_access_content`` branch in the access backends is
    gated on a registration -- but a downstream COURSE_ACCESS_BACKEND can, and
    the player must then degrade to read-only rather than mint a record with no
    registration behind it.
    """
    if not user.is_authenticated:
        return None
    resolved = learner_for_course(user, course)
    if resolved is None:
        return None
    return ensure_course_progress_record(
        resolved.learner, course, resolved.registration
    )


def _outline_header_context(
    course_progress: CourseProgress | None,
    course_index: PlayerCourseIndex,
    outline_mode: OutlineMode,
) -> dict[str, object]:
    """The outline panel header's organisation chip and next deadline."""
    course_complete = (
        course_progress is not None and course_progress.completed_time is not None
    )
    if outline_mode is not OutlineMode.FULL or course_complete:
        # Neither carries a deadline on the dashboard either.
        next_deadline = None
    else:
        next_deadline = next_deadline_card(
            course_index.rows,
            course_index.course_deadlines,
            course_index.deadline_policy,
            course_index.now,
        )
    return {
        # Read off the record rather than resolving the registration a second
        # time: the record's learner already names the organisation this pass
        # is being studied through, which is what the header is reporting.
        "course_organisation": (
            course_progress.learner.organisation
            if course_progress is not None
            else None
        ),
        "next_deadline_card": next_deadline,
    }


def _player_chrome_context(
    request: HttpRequest,
    course: Course,
    current_item: Topic | Form,
    index: int,
    viewable_items: list | None = None,
    course_index: PlayerCourseIndex | None = None,
    course_progress: CourseProgress | None | Unresolved = UNRESOLVED,
    outline_mode: OutlineMode = OutlineMode.FULL,
    *,
    reference_linked: bool,
    decision: CourseAccessDecision | None = None,
) -> dict:
    """Build the shared player-chrome context (TOC, breadcrumb, header, title).

    ``viewable_items``, ``course_index`` and ``course_progress`` may be passed
    in by a caller that has already resolved them (``view_course_item`` builds
    all three to run its gates and its write) to avoid doing the work twice;
    callers that have not let them default. Passing ``course_progress=None``
    means "there is no record", and is not the same as leaving it out.

    ``outline_mode`` shapes the outline it builds for an ended or paused learner and
    withholds the next-deadline card from both. When ``course_index`` is passed in, it is
    built by the caller with the same mode.

    ``reference_linked`` is whether the learner can read the reference pages, so the
    sidebar's reference topics link only when following them would not bounce.

    ``decision`` gates the outline's Revision entry; without one the entry is
    left out.
    """
    user = request.user
    if viewable_items is None:
        viewable_items = course.viewable_items()
    if isinstance(course_progress, Unresolved):
        course_progress = (
            course_progress_for(user, course) if user.is_authenticated else None
        )
    current_part = get_item_part(course, current_item)

    # The breadcrumb part crumb links to the part's first viewable item. Resolve
    # its 1-based index in the already-computed viewable_items, in memory.
    current_part_index: int | None = None
    if current_part is not None:
        part_children = [
            item.child
            for item in live_collection_items(current_part)
            if item.child is not None
        ]
        if part_children:
            first_child = part_children[0]
            for n, item in enumerate(viewable_items, start=1):
                if type(item) is type(first_child) and item.pk == first_child.pk:
                    current_part_index = n
                    break

    if course_index is None:
        # can_access_content=True: every caller runs the content-access gate
        # before reaching here, so the learner is confirmed to have content
        # access at this point.
        course_index = _player_course_index(
            user,
            course,
            index,
            course_progress,
            outline_mode=outline_mode,
        )

    rows = course_index.rows

    return {
        "course_index": rows,
        "current_entry": current_entry(rows),
        **_outline_header_context(course_progress, course_index, outline_mode),
        "current_part": current_part,
        "current_part_index": current_part_index,
        "course_progress": course_progress,
        # Without a record there is nowhere to write a completion, so the
        # templates hide the controls that would offer one.
        "can_record_progress": course_progress is not None,
        "item_title": current_item.title,
        "index": index,
        "paused": outline_mode is OutlineMode.PAUSED,
        "reference_linked": reference_linked,
        "revision_due_text": (
            _revision_due_text(
                cast("User", user), course_progress, decision, timezone.now()
            )
            if decision is not None
            else None
        ),
        **_time_zone_context(request),
    }


def view_topic(
    request,
    topic,
    course,
    next_url,
    previous_url,
    is_last_item=False,
    player_context: dict | None = None,
    *,
    collection_item: ContentCollectionItem,
    course_progress: CourseProgress | None,
    paused: bool = False,
):
    topic_progress = None
    if course_progress is not None and paused:
        # Reading a finished topic during a pause writes nothing, not even a touch.
        topic_progress = TopicProgress.objects.filter(
            course_progress=course_progress, collection_item=collection_item
        ).first()
    elif course_progress is not None:
        topic_progress, created = TopicProgress.objects.get_or_create(
            course_progress=course_progress,
            collection_item=collection_item,
            defaults={"site_id": course_progress.site_id, "topic": topic},
        )
        if not created:
            topic_progress.save()

    if request.method == "POST" and "mark_complete" in request.POST:
        if paused:
            return redirect("learner_interface:course_detail", course_slug=course.slug)
        if topic_progress is None:
            raise Http404("No course progress record to record this completion in.")
        # The first completion is the one that counts; a re-post keeps its time.
        if topic_progress.complete_time is None:
            topic_progress.complete_time = timezone.now()
            topic_progress.save()

        if next_url:
            return redirect(next_url)
        else:
            # If no next_url (last item), redirect to course finish page
            return redirect("learner_interface:course_finish", course_slug=course.slug)

    player_context = player_context or {}
    is_course_complete = bool(course_progress and course_progress.completed_time)

    context = {
        "course": course,
        "topic": topic,
        "is_complete": topic_progress is not None
        and topic_progress.complete_time is not None,
        "next_url": next_url,
        "previous_url": previous_url,
        "is_last_item": is_last_item,
        "is_course_complete": is_course_complete,
        **player_context,
    }
    return render(request, "learner_interface/course_topic.html", context)


def view_form(
    request,
    form,
    course,
    index,
    is_last_item=False,
    next_url=None,
    previous_url=None,
    player_context: dict | None = None,
    *,
    collection_item: ContentCollectionItem,
    course_progress: CourseProgress | None,
    paused: bool = False,
):
    """Show the front page of the form"""

    incomplete_form_progress = None
    completed_form_progress = FormProgress.objects.none()
    if course_progress is not None:
        # The learner's open attempt at this placement, if they have one. Not
        # created here -- the start screen reads, form_start writes.
        incomplete_form_progress = get_latest_incomplete(
            course_progress, collection_item
        )

        # The most-recent completed attempts at this placement. The start screen
        # shows a compact summary of the 5 latest; the button logic only needs
        # the latest via .first() (the queryset is ordered newest-first).
        # select_related("form") so the button logic's pass/fail verdict reads
        # form.quiz_pass_percentage without a second query.
        completed_form_progress = completed_attempts(course_progress, collection_item)[
            :5
        ]

    page_number = None
    if incomplete_form_progress:
        page_number = resume_page_number(
            incomplete_form_progress, current_path(incomplete_form_progress)
        )

    # Determine which buttons to show
    buttons = (
        []
        if paused
        else form_start_page_buttons(
            form=form,
            incomplete_form_progress=incomplete_form_progress,
            completed_form_progress=completed_form_progress,
            is_last_item=is_last_item,
        )
    )

    context = {
        "course": course,
        "form": form,
        "incomplete_form_progress": incomplete_form_progress,
        "completed_form_progress": completed_form_progress,
        "index": index,
        "page_number": page_number,
        "buttons": buttons,
        "next_url": next_url,
        "previous_url": previous_url,
        **(player_context or {}),
        "question_count": count_sitting_questions(form),
        "page_count": count_sitting_pages(form),
    }

    return render(request, "learner_interface/course_form.html", context)


@dataclass(frozen=True)
class FormStartGate:
    """What the checks before starting a sitting found: a redirect, or what to start in."""

    redirect: HttpResponseRedirect | None
    collection_item: ContentCollectionItem
    course_progress: CourseProgress | None
    decision: CourseAccessDecision
    course_index: PlayerCourseIndex | None


def _form_start_gate(request: HttpRequest, course: Course, index: int) -> FormStartGate:
    """The access, blocked and closed checks every route that starts a sitting runs first.
    It writes nothing except the player's course progress record."""
    decision = _course_access_decision(request.user, course)
    collection_item = get_form_collection_item_for_index(course, index)

    def refused(response: HttpResponseRedirect) -> FormStartGate:
        return FormStartGate(response, collection_item, None, decision, None)

    no_access = _course_access_redirect(
        decision, course, route=PlayerRoute.ITEM, collection_item=collection_item
    )
    if no_access is not None:
        return refused(no_access)
    course_progress = _ensure_player_course_progress(request.user, course)

    # Minting the attempt is what would flip a locked quiz to IN_PROGRESS, so the
    # gate has to come before it — and before finalise_stale_incomplete, which
    # writes too. Minting the course progress record above changes no status.
    # A closed form is refused here as well: starting it would open an attempt
    # the learner can no longer fill in.
    course_index = _player_course_index(request.user, course, index, course_progress)
    blocked = _blocked_item_redirect(
        request.user,
        course,
        index,
        course_index=course_index.rows,
        refuse_closed=True,
    )
    if blocked is not None:
        return refused(blocked)

    if course_progress is None:
        # Nothing grants this learner the course, so there is no record to
        # attempt the form in. Send them back to the read-only start screen
        # rather than mint an attempt with no record behind it.
        return refused(
            redirect(
                "learner_interface:view_course_item",
                course_slug=course.slug,
                index=index,
            )
        )
    return FormStartGate(None, collection_item, course_progress, decision, course_index)


def _expired_form_sitting_redirect(
    request: HttpRequest, course: Course, index: int
) -> HttpResponseRedirect | None:
    """`_expired_sitting_redirect` for the routes whose gate resolves the placement
    itself: the hidden-course and index 404s still come first."""
    raise_404_if_unavailable(request.user, course)
    collection_item = get_form_collection_item_for_index(course, index)
    return _expired_sitting_redirect(
        cast("User", request.user), course, collection_item, index
    )


def _declaration_redirect(course_slug: str, index: int) -> HttpResponseRedirect:
    return redirect(
        "learner_interface:form_declaration", course_slug=course_slug, index=index
    )


def _form_page_redirect(
    course_slug: str, index: int, form_progress: FormProgress
) -> HttpResponseRedirect:
    """Send the learner to the page of this sitting they should be on."""
    page_number = resume_page_number(form_progress, current_path(form_progress))
    return redirect(
        "learner_interface:form_fill_page",
        course_slug=course_slug,
        index=index,
        page_number=page_number,
    )


@login_required
def form_start(request: HttpRequest, course_slug: str, index: int) -> HttpResponse:
    """Start or resume a form for the current user."""

    course = get_object_or_404(Course, slug=course_slug)
    expired = _expired_form_sitting_redirect(request, course, index)
    if expired is not None:
        return expired
    gate = _form_start_gate(request, course, index)
    if gate.redirect is not None:
        return gate.redirect
    collection_item = gate.collection_item
    # The gate redirects when there is no record, so none is left here.
    course_progress = cast("CourseProgress", gate.course_progress)
    form = cast("Form", collection_item.child)

    if form_requires_declaration(form, request.user):
        # A signed sitting the learner left is finalised (submit-on-exit forms
        # only) and they sign again for the next one. Any other signed sitting is
        # resumed as it stands: start_attempt here could mint one nobody signed.
        open_sitting = close_left_signed_sitting(
            course_progress,
            collection_item,
            kept_if_untouched_since=_latest_pause_start(course_progress),
        )
        if open_sitting is None or sitting_needs_declaration(open_sitting):
            return _declaration_redirect(course_slug, index)
        form_progress = open_sitting
    else:
        # Finalise a stale incomplete attempt (submit-on-exit forms only), then resume
        # or create the sitting, serialised per record so concurrent starts share one.
        form_progress = start_attempt(
            course_progress,
            collection_item,
            kept_if_untouched_since=_latest_pause_start(course_progress),
        )
    ensure_served_paper(form_progress)
    return _form_page_redirect(course_slug, index, form_progress)


@login_required
def form_declaration(
    request: HttpRequest, course_slug: str, index: int
) -> HttpResponse:
    """The declaration a learner signs before each attempt at a declaration quiz."""
    course = get_object_or_404(Course, slug=course_slug)
    expired = _expired_form_sitting_redirect(request, course, index)
    if expired is not None:
        return expired
    gate = _form_start_gate(request, course, index)
    if gate.redirect is not None:
        return gate.redirect
    collection_item = gate.collection_item
    # The gate redirects when there is no record, so none is left here.
    course_progress = cast("CourseProgress", gate.course_progress)
    form = cast("Form", collection_item.child)
    open_sitting = get_latest_incomplete(course_progress, collection_item)
    if not form_requires_declaration(form, request.user) or (
        # Signed already: form_start decides whether it resumes or is finalised,
        # so a second signature never ends the attempt in progress.
        open_sitting is not None and not sitting_needs_declaration(open_sitting)
    ):
        return redirect(
            "learner_interface:form_start", course_slug=course_slug, index=index
        )

    text = form.effective_declaration_text()
    declaration_form = FormDeclarationForm(
        request.POST if request.method == "POST" else None, declaration_text=text
    )
    status = 200
    text_changed = False
    if request.method == "POST" and not declaration_form.is_valid():
        status = 422
        if declaration_form.declaration_changed():
            # The learner signed text they never saw: show the current text
            # with both fields cleared so they read it again.
            text_changed = True
            declaration_form = FormDeclarationForm(declaration_text=text)
    elif request.method == "POST":
        # A PermissionDenied from the client IP lookup propagates as a 403.
        ip = get_client_ip(request)
        form_progress = start_attempt(
            course_progress,
            collection_item,
            kept_if_untouched_since=_latest_pause_start(course_progress),
            declaration=FormDeclaration(
                declaration_text=text,
                typed_name=declaration_form.cleaned_data["typed_name"],
                ip_address=ip or None,
            ),
        )
        ensure_served_paper(form_progress)
        return _form_page_redirect(course_slug, index, form_progress)

    start_url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course_slug, "index": index},
    )
    context = {
        **_player_chrome_context(
            request,
            course,
            form,
            index,
            course_index=gate.course_index,
            course_progress=course_progress,
            reference_linked=gate.decision.can_access_content,
        ),
        "course": course,
        "form": form,
        "index": index,
        "declaration_text": text,
        "declaration_form": declaration_form,
        "text_changed": text_changed,
        "previous_url": start_url,
    }
    return render(
        request, "learner_interface/form_declaration.html", context, status=status
    )


def _form_page_url(course_slug: str, index: int, page_number: int) -> str:
    return reverse(
        "learner_interface:form_fill_page",
        kwargs={
            "course_slug": course_slug,
            "index": index,
            "page_number": page_number,
        },
    )


def _format_countdown(seconds: int) -> str:
    """Whole seconds as the countdown shows them: m:ss, or h:mm:ss from an hour."""
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _render_form_fill_page(
    request: HttpRequest,
    course: Course,
    form: Form,
    index: int,
    current: CurrentPage,
    course_progress: CourseProgress | None,
    form_progress: FormProgress | None,
    submission: PageSubmission,
    *,
    reference_linked: bool,
    decision: CourseAccessDecision,
    now: datetime,
    course_index: PlayerCourseIndex | None = None,
) -> HttpResponse:
    """Render one runner page, carrying whatever a submission was rejected for.

    Shared with `form_submit_and_exit`, which has to put the learner back on the
    page they were standing on when an answer is rejected, rather than finalise
    the attempt without it. Both callers have already resolved the page, so both
    hand it over rather than paying for it twice — and both record it as reached
    here, so leaving by the dialog moves the resume point just as paging does.
    ``course_index`` is the outline a caller already built for its gate, so the
    chrome does not build it again; a caller with no gate leaves it out.
    ``now`` is the instant the caller's expiry check used, so the countdown
    starts from the same clock that decided the sitting was still open.
    """

    def url_for_page(number: int) -> str:
        return _form_page_url(course.slug, index, number)

    # No incomplete attempt to resume (e.g. the form is already completed, or it
    # was finalised by a submit-on-exit safety net). Send the learner back to the
    # form start screen rather than dereferencing None and 500ing.
    if form_progress is None:
        return redirect(
            "learner_interface:view_course_item",
            course_slug=course.slug,
            index=index,
        )

    form_progress.record_page_reached(current.number, current.path)

    expiry = form_progress.expires_at()
    remaining_seconds = (
        None if expiry is None else max(0, int((expiry - now).total_seconds()))
    )

    context = page_context(form, current, form_progress, submission, url_for_page) | {
        "course": course,
        # Player chrome (outline panel + breadcrumb) so the fill page keeps the
        # same orientation as the rest of the player.
        **_player_chrome_context(
            request,
            course,
            form,
            index,
            course_index=course_index,
            course_progress=course_progress,
            reference_linked=reference_linked,
            decision=decision,
        ),
        **answered_counts(form_progress, current.questions, current.path),
        "remaining_seconds": remaining_seconds,
        "remaining_text": (
            None if remaining_seconds is None else _format_countdown(remaining_seconds)
        ),
        # URLs the exit dialog acts on.
        "submit_and_exit_url": reverse(
            "learner_interface:form_submit_and_exit",
            kwargs={"course_slug": course.slug, "index": index},
        ),
        "save_and_exit_url": reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": index},
        ),
    }
    return render_form_page(
        request, "learner_interface/course_form_page.html", context, submission
    )


@login_required
def form_fill_page(
    request: HttpRequest, course_slug: str, index: int, page_number: int
) -> HttpResponse:
    course = get_object_or_404(Course, slug=course_slug)
    decision = _course_access_decision(request.user, course)
    collection_item = get_form_collection_item_for_index(course, index)
    found = _open_sitting_at(cast("User", request.user), course, collection_item)
    now = timezone.now()
    # A page post that lands just after the clock ran out is still the learner's
    # work: it is saved, then the sitting completes. It runs ahead of the access
    # gates because the window is the server's clock, not the learner's access, and
    # it writes only this learner's own open sitting.
    if (
        request.method == "POST"
        and found is not None
        and found.sitting.in_grace(now)
        and _save_page_and_complete(
            found.course_progress,
            found.sitting,
            page_number,
            request.POST,
            now,
            time_up=False,
        )
    ):
        return redirect(
            "learner_interface:course_form_complete",
            course_slug=course_slug,
            index=index,
        )
    expired = _expired_sitting_redirect(
        cast("User", request.user), course, collection_item, index, found
    )
    if expired is not None:
        return expired
    no_access = _course_access_redirect(
        decision, course, route=PlayerRoute.ITEM, collection_item=collection_item
    )
    if no_access is not None:
        return no_access
    form = cast("Form", collection_item.child)
    course_progress = _ensure_player_course_progress(request.user, course)

    # Gated ahead of the POST branch below, which saves answers and can complete
    # the attempt: a refused page must write nothing at all. Closed forms are
    # refused too, so an attempt cannot be continued past the close instant.
    player_index = _player_course_index(request.user, course, index, course_progress)
    blocked = _blocked_item_redirect(
        request.user,
        course,
        index,
        course_index=player_index.rows,
        refuse_closed=True,
    )
    if blocked is not None:
        return blocked

    # Get the latest incomplete form progress instance
    form_progress = (
        get_latest_incomplete(course_progress, collection_item)
        if course_progress is not None
        else None
    )
    # No incomplete attempt to render or save into (e.g. it was finalised by a
    # submit-on-exit safety net, or the page was reached without starting).
    # Send the learner back to the form start screen rather than 500.
    if form_progress is None:
        return redirect(
            "learner_interface:view_course_item",
            course_slug=course_slug,
            index=index,
        )

    # An unsigned sitting is served nothing and saved nothing until it is signed.
    if sitting_needs_declaration(form_progress):
        return _declaration_redirect(course_slug, index)

    ensure_served_paper(form_progress)
    path = current_path(form_progress)
    landing = off_path_landing(path, page_number)
    if landing is not None:
        return redirect(_form_page_url(course_slug, index, landing))
    current = resolve_page(path, page_number)

    submission = PageSubmission()
    if request.method == "POST":
        submission = submit_page(current, request.POST, form_progress)
        # The answers just saved can change which pages come next, and so what
        # a rejected page's count and page-jump nav show.
        path = current_path(form_progress)
        if submission.accepted:
            next_number = path.next_page_number(page_number)
            if next_number is not None:
                return redirect(_form_page_url(course_slug, index, next_number))

            unanswered = unanswered_required_in_form(form_progress, path)
            onward = first_page_number_with_unanswered_required(path, unanswered)
            if onward is not None:
                # A page the answers reopened behind the learner holds a required
                # question the page-jump nav would otherwise let them skip.
                onward_questions = path.questions_of(path.all_pages[onward - 1])
                messages.error(
                    request,
                    unanswered_required_message(
                        [q for q in unanswered if q in onward_questions], path
                    ),
                )
                return redirect(_form_page_url(course_slug, index, onward))

            form_progress.complete()

            return redirect(
                "learner_interface:course_form_complete",
                course_slug=course_slug,
                index=index,
            )
        # A page's gate is on an earlier page, so the posted page is still on it.
        current = resolve_page(path, page_number)

    return _render_form_fill_page(
        request,
        course,
        form,
        index,
        current,
        course_progress,
        form_progress,
        submission,
        reference_linked=decision.can_access_content,
        decision=decision,
        now=now,
        course_index=player_index,
    )


@login_required
def course_form_complete(request, course_slug, index):
    course = get_object_or_404(Course, slug=course_slug)
    decision = _course_access_decision(request.user, course)
    # No sequential-unlock gate here, deliberately: this page only reads back a
    # sitting the learner already made, and a learner is always entitled to the
    # score they earned — including after the quiz itself has been withheld.
    # Fetch the collection items once and reuse them (they are not cached); the
    # view also needs the list length below for is_last_item.
    viewable_collection_items = course.viewable_collection_items()
    collection_item = get_form_collection_item_for_index(
        course, index, viewable_collection_items=viewable_collection_items
    )
    form = cast("Form", collection_item.child)

    # Completing it here lets the access gate below find the finished sitting.
    _complete_expired_sitting(
        _open_sitting_at(cast("User", request.user), course, collection_item),
        timezone.now(),
    )
    course_progress = course_progress_for(request.user, course)
    no_access = _course_access_redirect(
        decision,
        course,
        route=PlayerRoute.FORM_RESULTS,
        collection_item=collection_item,
        course_progress=course_progress,
    )
    if no_access is not None:
        return no_access
    access_ended = decision.access_ended_at is not None
    keeps_outline = _shows_ended_outline(decision)
    paused = decision.paused_at is not None

    # Get the most recent completed attempt at this placement
    form_progress = (
        completed_attempts(course_progress, collection_item).first()
        if course_progress is not None
        else None
    )
    if form_progress is None:
        return redirect(
            "learner_interface:view_course_item",
            course_slug=course_slug,
            index=index,
        )

    # Get incorrect answers if this is a quiz with show_incorrect enabled
    # Only a quiz sitting with a served paper is marked from a path; building
    # one for any other sitting would load the form tree for nothing.
    path = (
        sitting_path(form_progress)
        if form.strategy == FormStrategy.QUIZ and form_progress.served_paper is not None
        else None
    )
    incorrect_answers = form_progress.get_incorrect_quiz_answers(path)

    # Only set for QUIZ forms; non-quiz forms do not have a numeric percentage.
    percentage = None
    if form.strategy == FormStrategy.QUIZ:
        with contextlib.suppress(ValueError):
            percentage = form_progress.quiz_percentage()

    score_outdated = stored_score_outdated(form_progress, path)

    # Three-state: "passed", "failed", or None for a quiz with no pass mark —
    # there is no bar to clear, so the results page must claim neither outcome.
    # The PDF report and the educator panel use the same guard.
    quiz_verdict = None
    if percentage is not None and form.quiz_pass_percentage is not None:
        quiz_verdict = "passed" if form_progress.passed() else "failed"

    # Player chrome (outline panel + breadcrumb). Under "nothing" this is the one
    # player page an ended learner still reaches, and it carries no outline, so
    # the chrome is handed an empty index to draw.
    chrome = _player_chrome_context(
        request,
        course,
        form,
        index,
        course_index=(
            PlayerCourseIndex.empty() if access_ended and not keeps_outline else None
        ),
        course_progress=course_progress,
        outline_mode=_outline_mode(decision),
        reference_linked=decision.can_access_content,
        decision=decision,
    )
    course_index = chrome["course_index"]
    # A closed form refuses a new sitting, so its results offer no retry. Read off
    # the outline this page draws, as the player's other gates do, so there is one
    # definition of closed. An ended learner's empty index reads as open, and the
    # access_ended message and the hidden footer win for them anyway.
    item_closed = current_entry_status(course_index) == CLOSED

    # Calculate next URL for continue button
    total_viewable_items = len(viewable_collection_items)
    is_last_item = index >= total_viewable_items
    next_url: str | None
    if paused:
        next_url = None
    elif is_last_item:
        # Last item - go to course finish page
        next_url = reverse(
            "learner_interface:course_finish", kwargs={"course_slug": course_slug}
        )
    else:
        # Not last item - go to next item, unless this closed form keeps it locked.
        next_url = _unlocked_next_url(
            reverse(
                "learner_interface:view_course_item",
                kwargs={"course_slug": course_slug, "index": index + 1},
            ),
            course_index,
        )

    # Calculate retry URL
    retry_url = reverse(
        "learner_interface:form_start",
        kwargs={"course_slug": course_slug, "index": index},
    )

    # Previous means the item before this one in the course, the same as it does
    # in every other player footer. Stepping back into this form is the retry
    # button's job, not this one's. An ended learner gets no footer at all.
    previous_url = (
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course_slug, "index": index - 1},
        )
        if index > 1 and not access_ended and not paused
        else None
    )
    if item_closed:
        previous_url = _unlocked_previous_url(previous_url, course_index)

    context = {
        "course": course,
        "form": form,
        "form_progress": form_progress,
        "show_scores": True,
        "scores": form_progress.scores,
        "incorrect_answers": incorrect_answers,
        "stored_score_outdated": score_outdated,
        "quiz_verdict": quiz_verdict,
        "time_expired": form_progress.completion_reason
        == CompletionReason.TIME_EXPIRED,
        "next_url": next_url,
        "previous_url": previous_url,
        "retry_url": retry_url,
        "access_ended": access_ended,
        "paused": paused,
        "item_closed": item_closed,
        "hide_outline_panel": access_ended and not keeps_outline,
        **chrome,
    }

    # Only include percentage in context for QUIZ forms (avoids None littering the context
    # for non-quiz forms; template branches on form.strategy == "QUIZ" already).
    if percentage is not None:
        context["percentage"] = percentage

    return render(request, "learner_interface/course_form_complete.html", context)


def _course_index_without_current_row(
    request: HttpRequest, course: Course, course_progress: CourseProgress | None
) -> PlayerCourseIndex:
    """The outline for a page that is not one of the course's items.

    The caller has confirmed content access, so no row is rendered locked for
    want of it.
    """
    now = timezone.now()
    course_deadlines = _deadlines_or_none(course_progress, now)
    deadline_policy = _deadline_policy_or_none(course_progress)
    rows = get_course_index(
        user=request.user,
        course=course,
        can_access_content=True,
        course_progress=course_progress,
        course_deadlines=course_deadlines,
        deadline_policy=deadline_policy,
        now=now,
    )
    return PlayerCourseIndex(rows, course_deadlines, deadline_policy, now)


def _reference_access_redirect(
    request: HttpRequest, course: Course
) -> HttpResponseRedirect | None:
    """Where to send a learner who may not read this course's reference pages, or None.

    Reference pages follow the same gate as a closed item: whoever cannot see
    the course's content goes to its detail page. There are no read-only
    exceptions, because reading reference material records nothing.
    """
    decision = _course_access_decision(request.user, course)
    if decision.can_access_content:
        return None
    return redirect("learner_interface:course_detail", course_slug=course.slug)


def _reference_sidebar_context(
    request: HttpRequest, course: Course
) -> dict[str, object]:
    """The outline panel with no current row, read without writing any progress.

    course_progress_for only reads, so a learner who has never opened the
    course still has no course progress record after reading its reference material.
    """
    course_progress = course_progress_for(cast("User", request.user), course)
    course_index = _course_index_without_current_row(request, course, course_progress)
    return {
        "course_progress": course_progress,
        "course_index": course_index.rows,
        **_outline_header_context(course_progress, course_index, OutlineMode.FULL),
        "on_reference_page": True,
        "reference_linked": True,
        # The reference gate has already passed, so only the bank decides.
        "revision_due_text": _revision_due_badge(
            cast("User", request.user), course_progress, timezone.now()
        ),
        **_time_zone_context(request),
    }


@login_required
def course_reference(request: HttpRequest, course_slug: str) -> HttpResponse:
    course = get_object_or_404(Course, slug=course_slug)
    no_access = _reference_access_redirect(request, course)
    if no_access is not None:
        return no_access
    return render(
        request,
        "learner_interface/course_reference.html",
        {
            "course": course,
            "reference_outline": reference_outline(course, linked=True),
            **_reference_sidebar_context(request, course),
        },
    )


@login_required
def course_reference_topic(
    request: HttpRequest, course_slug: str, part_slug: str, topic_slug: str
) -> HttpResponse:
    course = get_object_or_404(Course, slug=course_slug)
    no_access = _reference_access_redirect(request, course)
    if no_access is not None:
        return no_access
    # Every part is read, not just this one: the sidebar outline lists them all.
    parts = course_reference_topics(course)
    part = next((part for part in parts if part.course_part.slug == part_slug), None)
    if part is None:
        raise Http404("No such reference part in this course.")
    position = next(
        (n for n, topic in enumerate(part.topics) if topic.slug == topic_slug), None
    )
    if position is None:
        raise Http404("No such topic in this reference part.")
    topic = part.topics[position]
    # Previous and Next stay inside the part: reference parts are read
    # separately, not as one sequence.
    previous_topic = part.topics[position - 1] if position > 0 else None
    next_topic = part.topics[position + 1] if position + 1 < len(part.topics) else None
    return render(
        request,
        "learner_interface/course_reference_topic.html",
        {
            "course": course,
            "topic": topic,
            "current_part": part.course_part,
            "reference_outline": reference_outline(
                course,
                linked=True,
                current_part=part.course_part,
                current_topic=topic,
                parts=parts,
            ),
            "previous_topic": previous_topic,
            "next_topic": next_topic,
            "previous_url": (
                reference_topic_url(course, part.course_part, previous_topic)
                if previous_topic
                else None
            ),
            "next_url": (
                reference_topic_url(course, part.course_part, next_topic)
                if next_topic
                else None
            ),
            **_reference_sidebar_context(request, course),
        },
    )


def _revision_record(
    request: HttpRequest, course_slug: str
) -> tuple[Course, CourseProgress] | HttpResponseRedirect:
    """The gate every revision view passes first: the course and the learner's record, or the redirect."""
    course = get_object_or_404(Course, slug=course_slug)
    no_access = _course_access_redirect(
        _course_access_decision(request.user, course),
        course,
        route=PlayerRoute.REVISION,
    )
    if no_access is not None:
        return no_access
    record = _ensure_player_course_progress(request.user, course)
    if record is None:
        raise Http404("No course progress record for this learner and course.")
    return course, record


def _revision_redirect(request: HttpRequest, url: str) -> HttpResponse:
    """Send a revision POST to ``url``: a 204 with HX-Redirect under htmx, a redirect otherwise.

    htmx follows a plain redirect inside its own request and swaps the whole
    page it lands on into ``#revision-card``, so it gets HX-Redirect instead.
    """
    if request.headers.get("HX-Request") == "true":
        response = HttpResponse(status=204)
        response["HX-Redirect"] = url
        return response
    return redirect(url)


def _revision_page_redirect(request: HttpRequest, course: Course) -> HttpResponse:
    return _revision_redirect(
        request,
        reverse(
            "learner_interface:course_revision", kwargs={"course_slug": course.slug}
        ),
    )


def _revision_state(
    request: HttpRequest, course: Course
) -> RevisionSessionState | None:
    """The learner's revision session for this course, or None when there is none or it is unreadable."""
    stored = request.session.get(_revision_session_key(course))
    if stored is None:
        return None
    try:
        return RevisionSessionState.model_validate(stored)
    except PydanticValidationError:
        return None


def _revision_session_key(course: Course) -> str:
    return f"revision_session:{course.id}"


def _store_revision_state(
    request: HttpRequest, course: Course, state: RevisionSessionState
) -> None:
    request.session[_revision_session_key(course)] = state.model_dump(mode="json")


def _current_revision_question(
    record: CourseProgress, state: RevisionSessionState
) -> tuple[FormQuestion | None, RevisionSessionState]:
    """The question the session is on, read through the bank, and the state after skipping.

    A question that has left the bank since the session was built is skipped,
    so a session never serves a question the learner may no longer revise.
    """
    while (question_id := state.current_question_id) is not None:
        question = (
            bank_questions(record)
            .filter(pk=question_id)
            .prefetch_related(
                "options", "formquestiontopic_set", "formquestioncoursepart_set"
            )
            .first()
        )
        if question is not None:
            return question, state
        state = state.advanced()
    return None, state


@dataclass(frozen=True)
class SectionLink:
    title: str
    url: str


def _openable_positions(
    user: RequestUser, course: Course, record: CourseProgress
) -> dict[uuid.UUID, int]:
    """Placement id to its 1-based player position, for every placement this learner can open.

    Read from the outline the player itself gates on, so a section link is
    never offered for a page the player would refuse.
    """
    # Index 0 marks no row as current.
    outline = item_rows(_player_course_index(user, course, 0, record).rows)
    return {
        item.pk: position
        for position, (item, row) in enumerate(
            zip(course.viewable_collection_items(), outline, strict=True), start=1
        )
        if row["status"] not in (BLOCKED, CLOSED)
    }


def _section_links(
    record: CourseProgress,
    question: FormQuestion,
    openable: Mapping[uuid.UUID, int],
) -> list[SectionLink]:
    links = []
    for section in question_sections(record, question):
        placement = section_first_placement(record.course, section)
        if placement is None or placement.pk not in openable:
            continue
        url = reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": record.course.slug, "index": openable[placement.pk]},
        )
        links.append(SectionLink(title=section.title, url=url))
    return links


def _revision_review_of(
    user: User, course: Course, state: RevisionSessionState, question: FormQuestion
) -> RevisionReview | None:
    """The latest review of this question written during this session, if any."""
    review: RevisionReview | None = (
        session_reviews(user, state, course)
        .filter(question=question)
        .order_by("-reviewed_at")
        .first()
    )
    return review


def _render_revision_card(
    request: HttpRequest,
    course: Course,
    record: CourseProgress,
    state: RevisionSessionState,
    *,
    error: str = "",
    status: int = 200,
) -> HttpResponse:
    """The `#revision-card` partial for wherever the session now is.

    A form posted natively, because htmx had not loaded yet, is sent back to the
    revision page, which renders the session's current state in full.
    """
    if request.headers.get("HX-Request") != "true":
        response = _revision_page_redirect(request, course)
        # See Other: the browser follows the native POST with a GET.
        response.status_code = 303
        return response
    template, context = _revision_card_context(request, course, record, state)
    context["error"] = error
    return render(request, template, context, status=status)


def _revision_end_context(
    request: HttpRequest, course: Course, state: RevisionSessionState
) -> dict[str, object]:
    return {
        "course": course,
        "summary": session_summary(cast("User", request.user), state, course),
    }


def _revision_card_context(
    request: HttpRequest,
    course: Course,
    record: CourseProgress,
    state: RevisionSessionState,
) -> tuple[str, dict[str, object]]:
    """The template and context for where the session is: a question, or the done card.

    Reaching the done card ends the session, so the next visit to the
    revision page starts from the dashboard.
    """
    question, state = _current_revision_question(record, state)
    if question is None:
        request.session.pop(_revision_session_key(course), None)
        return "learner_interface/partials/revision_end.html", _revision_end_context(
            request, course, state
        )
    review = _revision_review_of(cast("User", request.user), course, state, question)
    section_links = (
        _section_links(
            record,
            question,
            _openable_positions(request.user, course, record),
        )
        if review is not None
        else []
    )
    options = shuffled_options(question, state.seeds[state.index])
    # Counted over the questions still in the bank, so a question that left it
    # mid-session leaves no gap in "N of M".
    in_bank = set(
        bank_questions(record)
        .filter(pk__in=state.question_ids)
        .values_list("pk", flat=True)
    )
    position = sum(
        1
        for question_id in state.question_ids[: state.index + 1]
        if question_id in in_bank
    )
    return "learner_interface/partials/revision_card.html", {
        "course": course,
        "question": question,
        "section_links": section_links,
        "revision_options": options,
        "correct_options": [option for option in options if option.correct],
        "review": review,
        "position": position,
        "total": len(in_bank),
        "question_positions": {question.id: position},
        "rejected_answers": {},
        "existing_answers": {},
    }


COURSE_DUE_CAP = 40


def _due_count(user: User, record: CourseProgress, now: datetime) -> int:
    """The due questions, counted one past the cap so "40" and "more than 40" can be told apart."""
    return ready_count(user, record, now, limit=COURSE_DUE_CAP + 1)


def _due_number(count: int) -> str:
    return f"{COURSE_DUE_CAP}+" if count > COURSE_DUE_CAP else str(count)


def _revision_due_text(
    user: User,
    record: CourseProgress | None,
    decision: CourseAccessDecision,
    now: datetime,
) -> str | None:
    """The badge on the outline's Revision entry, or None when the outline shows no entry."""
    if record is None or not decision.can_access_content:
        return None
    return _revision_due_badge(user, record, now)


def _revision_due_badge(
    user: User, record: CourseProgress | None, now: datetime
) -> str | None:
    """ "N due" for a learner with a bank, None for one without or with no record."""
    if record is None or not bank_questions(record).exists():
        return None
    return f"{_due_number(_due_count(user, record, now))} due"


def _revision_dashboard_context(
    user: User, course: Course, record: CourseProgress
) -> dict[str, object]:
    has_bank = bank_questions(record).exists()
    due_count = _due_count(user, record, timezone.now()) if has_bank else 0
    return {
        "course": course,
        "has_bank": has_bank,
        "due_count": due_count,
        "due_number": _due_number(due_count),
    }


def _render_revision_page(
    request: HttpRequest,
    course: Course,
    record: CourseProgress,
    card_template: str,
    context: dict[str, object],
) -> HttpResponse:
    """The revision page in the course player: the outline beside one revision card."""
    user = cast("User", request.user)
    # Index 0 marks no row as current: the Revision entry is the current place.
    course_index = _player_course_index(user, course, 0, record)
    return render(
        request,
        "learner_interface/course_revision.html",
        {
            **context,
            "card_template": card_template,
            "course_progress": record,
            "course_index": course_index.rows,
            **_outline_header_context(record, course_index, OutlineMode.FULL),
            # The access gate has already passed, so the reference pages are open.
            "reference_linked": True,
            "item_title": "Revision",
            "revision_is_current": True,
            # The access gate has already passed, so only the bank decides.
            "revision_due_text": _revision_due_badge(user, record, timezone.now()),
            **_time_zone_context(request),
        },
    )


@login_required
def course_revision(request: HttpRequest, course_slug: str) -> HttpResponse:
    """The revision page: the dashboard, or the session's current card or done card."""
    gate = _revision_record(request, course_slug)
    if isinstance(gate, HttpResponseRedirect):
        return gate
    course, record = gate
    state = _revision_state(request, course)
    if state is None:
        return _render_revision_page(
            request,
            course,
            record,
            "learner_interface/partials/revision_dashboard.html",
            _revision_dashboard_context(cast("User", request.user), course, record),
        )
    card_template, context = _revision_card_context(request, course, record, state)
    context["error"] = ""
    return _render_revision_page(request, course, record, card_template, context)


@login_required
@require_POST
def course_revision_start(request: HttpRequest, course_slug: str) -> HttpResponse:
    """Start a revision session: the due questions, or the weakest ones when none is due."""
    gate = _revision_record(request, course_slug)
    if isinstance(gate, HttpResponseRedirect):
        return gate
    course, record = gate
    state = build_session(cast("User", request.user), record, timezone.now())
    if state.question_ids:
        _store_revision_state(request, course, state)
    response = redirect("learner_interface:course_revision", course_slug=course.slug)
    # See Other: the browser follows a POST with a GET of the revision page.
    response.status_code = 303
    return response


@login_required
@require_POST
def partial_course_revision_answer(
    request: HttpRequest, course_slug: str
) -> HttpResponse:
    """Mark the posted answer to the session's current question and show its feedback."""
    gate = _revision_record(request, course_slug)
    if isinstance(gate, HttpResponseRedirect):
        # Not a plain redirect: htmx would draw the page it lands on inside the card.
        return _revision_redirect(request, gate.url)
    course, record = gate
    state = _revision_state(request, course)
    if state is None:
        return _revision_page_redirect(request, course)
    question, state = _current_revision_question(record, state)
    if question is None:
        _store_revision_state(request, course, state)
        return _revision_page_redirect(request, course)
    # Skipped questions moved the index; keep the state the learner now sits on.
    _store_revision_state(request, course, state)

    if (
        _revision_review_of(cast("User", request.user), course, state, question)
        is not None
    ):
        return _render_revision_card(request, course, record, state)

    own_option_ids = {option.id for option in live_options(question)}
    selected: set[uuid.UUID] = set()
    for value in request.POST.getlist(f"question_{question.id}"):
        try:
            option_id = uuid.UUID(value)
        except ValueError:
            continue
        if option_id in own_option_ids:
            selected.add(option_id)
    if not selected:
        return _render_revision_card(
            request, course, record, state, error="Choose an answer.", status=422
        )
    record_answer(
        cast("User", request.user),
        record,
        question,
        selected,
        timezone.now(),
        session_started_at=state.started_at,
    )
    return _render_revision_card(request, course, record, state)


@login_required
@require_POST
def partial_course_revision_next(
    request: HttpRequest, course_slug: str
) -> HttpResponse:
    """Move to the next question once the current one has been answered."""
    gate = _revision_record(request, course_slug)
    if isinstance(gate, HttpResponseRedirect):
        # Not a plain redirect: htmx would draw the page it lands on inside the card.
        return _revision_redirect(request, gate.url)
    course, record = gate
    state = _revision_state(request, course)
    if state is None:
        return _revision_page_redirect(request, course)
    question, state = _current_revision_question(record, state)
    if question is not None and _revision_review_of(
        cast("User", request.user), course, state, question
    ):
        state = state.advanced()
    _store_revision_state(request, course, state)
    if request.headers.get("HX-Request") != "true":
        return _revision_page_redirect(request, course)
    return _render_revision_card(request, course, record, state)


@login_required
def course_finish(request, course_slug):
    """Mark the course progress as complete for this user and render a completion page."""

    course = get_object_or_404(Course, slug=course_slug)
    no_access = _course_access_redirect(
        _course_access_decision(request.user, course),
        course,
        route=PlayerRoute.FINISH,
    )
    if no_access is not None:
        return no_access

    # The record the learner's registration granted, minted here if it is
    # missing -- the same self-healing path the rest of the player takes, so a
    # registration made before course progress records existed does not turn a
    # bookmarked finish URL into a 404. None means nothing grants them this
    # course, so there is no pass to finish -- 404 rather than dereferencing None.
    course_progress = _ensure_player_course_progress(request.user, course)
    if course_progress is None:
        raise Http404("No course progress record for this learner and course.")

    # Mark as complete if not already. A course is complete when every item in
    # it is, so an unread topic or an unpassed quiz withholds the completion —
    # the page still renders, naming what is left and linking to each item.
    #
    # The stamp and the webhook share this branch deliberately: an announced
    # completion cannot be taken back, so neither may happen without the other.
    still_to_do = outstanding_items(course_progress, course)

    if not course_progress.completed_time and not still_to_do:
        course_progress.completed_time = timezone.now()
        course_progress.save(update_fields=["completed_time"])

        from freedom_ls.webhooks.events import fire_webhook_event

        fire_webhook_event(
            "course.completed",
            {
                "user_id": request.user.pk,
                "user_email": request.user.email,
                "course_id": str(course.id),
                "course_title": course.title,
                "completed_time": course_progress.completed_time.isoformat(),
                "organisation_id": str(course_progress.learner.organisation_id),
                "course_progress_id": str(course_progress.id),
            },
        )
        record_course_completed(
            request,
            course,
            via_cohort=course_progress.cohort_registration_id is not None,
        )

    context = {
        "course": course,
        "course_progress": course_progress,
        "outstanding_items": still_to_do,
        # Outline panel for the completion page (no single current item).
        # can_access_content=True: the learner reached the end of the course, so
        # they have had content access throughout, whether or not the completion
        # was withheld.
        "course_index": _course_index_without_current_row(
            request, course, course_progress
        ).rows,
        # The finish page is open only to a learner with content access.
        "reference_linked": True,
        "revision_due_text": _revision_due_badge(
            request.user, course_progress, timezone.now()
        ),
        **_time_zone_context(request),
    }

    return render(request, "learner_interface/course_finish.html", context)


def _posted_page_number(post_data: QueryDict) -> int | None:
    """The page number a page-bearing POST names, or None when it names none."""
    try:
        return int(post_data.get("page_number", ""))
    except ValueError:
        return None


def _posted_page(path: SittingPath, post_data: QueryDict) -> CurrentPage | None:
    """The page a submit-and-exit POST was made from.

    The exit dialog retargets the runner page form here, so the POST holds the
    page the learner was standing on — named by a hidden field, because this
    endpoint's URL has no page in it. save_answers() clears any question it is
    handed no answer for, so only that page's questions may be passed; a POST
    that names no usable page saves nothing rather than guessing at one.
    """
    page_number = _posted_page_number(post_data)
    return None if page_number is None else page_at(path, page_number)


@login_required
@require_POST
def form_submit_and_exit(
    request: HttpRequest, course_slug: str, index: int
) -> HttpResponse:
    """POST-only endpoint: finalise the learner's current attempt and redirect to results.

    Used by the exit dialog's "Leave and submit" action on submit-on-exit forms.
    Calling complete() is idempotent so double-submits are safe.

    Required answers are deliberately not enforced: leaving scores the attempt
    as it stands, so a blank required question must not trap the learner in the
    dialog. An answer that fails its type's check is the other case — it cannot
    be stored, and finalising on it would freeze the attempt without it and
    leave nowhere to put it right. That one sends the learner back to the page.
    """
    course = get_object_or_404(Course, slug=course_slug)
    decision = _course_access_decision(request.user, course)
    collection_item = get_form_collection_item_for_index(course, index)
    found = _open_sitting_at(cast("User", request.user), course, collection_item)
    now = timezone.now()
    # The countdown's post at zero. The server never takes its word that time is
    # up: one that arrives early saves its page below and completes nothing.
    time_up = "time_up" in request.POST
    # The page a post was made from is still the learner's work when the post
    # lands just after the clock ran out, whichever button sent it. Past the
    # window nothing is saved, and the sitting completes just below.
    if (
        found is not None
        and (
            found.sitting.accepts_time_up(now)
            if time_up
            else found.sitting.in_grace(now)
        )
        and _save_page_and_complete(
            found.course_progress,
            found.sitting,
            _posted_page_number(request.POST),
            request.POST,
            now,
            time_up=time_up,
        )
    ):
        return redirect(
            "learner_interface:course_form_complete",
            course_slug=course_slug,
            index=index,
        )
    expired = _expired_sitting_redirect(
        cast("User", request.user), course, collection_item, index, found
    )
    if expired is not None:
        return expired
    no_access = _course_access_redirect(
        decision,
        course,
        route=PlayerRoute.SUBMIT_AND_EXIT,
        collection_item=collection_item,
    )
    if no_access is not None:
        return no_access
    form = cast("Form", collection_item.child)

    # No sequential-unlock gate here, deliberately: this finalises an attempt the
    # learner already started, and refusing it would strand that attempt
    # incomplete for good. Creating an attempt still requires form_start, which
    # is gated.
    # The exit dialog only renders this POST for submit-on-exit forms, but the
    # endpoint is reachable directly. Save-on-exit forms promise the attempt is
    # saved (resumable), not scored, so never finalise one here — send the
    # learner back to the form start screen instead.
    course_progress = _ensure_player_course_progress(request.user, course)
    # A closed form, or one whose learner's access has ended, can no longer be
    # continued, so its open attempt is finalised whatever its exit strategy; the
    # learner would otherwise be stuck with it.
    closed = decision.access_ended_at is not None or _is_closed_for_learner(
        course_progress, collection_item, timezone.now()
    )
    if not form.submit_on_exit and not closed and not time_up:
        return redirect(
            "learner_interface:view_course_item",
            course_slug=course_slug,
            index=index,
        )

    form_progress = (
        get_latest_incomplete(course_progress, collection_item)
        if course_progress is not None
        else None
    )
    if (
        form_progress is not None
        and not closed
        and sitting_needs_declaration(form_progress)
    ):
        return _declaration_redirect(course_slug, index)
    if form_progress is not None:
        ensure_served_paper(form_progress)
        # Nothing posted is saved once closed: the item has no later to resume in.
        # Save before completing, so score() sees the page the learner was on.
        posted = (
            None if closed else _posted_page(current_path(form_progress), request.POST)
        )
        if posted is not None:
            submission = submit_page(
                posted, request.POST, form_progress, require_answers=False
            )
            if not submission.accepted:
                # The answers that were saved can change which pages come next.
                return _render_form_fill_page(
                    request,
                    course,
                    form,
                    index,
                    resolve_page(current_path(form_progress), posted.number),
                    course_progress,
                    form_progress,
                    submission,
                    reference_linked=decision.can_access_content,
                    decision=decision,
                    now=now,
                )
        if time_up and not closed:
            # Time is not up by the server's clock: the device's ran ahead, or
            # the limit was raised or removed while the page was open. The page
            # is saved and the learner carries on from it.
            if posted is None:
                return _form_page_redirect(course_slug, index, form_progress)
            return redirect(_form_page_url(course_slug, index, posted.number))
        form_progress.complete()  # idempotent

    return redirect(
        "learner_interface:course_form_complete",
        course_slug=course_slug,
        index=index,
    )


if TYPE_CHECKING:
    from collections.abc import Mapping

    from django.db.models import QuerySet

    from freedom_ls.accounts.models import User
    from freedom_ls.course_access.backends import (
        CourseAccessBackend,
        CourseAccessDecision,
        DashboardContribution,
        RequestUser,
    )


@login_required
@require_POST
def partial_course_revision_guessed(
    request: HttpRequest, course_slug: str
) -> HttpResponse:
    """Flip "I guessed" on the current question's right answer."""
    gate = _revision_record(request, course_slug)
    if isinstance(gate, HttpResponseRedirect):
        # Not a plain redirect: htmx would draw the page it lands on inside the card.
        return _revision_redirect(request, gate.url)
    course, record = gate
    state = _revision_state(request, course)
    if state is None:
        return _revision_page_redirect(request, course)
    question, state = _current_revision_question(record, state)
    if question is None:
        _store_revision_state(request, course, state)
        return _revision_page_redirect(request, course)
    _store_revision_state(request, course, state)

    review = _revision_review_of(cast("User", request.user), course, state, question)
    if review is None:
        return _render_revision_card(request, course, record, state, status=422)
    try:
        mark_guessed(review)
    except GuessRefused:
        return _render_revision_card(request, course, record, state, status=422)
    return _render_revision_card(request, course, record, state)
