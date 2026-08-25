from __future__ import annotations

import contextlib
import uuid
from typing import TYPE_CHECKING, cast

from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import Site
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

from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CourseVisibility,
    Topic,
)
from freedom_ls.course_access.loader import get_course_access_backend
from freedom_ls.course_access.overrides import (
    is_coming_soon_for_display,
    override_visibility_to_visible,
)
from freedom_ls.course_access.visibility import raise_404_if_hidden_unregistered
from freedom_ls.course_interest.queries import stamp_interest
from freedom_ls.form_engine.models import Form, FormProgress, FormQuestion, FormStrategy
from freedom_ls.form_engine.queries import count_form_questions, page_questions
from freedom_ls.form_engine.submissions import has_submitted_answer
from freedom_ls.learner_management.config import config
from freedom_ls.learner_management.deadline_utils import is_item_locked_by_deadline
from freedom_ls.learner_management.models import (
    LearnerCourseRegistration,
    RecommendedCourse,
)
from freedom_ls.learner_management.queries import (
    learner_for_course,
)
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.learner_progress.attempts import (
    completed_attempts,
    finalise_stale_incomplete,
    get_latest_incomplete,
    get_or_create_incomplete,
)
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.learner_progress.queries import course_progress_for
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.site_aware_models.models import get_cached_site

from .utils import (
    BLOCKED,
    IN_PROGRESS,
    READY,
    UNRESOLVED,
    Unresolved,
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
    get_recommended_courses,
    get_resume_index,
    outstanding_items,
    stamp_course_access_badge,
)


def _annotate_next_up(course: Course, user, *, can_access_content: bool) -> None:
    """Pick the first IN_PROGRESS child (then READY) and stamp it on the course.

    Walks at most two levels of ``get_course_index`` (top-level children plus
    their direct children — which matches the depth ``get_course_index``
    itself produces). Sets empty strings when nothing is actionable so the
    template never renders ``Next up:`` with a blank tail.

    ``can_access_content`` is passed through from the dashboard's per-course
    backend decision so that get_course_index is not called with a stale value.
    """
    children = get_course_index(
        user=user, course=course, can_access_content=can_access_content
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


def _detail_cta_label(course: Course, user: User) -> str:
    """Progress-aware CTA label for a registered learner on the course detail page.

    Reads the resolved record — does not scan TopicProgress/FormProgress. Only
    call this for registered learners; unregistered paths use decision.cta_label.

    "Start course" is keyed on the percentage, never on the row existing: a
    record is minted by the registration, so a learner who has never opened the
    course still has one.
    """
    progress = course_progress_for(user, course)
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
    the wrapper's rule. Only pks are queried; the already-fetched rec.collection
    instances are reused for rendering.
    """
    recs = list(get_recommended_courses(user))
    visible_rec_ids = set(
        backend.filter_visible(
            user=user,
            courses=Course.objects.filter(pk__in=[rec.collection_id for rec in recs]),
        ).values_list("pk", flat=True)
    )
    return [rec for rec in recs if rec.collection_id in visible_rec_ids]


def _annotate_registered_courses(
    courses: list[Course], user, backend: CourseAccessBackend
) -> None:
    """Stamp registration status, listing status and the next-up item onto each course.

    ``get_current_courses`` already excludes completed courses and stamps
    ``progress_percentage``, so the listing status here is only ever registered
    (0%) or in_progress (>0%).
    """
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
        course_decision = backend.get_access(user=user, course=course)
        _annotate_next_up(
            course,
            user,
            can_access_content=course_decision.can_access_content,
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
        setattr(rec.collection, "is_registered", False)  # noqa: B010
        setattr(  # noqa: B010
            rec.collection,
            "listing_status",
            derive_listing_status(
                is_registered=False,
                is_coming_soon=is_coming_soon_for_display(rec.collection),
                is_complete=False,
                progress_percentage=0,
            ),
        )


def _available_courses(
    user, backend: CourseAccessBackend, *, excluded_ids: set[uuid.UUID]
) -> list[Course]:
    """Up to three discovery courses the user is neither registered for nor recommended.

    Runs for both auth states — anonymous visitors simply arrive with an empty
    registration half of ``excluded_ids``.
    """
    visible_courses = backend.filter_visible(user=user, courses=get_all_courses())
    available_courses: list[Course] = []
    for course in visible_courses:
        if course.id in excluded_ids:
            continue
        setattr(course, "is_registered", False)  # noqa: B010
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
        available_courses.append(course)
        if len(available_courses) == 3:
            break
    return available_courses


def dashboard(request: HttpRequest) -> HttpResponse:
    """Dashboard view — authenticated or anonymous.

    Authenticated users see their personalised course lists, backend-contributed
    panels, and the welcome greeting. Anonymous users see a hero and the
    discovery (available courses) section only. Both states share a single code
    path; personalised work is guarded by ``is_auth`` to avoid unnecessary
    backend calls for anonymous visitors.
    """
    backend = get_course_access_backend()
    is_auth = request.user.is_authenticated

    # These helpers are all anonymous-safe (return empty lists / querysets for
    # unauthenticated users), so they run unconditionally.
    registered_courses = get_current_courses(request.user)
    completed_courses = get_completed_courses(request.user)
    recommended_courses = _visible_recommendations(request.user, backend)

    if is_auth:
        _annotate_registered_courses(registered_courses, request.user, backend)
        _annotate_completed_courses(completed_courses)
        _annotate_recommendations(recommended_courses)

    excluded_ids = (
        {c.id for c in get_course_registrations(request.user)} if is_auth else set()
    ) | {rec.collection_id for rec in recommended_courses}
    available_courses = _available_courses(
        request.user, backend, excluded_ids=excluded_ids
    )

    # Dashboard contributions from the active backend (e.g. the applications panel).
    # Only fetched for authenticated users — anonymous visitors have no panels,
    # and calling get_dashboard_contributions for an anonymous user is unnecessary.
    dashboard_panels: list[str] = []
    if is_auth:
        contributions = backend.get_dashboard_contributions(user=request.user)
        dashboard_panels = [
            render_to_string(c.template_name, c.context, request=request)
            for c in contributions
        ]

    context = {
        "registered_courses": registered_courses,
        "completed_courses": completed_courses,
        "recommended_courses": recommended_courses,
        "available_courses": available_courses,
        "dashboard_panels": dashboard_panels,
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
    for entry in entries:
        course = entry.course
        setattr(course, "listing_status", entry.status)  # noqa: B010
        setattr(course, "progress_percentage", entry.progress_percentage)  # noqa: B010
        stamp_course_access_badge(course, badge=entry.access_badge)
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
    course = get_object_or_404(Course, slug=course_slug)
    # Two distinct registration signals, intentionally both fetched: is_registered
    # drives the template (TOC partialdef) and the three-state CTA vocabulary, while
    # decision.can_access_content drives the content gate. They diverge for an
    # invalid-config course, so neither can be derived from the other.
    is_registered = get_is_registered(user=request.user, course=course)
    # Hidden courses 404 for anyone not registered, matching the wrapper's
    # filter_visible rule (coming_soon and published detail pages stay accessible).
    raise_404_if_hidden_unregistered(request.user, course)
    decision = get_course_access_backend().get_access(user=request.user, course=course)
    # get_course_index is anonymous-safe (it fetches user-scoped progress/deadlines
    # only behind its own is_authenticated / can_access_content guards).
    children = get_course_index(
        user=request.user, course=course, can_access_content=decision.can_access_content
    )
    start_url: str | None
    cta_label: str | None
    if is_registered:
        # Registered learners get the richer progress-aware helpers: "Start course",
        # "Continue", "Review course". Do NOT route registered learners through
        # decision.cta_label — it would regress the three-state vocabulary to "Continue".
        start_url = _detail_start_url(
            course, is_registered=True, has_items=bool(children)
        )
        # is_registered implies an authenticated User, so the cast is safe here.
        cta_label = _detail_cta_label(course, cast("User", request.user))
    else:
        # Not-registered: use the backend's acquisition affordance (e.g. "Enrol for free"
        # for free courses, "Apply now" for application-gated courses). May be None for
        # backends that provide no CTA (e.g. invalid config) — <c-button href=""> renders disabled.
        start_url = decision.cta_url
        cta_label = decision.cta_label
    # Coming-soon courses render the shared express-interest control in the
    # not-registered branch instead of the generic enrol anchor (which would
    # GET a POST-only endpoint and can't reflect existing interest). Stamp the
    # course's current interest state so the partial picks the right variant.
    is_coming_soon = is_coming_soon_for_display(course)
    if is_coming_soon and not is_registered:
        stamp_interest(request.user, [course])
    breadcrumbs = [
        {"label": "All courses", "url": reverse("learner_interface:courses")},
        {"label": course.title},
    ]
    viewable = course.viewable_items()
    # "Lessons" counts content items only — assessments (Form children) are
    # surfaced separately via ``includes_assessments``, so exclude them here.
    lesson_count = sum(1 for c in viewable if not isinstance(c, Form))
    lesson_count_label = f"{lesson_count} lesson{'' if lesson_count == 1 else 's'}"
    includes_assessments = any(isinstance(c, Form) for c in viewable)

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

    return render(
        request,
        "learner_interface/course_detail.html",
        {
            "course": course,
            "children": children,
            "is_registered": is_registered,
            "is_coming_soon": is_coming_soon,
            "start_url": start_url,
            "cta_label": cta_label,
            # Acquisition-funnel copy is access-type-specific and comes from the
            # backend decision (not the CTA-state helpers above), so it is correct
            # for gated courses as well as free ones.
            "enrolment_summary": decision.enrolment_summary,
            "acquisition_heading": decision.acquisition_heading,
            "acquisition_subtext": decision.acquisition_subtext,
            "breadcrumbs": breadcrumbs,
            "lesson_count": lesson_count,
            "lesson_count_label": lesson_count_label,
            "includes_assessments": includes_assessments,
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
    raise_404_if_hidden_unregistered(request.user, course)

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


@login_required
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
    raise_404_if_hidden_unregistered(request.user, course)
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

    # Create the course registration directly on the learner. No organisation
    # is in scope for a self-service registration, so it lands on the Site's
    # default Organisation — guaranteed to exist by the post_save receiver
    # that gives every Site one. ensure_learner reactivates a removed learner,
    # so re-registering is a live signal of re-association.
    learner = ensure_learner(
        request.user,
        # get_cached_site's RequestSite branch only applies with the Sites
        # framework absent, which FLS always has installed.
        get_default_organisation(cast(Site, get_cached_site(request))),
    )
    # update_or_create, not get_or_create: defaults only apply on create, so a
    # registration an admin had deactivated would stay inactive and the learner
    # would be bounced back out of the course they just asked to enter.
    LearnerCourseRegistration.objects.update_or_create(
        learner=learner,
        collection=course,
        defaults={"is_active": True},
    )

    # Delete any existing RecommendedCourse for this user and course
    RecommendedCourse.objects.filter(user=request.user, collection=course).delete()

    # Redirect into the player. course_home is now a resume redirector, so a
    # freshly registered (0-progress) learner lands on the first course item.
    return redirect("learner_interface:course_home", course_slug=course_slug)


def _course_access_redirect(
    user: RequestUser, course: Course
) -> HttpResponseRedirect | None:
    """Turn away anyone the course itself is closed to, or None if it is open.

    The same pair of gates for every route that serves or accepts a course item:
    a hidden course must 404 rather than 302 (a redirect would confirm it exists),
    and the access backend decides whether this learner may see content at all.
    """
    raise_404_if_hidden_unregistered(user, course)
    decision = get_course_access_backend().get_access(user=user, course=course)
    if not decision.can_access_content:
        return redirect("learner_interface:course_detail", course_slug=course.slug)
    return None


def _blocked_item_redirect(
    user: RequestUser,
    course: Course,
    index: int,
    *,
    course_index: list[dict] | None = None,
    course_progress: CourseProgress | None | Unresolved = UNRESOLVED,
) -> HttpResponseRedirect | None:
    """Turn away an item the course index shows as BLOCKED, or None if it is open.

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
    if current_entry_status(course_index) == BLOCKED:
        # course_detail, never course_home: course_home resumes to the last item
        # accessed, which would bounce straight back here.
        return redirect("learner_interface:course_detail", course_slug=course.slug)
    return None


@login_required
def view_course_item(request, course_slug, index):
    course = get_object_or_404(Course, slug=course_slug)
    # Hidden-course 404 plus the content-access gate. Closes the hole where an
    # unregistered learner could view a free course's content by guessing the URL
    # (the TOC hides the links as BLOCKED, but the URL was previously unguarded).
    no_access = _course_access_redirect(request.user, course)
    if no_access is not None:
        return no_access

    viewable_collection_items = course.viewable_collection_items()
    if index < 1 or index > len(viewable_collection_items):
        raise Http404("No course item at this index.")
    current_collection_item = viewable_collection_items[index - 1]
    current_item = current_collection_item.child
    viewable_items = [item.child for item in viewable_collection_items]

    # The record every write below lands in, minted from the registration if it
    # is missing. This is the self-healing path: a registration made before
    # course progress records existed gets one the first time the learner opens
    # the course, which is why no backfill is needed.
    course_progress = _ensure_player_course_progress(request.user, course)

    # Check if item is locked by a hard deadline
    if config.DEADLINES_ACTIVE and request.user.is_authenticated:
        is_completed = _is_content_item_completed(
            current_collection_item, course_progress
        )
        if is_item_locked_by_deadline(
            request.user, course, current_item, is_completed=is_completed
        ):
            # Redirect to the loop-free detail page. course_home is now a
            # resume redirector, so redirecting a locked item there would loop
            # straight back to the same locked item.
            return redirect("learner_interface:course_detail", course_slug=course_slug)

    # Sequential-unlock gate. Built here rather than inside _player_chrome_context
    # so the decision is made before anything is written, then handed on to the
    # chrome so the index is built once.
    course_index = get_course_index(
        user=request.user,
        course=course,
        current_index=index,
        can_access_content=True,
        course_progress=course_progress,
    )
    blocked = _blocked_item_redirect(
        request.user, course, index, course_index=course_index
    )
    if blocked is not None:
        return blocked

    total = len(viewable_items)

    # Record this collection item as the resume target. This is the single
    # write point for both topics and forms, so resume no longer depends on
    # per-item progress timestamps. The deadline-locked and sequential-unlock
    # branches return above, so a locked item is never recorded.
    #
    # last_accessed_time is written here rather than by auto_now, so a
    # background percentage recalculation never looks like a visit. started_at
    # is stamped once, on first content access, and never re-stamped.
    if course_progress is not None:
        now = timezone.now()
        course_progress.last_accessed_item = current_collection_item
        course_progress.last_accessed_time = now
        if course_progress.started_at is None:
            course_progress.started_at = now
        course_progress.save(
            update_fields=["last_accessed_item", "last_accessed_time", "started_at"]
        )

    # Calculate navigation URLs
    is_last_item = index >= total
    next_url = (
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course_slug, "index": index + 1},
        )
        if index < total
        else None
    )
    previous_url = (
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course_slug, "index": index - 1},
        )
        if index > 1
        else None
    )

    # Player chrome context shared by topic and form item pages: the outline
    # with the current item marked, the containing part (for breadcrumb / title),
    # the CourseProgress (for the header progress bar / %), and the 1-based index.
    # Reuse the viewable_items already resolved above so the chrome helper does
    # not re-traverse the course a second time.
    player_context = _player_chrome_context(
        request.user,
        course,
        current_item,
        index,
        viewable_items=viewable_items,
        course_index=course_index,
        course_progress=course_progress,
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
        )

    if isinstance(current_item, Form):
        return view_form(
            request,
            form=current_item,
            course=course,
            index=index,
            is_last_item=is_last_item,
            next_url=next_url,
            player_context=player_context,
            collection_item=current_collection_item,
            course_progress=course_progress,
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


def _player_chrome_context(
    user,
    course: Course,
    current_item: Topic | Form,
    index: int,
    viewable_items: list | None = None,
    course_index: list[dict] | None = None,
    course_progress: CourseProgress | None | Unresolved = UNRESOLVED,
) -> dict:
    """Build the shared player-chrome context (TOC, breadcrumb, header, title).

    ``viewable_items``, ``course_index`` and ``course_progress`` may be passed
    in by a caller that has already resolved them (``view_course_item`` builds
    all three to run its gates and its write) to avoid doing the work twice;
    callers that have not let them default. Passing ``course_progress=None``
    means "there is no record", and is not the same as leaving it out.
    """
    if viewable_items is None:
        viewable_items = course.viewable_items()
    if isinstance(course_progress, Unresolved):
        course_progress = (
            course_progress_for(user, course) if user.is_authenticated else None
        )
    # Read off the record rather than resolving the registration a second time:
    # the record's learner already names the organisation this pass is being
    # studied through, which is what the chrome is reporting.
    course_organisation = (
        course_progress.learner.organisation if course_progress is not None else None
    )
    current_part = get_item_part(course, current_item)

    # The breadcrumb part crumb links to the part's first viewable item. Resolve
    # its 1-based index in the already-computed viewable_items, in memory.
    current_part_index: int | None = None
    if current_part is not None:
        part_children = current_part.children()
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
        course_index = get_course_index(
            user=user, course=course, current_index=index, can_access_content=True
        )

    return {
        "course_index": course_index,
        "current_part": current_part,
        "current_part_index": current_part_index,
        "course_progress": course_progress,
        # Without a record there is nowhere to write a completion, so the
        # templates hide the controls that would offer one.
        "can_record_progress": course_progress is not None,
        "course_organisation": course_organisation,
        "item_title": current_item.title,
        "index": index,
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
):
    topic_progress = None
    if course_progress is not None:
        topic_progress, created = TopicProgress.objects.get_or_create(
            course_progress=course_progress,
            collection_item=collection_item,
            defaults={"site_id": course_progress.site_id, "topic": topic},
        )
        if not created:
            topic_progress.save()

    if request.method == "POST" and "mark_complete" in request.POST:
        if topic_progress is None:
            raise Http404("No course progress record to record this completion in.")
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
    player_context: dict | None = None,
    *,
    collection_item: ContentCollectionItem,
    course_progress: CourseProgress | None,
):
    """Show the front page of the form"""

    incomplete_form_progress = None
    completed_form_progress = FormProgress.objects.none()
    if course_progress is not None:
        # Finalise any stale incomplete attempt for submit-on-exit forms before
        # reading progress state. No-op for save-on-exit forms.
        finalise_stale_incomplete(course_progress, collection_item)

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
        page_number = incomplete_form_progress.get_current_page_number()

    # Determine which buttons to show
    buttons = form_start_page_buttons(
        form=form,
        incomplete_form_progress=incomplete_form_progress,
        completed_form_progress=completed_form_progress,
        is_last_item=is_last_item,
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
        **(player_context or {}),
        "question_count": count_form_questions(form),
        "page_count": form.pages.count(),
    }

    return render(request, "learner_interface/course_form.html", context)


@login_required
def form_start(request, course_slug, index):
    """Start or resume a form for the current user."""

    course = get_object_or_404(Course, slug=course_slug)
    no_access = _course_access_redirect(request.user, course)
    if no_access is not None:
        return no_access
    collection_item = get_form_collection_item_for_index(course, index)
    course_progress = _ensure_player_course_progress(request.user, course)

    # Minting the attempt is what would flip a locked quiz to IN_PROGRESS, so the
    # gate has to come before it — and before finalise_stale_incomplete, which
    # writes too. Minting the course progress record above changes no status.
    blocked = _blocked_item_redirect(
        request.user, course, index, course_progress=course_progress
    )
    if blocked is not None:
        return blocked

    if course_progress is None:
        # Nothing grants this learner the course, so there is no record to
        # attempt the form in. Send them back to the read-only start screen
        # rather than mint an attempt with no record behind it.
        return redirect(
            "learner_interface:view_course_item",
            course_slug=course_slug,
            index=index,
        )

    # Finalise any stale incomplete attempt for submit-on-exit forms before
    # get_or_create_incomplete runs. No-op for save-on-exit forms.
    finalise_stale_incomplete(course_progress, collection_item)

    # Create a FormProgress instance if it doesn't yet exist
    form_progress = get_or_create_incomplete(course_progress, collection_item)

    # Figure out what page of the form the user is on
    page_number = form_progress.get_current_page_number()

    # Redirect the user to form_fill_page
    return redirect(
        "learner_interface:form_fill_page",
        course_slug=course_slug,
        index=index,
        page_number=page_number,
    )


def _unanswered_required_message(questions: list[FormQuestion]) -> str:
    """Name the required questions the learner still has to answer."""
    numbers = [str(question.question_number()) for question in questions]
    if len(numbers) == 1:
        return f"Question {numbers[0]} needs an answer before you can continue."
    listed = f"{', '.join(numbers[:-1])} and {numbers[-1]}"
    return f"Questions {listed} need answers before you can continue."


@login_required
def form_fill_page(request, course_slug, index, page_number):
    course = get_object_or_404(Course, slug=course_slug)
    no_access = _course_access_redirect(request.user, course)
    if no_access is not None:
        return no_access
    collection_item = get_form_collection_item_for_index(course, index)
    form = cast("Form", collection_item.child)
    course_progress = _ensure_player_course_progress(request.user, course)

    # Gated ahead of the POST branch below, which saves answers and can complete
    # the attempt: a refused page must write nothing at all.
    blocked = _blocked_item_redirect(
        request.user, course, index, course_progress=course_progress
    )
    if blocked is not None:
        return blocked

    all_pages = list(form.pages.all())
    total_pages = len(all_pages)
    if page_number < 1 or page_number > total_pages:
        raise Http404("No form page at this number.")
    form_page = all_pages[page_number - 1]

    # Get the latest incomplete form progress instance
    form_progress = (
        get_latest_incomplete(course_progress, collection_item)
        if course_progress is not None
        else None
    )

    # Get existing answers for questions on this page
    questions = page_questions(form_page)

    next_page_url = (
        reverse(
            "learner_interface:form_fill_page",
            kwargs={
                "course_slug": course_slug,
                "index": index,
                "page_number": page_number + 1,
            },
        )
        if page_number < total_pages
        else None
    )

    # Set when a submission is rejected for missing required answers: the page is
    # re-rendered carrying it instead of advancing or completing.
    required_answers_error = ""

    if request.method == "POST":
        # No incomplete attempt to save into (e.g. it was finalised by a
        # submit-on-exit safety net, or the page was reached without starting).
        # Send the learner back to the form start screen rather than 500.
        if form_progress is None:
            return redirect(
                "learner_interface:view_course_item",
                course_slug=course_slug,
                index=index,
            )

        unanswered_required = [
            question
            for question in questions
            if question.required and not has_submitted_answer(question, request.POST)
        ]

        # Save regardless, so a rejected submission does not throw away the
        # answers the learner did give.
        form_progress.save_answers(questions, request.POST)

        if not unanswered_required:
            if next_page_url:
                return redirect(next_page_url)

            # Mark form as completed and calculate scores
            form_progress.complete()

            return redirect(
                "learner_interface:course_form_complete",
                course_slug=course_slug,
                index=index,
            )

        required_answers_error = _unanswered_required_message(unanswered_required)

    previous_page_url = (
        reverse(
            "learner_interface:form_fill_page",
            kwargs={
                "course_slug": course_slug,
                "index": index,
                "page_number": page_number - 1,
            },
        )
        if page_number > 1
        else None
    )

    # No incomplete attempt to resume (e.g. the form is already completed, or it
    # was finalised by a submit-on-exit safety net). Send the learner back to the
    # form start screen rather than dereferencing None and 500ing, mirroring the
    # POST branch above.
    if form_progress is None:
        return redirect(
            "learner_interface:view_course_item",
            course_slug=course_slug,
            index=index,
        )

    # Build a dictionary of existing answers keyed by question ID
    existing_answers = form_progress.existing_answers_dict(questions)

    # A skipped question leaves no answer row behind, so the first-outstanding
    # page can sit behind where the learner has actually reached. On its own it
    # would lock the page they are standing on, and pages they have already
    # answered, out of the page-jump navigation.
    answered_page_ids = set(
        form_progress.answers.values_list("question__form_page_id", flat=True)
    )
    furthest_answered_page = max(
        (
            number
            for number, page in enumerate(all_pages, start=1)
            if page.id in answered_page_ids
        ),
        default=0,
    )
    furthest_page = max(
        form_progress.get_current_page_number(), page_number, furthest_answered_page
    )

    # Build list of all page objects with their URLs for navigation
    page_links = []
    for i in range(1, total_pages + 1):
        page_links.append(
            {
                "number": i,
                "title": all_pages[i - 1].title,
                "url": reverse(
                    "learner_interface:form_fill_page",
                    kwargs={
                        "course_slug": course_slug,
                        "index": index,
                        "page_number": i,
                    },
                ),
                "is_current": i == page_number,
                "is_accessible": i
                <= furthest_page,  # Can access all pages up to furthest progress
            }
        )

    # answered_count is the no-JS fallback (persisted answers only); answered_other_pages
    # is the base the client adds the live current-page tally to. Questions on this page
    # are excluded so the in-browser count is not double-counted.
    answered_count = form_progress.answers.count() if form_progress else 0
    current_page_question_ids = {q.id for q in questions}
    answered_other_pages = (
        form_progress.answers.exclude(question_id__in=current_page_question_ids).count()
        if form_progress
        else 0
    )
    total_question_count = count_form_questions(form)

    # URL for the submit-and-exit endpoint (used by the exit dialog)
    submit_and_exit_url = reverse(
        "learner_interface:form_submit_and_exit",
        kwargs={"course_slug": course_slug, "index": index},
    )

    # URL for the save-and-exit link (used by the exit dialog)
    save_and_exit_url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course_slug, "index": index},
    )

    context = {
        "course": course,
        "form": form,
        "form_page": form_page,
        "form_progress": form_progress,
        "current_page_num": page_number,
        "total_pages": total_pages,
        "previous_page_url": previous_page_url,
        "has_next_page": next_page_url,
        "existing_answers": existing_answers,
        "page_links": page_links,
        # Player chrome (outline panel + breadcrumb) so the fill page keeps the
        # same orientation as the rest of the player.
        **_player_chrome_context(
            request.user, course, form, index, course_progress=course_progress
        ),
        "answered_count": answered_count,
        "answered_other_pages": answered_other_pages,
        "total_question_count": total_question_count,
        "submit_and_exit_url": submit_and_exit_url,
        "save_and_exit_url": save_and_exit_url,
        "required_answers_error": required_answers_error,
    }

    # A rejected submission is a validation failure, not a fresh page view.
    response = render(
        request,
        "learner_interface/course_form_page.html",
        context,
        status=422 if required_answers_error else 200,
    )
    # Runner pages must re-fetch on back-nav so the answered count is never stale.
    response["Cache-Control"] = "no-store"
    return response


@login_required
def course_form_complete(request, course_slug, index):
    course = get_object_or_404(Course, slug=course_slug)
    no_access = _course_access_redirect(request.user, course)
    if no_access is not None:
        return no_access
    # No sequential-unlock gate here, deliberately: this page only reads back a
    # sitting the learner already made, and a learner is always entitled to the
    # score they earned — including after a deadline has closed the quiz itself.
    # Fetch the collection items once and reuse them (they are not cached); the
    # view also needs the list length below for is_last_item.
    viewable_collection_items = course.viewable_collection_items()
    collection_item = get_form_collection_item_for_index(
        course, index, viewable_collection_items=viewable_collection_items
    )
    form = cast("Form", collection_item.child)

    course_progress = course_progress_for(request.user, course)

    # Get the most recent completed attempt at this placement
    form_progress = (
        completed_attempts(course_progress, collection_item).first()
        if course_progress is not None
        else None
    )

    # Get incorrect answers if this is a quiz with show_incorrect enabled
    incorrect_answers = []
    if form_progress:
        incorrect_answers = form_progress.get_incorrect_quiz_answers()

    # Only set for QUIZ forms; non-quiz forms do not have a numeric percentage.
    percentage = None
    if form_progress and form.strategy == FormStrategy.QUIZ:
        with contextlib.suppress(ValueError):
            percentage = form_progress.quiz_percentage()

    # Scores are frozen at submission and never rescored, so an attempt sat before
    # the marking rules changed can carry a score the review list below it
    # contradicts. The page has to own that rather than let the learner spot it.
    stored_score_outdated = False
    if form_progress and form.strategy == FormStrategy.QUIZ and form_progress.scores:
        current_scores = form_progress.compute_quiz_scores()
        # max_score too, not just score: a quiz that gained or lost a question
        # since the attempt shows a stale percentage the score alone cannot catch.
        stored_score_outdated = any(
            form_progress.scores.get(key) != current_scores[key]
            for key in ("score", "max_score")
        )

    # Three-state: "passed", "failed", or None for a quiz with no pass mark —
    # there is no bar to clear, so the results page must claim neither outcome.
    # The PDF report and the educator panel use the same guard.
    quiz_verdict = None
    if (
        form_progress
        and percentage is not None
        and form.quiz_pass_percentage is not None
    ):
        quiz_verdict = "passed" if form_progress.passed() else "failed"

    # Calculate next URL for continue button
    total_viewable_items = len(viewable_collection_items)
    is_last_item = index >= total_viewable_items
    if is_last_item:
        # Last item - go to course finish page
        next_url = reverse(
            "learner_interface:course_finish", kwargs={"course_slug": course_slug}
        )
    else:
        # Not last item - go to next item
        next_url = reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course_slug, "index": index + 1},
        )

    # Calculate retry URL
    retry_url = reverse(
        "learner_interface:form_start",
        kwargs={"course_slug": course_slug, "index": index},
    )

    context = {
        "course": course,
        "form": form,
        "form_progress": form_progress,
        "show_scores": True,
        "scores": form_progress.scores if form_progress else None,
        "incorrect_answers": incorrect_answers,
        "stored_score_outdated": stored_score_outdated,
        "quiz_verdict": quiz_verdict,
        "next_url": next_url,
        "retry_url": retry_url,
        # Player chrome (outline panel + breadcrumb).
        **_player_chrome_context(
            request.user, course, form, index, course_progress=course_progress
        ),
    }

    # Only include percentage in context for QUIZ forms (avoids None littering the context
    # for non-quiz forms; template branches on form.strategy == "QUIZ" already).
    if percentage is not None:
        context["percentage"] = percentage

    return render(request, "learner_interface/course_form_complete.html", context)


@login_required
def course_finish(request, course_slug):
    """Mark the course progress as complete for this user and render a completion page."""

    course = get_object_or_404(Course, slug=course_slug)

    # The record the learner's registration granted. Missing means nothing
    # grants them this course, so there is no pass to finish -- 404 rather than
    # dereferencing None.
    course_progress = course_progress_for(request.user, course)
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

    context = {
        "course": course,
        "course_progress": course_progress,
        "outstanding_items": still_to_do,
        # Outline panel for the completion page (no single current item).
        # can_access_content=True: the learner reached the end of the course, so
        # they have had content access throughout, whether or not the completion
        # was withheld.
        "course_index": get_course_index(
            user=request.user,
            course=course,
            can_access_content=True,
            course_progress=course_progress,
        ),
    }

    return render(request, "learner_interface/course_finish.html", context)


def _save_posted_page_answers(
    form: Form, form_progress: FormProgress, post_data: QueryDict
) -> None:
    """Persist the runner page's answers carried by a submit-and-exit POST.

    The exit dialog retargets the runner page form here, so the POST holds the
    page the learner was standing on — named by a hidden field, because this
    endpoint's URL has no page in it. save_answers() clears any question it is
    handed no answer for, so only that page's questions may be passed; a POST
    that names no usable page saves nothing rather than guessing at one.

    Required answers are deliberately not enforced. Leaving scores the attempt
    as it stands, which is the opposite of the Next/Submit path.
    """
    try:
        page_number = int(post_data.get("page_number", ""))
    except ValueError:
        return
    pages = list(form.pages.all())
    if not 1 <= page_number <= len(pages):
        return
    form_progress.save_answers(page_questions(pages[page_number - 1]), post_data)


@login_required
@require_POST
def form_submit_and_exit(request, course_slug: str, index: int):
    """POST-only endpoint: finalise the learner's current attempt and redirect to results.

    Used by the exit dialog's "Leave and submit" action on submit-on-exit forms.
    Calling complete() is idempotent so double-submits are safe.
    """
    course = get_object_or_404(Course, slug=course_slug)
    no_access = _course_access_redirect(request.user, course)
    if no_access is not None:
        return no_access
    collection_item = get_form_collection_item_for_index(course, index)
    form = cast("Form", collection_item.child)

    # No sequential-unlock gate here, deliberately: this finalises an attempt the
    # learner already started, and refusing it would strand that attempt
    # incomplete for good. Creating an attempt still requires form_start, which
    # is gated.
    # The exit dialog only renders this POST for submit-on-exit forms, but the
    # endpoint is reachable directly. Save-on-exit forms promise the attempt is
    # saved (resumable), not scored, so never finalise one here — send the
    # learner back to the form start screen instead.
    if not form.submit_on_exit:
        return redirect(
            "learner_interface:view_course_item",
            course_slug=course_slug,
            index=index,
        )

    course_progress = _ensure_player_course_progress(request.user, course)
    form_progress = (
        get_latest_incomplete(course_progress, collection_item)
        if course_progress is not None
        else None
    )
    if form_progress is not None:
        # Save before completing, so score() sees the page the learner was on.
        _save_posted_page_answers(form, form_progress, request.POST)
        form_progress.complete()  # idempotent

    return redirect(
        "learner_interface:course_form_complete",
        course_slug=course_slug,
        index=index,
    )


if TYPE_CHECKING:
    from freedom_ls.accounts.models import User
    from freedom_ls.course_access.backends import CourseAccessBackend, RequestUser


def _is_content_item_completed(
    collection_item: ContentCollectionItem, course_progress: CourseProgress | None
) -> bool:
    """Whether this placement is complete within this course progress record.

    Scoped to the record as well as the placement because it decides whether a
    hard deadline locks the item: the same topic completed in another course,
    or under another registration, must not unlock this one.
    """
    if course_progress is None:
        return False
    if isinstance(collection_item.child, Topic):
        return TopicProgress.objects.filter(
            course_progress=course_progress,
            collection_item=collection_item,
            complete_time__isnull=False,
        ).exists()
    return completed_attempts(course_progress, collection_item).exists()
