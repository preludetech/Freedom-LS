from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from freedom_ls.content_engine.models import (
    Course,
    Form,
    FormStrategy,
    Topic,
)
from freedom_ls.course_access.loader import get_course_access_backend
from freedom_ls.student_management.config import config
from freedom_ls.student_management.deadline_utils import is_item_locked_by_deadline
from freedom_ls.student_management.models import (
    RecommendedCourse,
    UserCourseRegistration,
)
from freedom_ls.student_progress.models import (
    CourseProgress,
    FormProgress,
    TopicProgress,
)

from .utils import (
    IN_PROGRESS,
    READY,
    access_badge_label,
    count_form_questions,
    form_start_page_buttons,
    get_all_courses,
    get_completed_courses,
    get_course_index,
    get_course_listing,
    get_course_registrations,
    get_current_courses,
    get_form_for_index,
    get_is_registered,
    get_item_part,
    get_recommended_courses,
    get_resume_index,
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
            "student_interface:initiate_course_access",
            kwargs={"course_slug": course.slug},
        )
    if has_items:
        return reverse(
            "student_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    return reverse(
        "student_interface:course_home",
        kwargs={"course_slug": course.slug},
    )


def _detail_cta_label(course: Course, user: User) -> str:
    """Progress-aware CTA label for a registered learner on the course detail page.

    Uses a single CourseProgress lookup — does not scan TopicProgress/FormProgress.
    Only call this for registered learners; unregistered paths use decision.cta_label.
    """
    progress = CourseProgress.objects.filter(user=user, course=course).first()
    if progress is None or progress.completed_time is None:
        if progress is not None and progress.progress_percentage > 0:
            return "Continue"
        return "Start course"
    return "Review course"


@login_required
def dashboard(request):
    """Authenticated dashboard listing the learner's courses."""
    backend = get_course_access_backend()
    registered_courses = get_current_courses(request.user)
    completed_courses = get_completed_courses(request.user)
    recommended_courses = get_recommended_courses(request.user)

    for course in registered_courses:
        setattr(course, "is_registered", True)  # noqa: B010
        # Registered learners can always access content for the default backend.
        # Pass can_access_content from the backend decision so a future backend
        # (e.g. subscription-gated) could revoke access without a separate check.
        course_decision = backend.get_access(user=request.user, course=course)
        _annotate_next_up(
            course, request.user, can_access_content=course_decision.can_access_content
        )
    for rec in recommended_courses:
        # Recommendations are by definition not yet registered, so they get
        # the not-registered card (single link to detail page).
        setattr(rec.collection, "is_registered", False)  # noqa: B010

    registered_ids = {c.id for c in get_course_registrations(request.user)}
    recommended_ids = {rec.collection_id for rec in recommended_courses}

    visible_courses = backend.filter_visible(
        user=request.user, courses=get_all_courses()
    )
    available_courses: list[Course] = []
    for course in visible_courses:
        if course.id in registered_ids or course.id in recommended_ids:
            continue
        setattr(course, "is_registered", False)  # noqa: B010
        available_courses.append(course)
        if len(available_courses) == 3:
            break

    # Dashboard contributions from the active backend (e.g. the applications panel).
    # Each contribution is rendered generically; the view never reads context keys and
    # never imports course_applications — the contributing backend owns the partial.
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
    return render(request, "student_interface/dashboard.html", context)


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
    for entry in entries:
        course = entry.course
        setattr(course, "listing_status", entry.status)  # noqa: B010
        setattr(course, "progress_percentage", entry.progress_percentage)  # noqa: B010
        setattr(  # noqa: B010
            course,
            "access_badge_label",
            access_badge_label(entry.is_accessible_for_free),
        )
        setattr(course, "is_accessible_for_free", entry.is_accessible_for_free)  # noqa: B010
    return render(
        request,
        "student_interface/all_courses.html",
        {"all_courses": [e.course for e in entries]},
    )


@login_required
def course_detail(request, course_slug):
    """Canonical course detail page — accessible on all screen sizes."""
    course = get_object_or_404(Course, slug=course_slug)
    # Two distinct registration signals, intentionally both fetched: is_registered
    # drives the template (TOC partialdef) and the three-state CTA vocabulary, while
    # decision.can_access_content drives the content gate. They diverge for an
    # invalid-config course, so neither can be derived from the other.
    is_registered = get_is_registered(user=request.user, course=course)
    decision = get_course_access_backend().get_access(user=request.user, course=course)
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
        cta_label = _detail_cta_label(course, request.user)
    else:
        # Not-registered: use the backend's acquisition affordance (e.g. "Enrol for free"
        # for free courses, "Apply now" for application-gated courses). May be None for
        # backends that provide no CTA (e.g. invalid config) — <c-button href=""> renders disabled.
        start_url = decision.cta_url
        cta_label = decision.cta_label
    breadcrumbs = [
        {"label": "All courses", "url": reverse("student_interface:courses")},
        {"label": course.title},
    ]
    viewable = course.viewable_items()
    # "Lessons" counts content items only — assessments (Form children) are
    # surfaced separately via ``includes_assessments``, so exclude them here.
    lesson_count = sum(1 for c in viewable if not isinstance(c, Form))
    lesson_count_label = f"{lesson_count} lesson{'' if lesson_count == 1 else 's'}"
    includes_assessments = any(isinstance(c, Form) for c in viewable)
    return render(
        request,
        "student_interface/course_detail.html",
        {
            "course": course,
            "children": children,
            "is_registered": is_registered,
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

    if (
        not get_course_access_backend()
        .get_access(user=request.user, course=course)
        .can_access_content
    ):
        return redirect("student_interface:course_detail", course_slug=course_slug)

    index = get_resume_index(request.user, course)
    return redirect(
        "student_interface:view_course_item",
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
            else redirect("student_interface:course_detail", course_slug=course_slug)
        )

    # Create the course registration directly with user
    UserCourseRegistration.objects.get_or_create(
        user=request.user,
        collection=course,
        defaults={"is_active": True},
    )

    # Delete any existing RecommendedCourse for this user and course
    RecommendedCourse.objects.filter(user=request.user, collection=course).delete()

    # Redirect into the player. course_home is now a resume redirector, so a
    # freshly registered (0-progress) learner lands on the first course item.
    return redirect("student_interface:course_home", course_slug=course_slug)


@login_required
def view_course_item(request, course_slug, index):
    course = get_object_or_404(Course, slug=course_slug)

    # Content-access gate: an unregistered learner (or one blocked by a gating
    # backend) is redirected to course_detail. This closes the hole where an
    # unregistered learner could view a free course's content by guessing the URL
    # (the TOC hides the links as BLOCKED, but the URL was previously unguarded).
    decision = get_course_access_backend().get_access(user=request.user, course=course)
    if not decision.can_access_content:
        return redirect("student_interface:course_detail", course_slug=course_slug)

    viewable_items = course.viewable_items()
    if index < 1 or index > len(viewable_items):
        raise Http404("No course item at this index.")
    current_item = viewable_items[index - 1]

    # Check if item is locked by a hard deadline
    if config.DEADLINES_ACTIVE and request.user.is_authenticated:
        is_completed = _is_content_item_completed(current_item, request.user)
        if is_item_locked_by_deadline(
            request.user, course, current_item, is_completed=is_completed
        ):
            # Redirect to the loop-free detail page. course_home is now a
            # resume redirector, so redirecting a locked item there would loop
            # straight back to the same locked item.
            return redirect("student_interface:course_detail", course_slug=course_slug)

    total = len(viewable_items)

    # Update or create course progress, recording this item as the resume
    # target. This is the single write point for both topics and forms, so
    # resume no longer depends on per-item progress timestamps. The
    # deadline-locked branch returns above, so a locked item is never recorded.
    if request.user.is_authenticated:
        course_progress, _ = CourseProgress.objects.get_or_create(
            user=request.user, course=course
        )
        course_progress.last_accessed_item = current_item
        course_progress.save()  # auto_now also bumps last_accessed_time

    # Calculate navigation URLs
    is_last_item = index >= total
    next_url = (
        reverse(
            "student_interface:view_course_item",
            kwargs={"course_slug": course_slug, "index": index + 1},
        )
        if index < total
        else None
    )
    previous_url = (
        reverse(
            "student_interface:view_course_item",
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
        request.user, course, current_item, index, viewable_items=viewable_items
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
        )

    raise Http404("Unsupported course item type.")


def _player_chrome_context(
    user,
    course: Course,
    current_item: Topic | Form,
    index: int,
    viewable_items: list | None = None,
) -> dict:
    """Build the shared player-chrome context (TOC, breadcrumb, header, title).

    ``viewable_items`` may be passed in by a caller that has already resolved it
    (``view_course_item``) to avoid re-traversing the course; callers that have
    not (the form fill / complete pages) let it default to ``viewable_items()``.
    """
    if viewable_items is None:
        viewable_items = course.viewable_items()
    course_progress = (
        CourseProgress.objects.filter(user=user, course=course).first()
        if user.is_authenticated
        else None
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

    return {
        # can_access_content=True: _player_chrome_context is only called after
        # the content-access gate in view_course_item has already passed, so the
        # learner is confirmed to have content access here.
        "course_index": get_course_index(
            user=user, course=course, current_index=index, can_access_content=True
        ),
        "current_part": current_part,
        "current_part_index": current_part_index,
        "course_progress": course_progress,
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
):
    topic_progress, created = TopicProgress.objects.get_or_create(
        user=request.user, topic=topic
    )
    if not created:
        topic_progress.save()

    if request.method == "POST" and "mark_complete" in request.POST:
        topic_progress.complete_time = timezone.now()
        topic_progress.save()

        if next_url:
            return redirect(next_url)
        else:
            # If no next_url (last item), redirect to course finish page
            return redirect("student_interface:course_finish", course_slug=course.slug)

    # Check if the course is already complete. Reuse the CourseProgress already
    # fetched into player_context rather than querying it a second time.
    player_context = player_context or {}
    course_progress = player_context.get("course_progress")
    is_course_complete = bool(course_progress and course_progress.completed_time)

    context = {
        "course": course,
        "topic": topic,
        "is_complete": topic_progress.complete_time is not None,
        "next_url": next_url,
        "previous_url": previous_url,
        "is_last_item": is_last_item,
        "is_course_complete": is_course_complete,
        **player_context,
    }
    return render(request, "student_interface/course_topic.html", context)


def view_form(
    request,
    form,
    course,
    index,
    is_last_item=False,
    next_url=None,
    player_context: dict | None = None,
):
    """Show the front page of the form"""

    # Finalise any stale incomplete attempt for submit-on-exit forms before reading
    # progress state. No-op for save-on-exit forms.
    FormProgress.finalise_stale_incomplete(request.user, form)

    # Try to get existing incomplete form progress (don't create if it doesn't exist)
    incomplete_form_progress = FormProgress.get_latest_incomplete(
        user=request.user, form=form
    )

    page_number = None
    if incomplete_form_progress:
        page_number = incomplete_form_progress.get_current_page_number()

    # Get the most-recent completed submissions for this user and form. The start
    # screen shows a compact summary of the 5 latest attempts; the button logic
    # only needs the latest via .first() (the queryset is ordered newest-first).
    completed_form_progress = FormProgress.objects.filter(
        user=request.user, form=form, completed_time__isnull=False
    ).order_by("-completed_time")[:5]

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

    return render(request, "student_interface/course_form.html", context)


@login_required
def form_start(request, course_slug, index):
    """Start or resume a form for the current user."""

    course = get_object_or_404(Course, slug=course_slug)
    form = get_form_for_index(course, index)

    # Finalise any stale incomplete attempt for submit-on-exit forms before
    # get_or_create_incomplete runs. No-op for save-on-exit forms.
    FormProgress.finalise_stale_incomplete(request.user, form)

    # Create a FormProgress instance if it doesn't yet exist
    form_progress = FormProgress.get_or_create_incomplete(request.user, form)

    # Figure out what page of the form the user is on
    page_number = form_progress.get_current_page_number()

    # Redirect the user to form_fill_page
    return redirect(
        "student_interface:form_fill_page",
        course_slug=course_slug,
        index=index,
        page_number=page_number,
    )


@login_required
def form_fill_page(request, course_slug, index, page_number):
    course = get_object_or_404(Course, slug=course_slug)
    form = get_form_for_index(course, index)
    all_pages = list(form.pages.all())
    total_pages = len(all_pages)
    if page_number < 1 or page_number > total_pages:
        raise Http404("No form page at this number.")
    form_page = all_pages[page_number - 1]

    # Get the latest incomplete form progress instance
    form_progress = FormProgress.get_latest_incomplete(user=request.user, form=form)

    # Get existing answers for questions on this page
    questions = [
        child
        for child in form_page.children()
        if hasattr(child, "question")  # It's a FormQuestion
    ]

    next_page_url = (
        reverse(
            "student_interface:form_fill_page",
            kwargs={
                "course_slug": course_slug,
                "index": index,
                "page_number": page_number + 1,
            },
        )
        if page_number < total_pages
        else None
    )

    if request.method == "POST":
        # No incomplete attempt to save into (e.g. it was finalised by a
        # submit-on-exit safety net, or the page was reached without starting).
        # Send the learner back to the form start screen rather than 500.
        if form_progress is None:
            return redirect(
                "student_interface:view_course_item",
                course_slug=course_slug,
                index=index,
            )

        # Process each question's answer
        form_progress.save_answers(questions, request.POST)

        if next_page_url:
            return redirect(next_page_url)

        # Mark form as completed and calculate scores
        form_progress.complete()

        return redirect(
            "student_interface:course_form_complete",
            course_slug=course_slug,
            index=index,
        )

    previous_page_url = (
        reverse(
            "student_interface:form_fill_page",
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
            "student_interface:view_course_item",
            course_slug=course_slug,
            index=index,
        )

    # Build a dictionary of existing answers keyed by question ID
    existing_answers = form_progress.existing_answers_dict(questions)

    # Determine the furthest page the user has progressed to
    furthest_page = form_progress.get_current_page_number()

    # Build list of all page objects with their URLs for navigation
    page_links = []
    for i in range(1, total_pages + 1):
        page_links.append(
            {
                "number": i,
                "title": all_pages[i - 1].title,
                "url": reverse(
                    "student_interface:form_fill_page",
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
        "student_interface:form_submit_and_exit",
        kwargs={"course_slug": course_slug, "index": index},
    )

    # URL for the save-and-exit link (used by the exit dialog)
    save_and_exit_url = reverse(
        "student_interface:view_course_item",
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
        **_player_chrome_context(request.user, course, form, index),
        "answered_count": answered_count,
        "answered_other_pages": answered_other_pages,
        "total_question_count": total_question_count,
        "submit_and_exit_url": submit_and_exit_url,
        "save_and_exit_url": save_and_exit_url,
    }

    response = render(request, "student_interface/course_form_page.html", context)
    # Runner pages must re-fetch on back-nav so the answered count is never stale.
    response["Cache-Control"] = "no-store"
    return response


@login_required
def course_form_complete(request, course_slug, index):
    course = get_object_or_404(Course, slug=course_slug)
    # Fetch viewable_items once and reuse it (it is not cached); the view also
    # needs the list length below for is_last_item.
    viewable_items = course.viewable_items()
    form = get_form_for_index(course, index, viewable_items=viewable_items)

    # Get the most recent completed form progress
    form_progress = (
        FormProgress.objects.filter(
            user=request.user, form=form, completed_time__isnull=False
        )
        .order_by("-completed_time")
        .first()
    )

    # Get incorrect answers if this is a quiz with show_incorrect enabled
    incorrect_answers = []
    if form_progress:
        incorrect_answers = form_progress.get_incorrect_quiz_answers()

    # Determine if this is a failed quiz
    is_failed_quiz = False
    if form_progress and form.strategy == FormStrategy.QUIZ:
        with contextlib.suppress(ValueError):
            is_failed_quiz = not form_progress.passed()

    # Only set for QUIZ forms; non-quiz forms do not have a numeric percentage.
    percentage = None
    if form_progress and form.strategy == FormStrategy.QUIZ:
        with contextlib.suppress(ValueError):
            percentage = form_progress.quiz_percentage()

    # Calculate next URL for continue button
    total_viewable_items = len(viewable_items)
    is_last_item = index >= total_viewable_items
    if is_last_item:
        # Last item - go to course finish page
        next_url = reverse(
            "student_interface:course_finish", kwargs={"course_slug": course_slug}
        )
    else:
        # Not last item - go to next item
        next_url = reverse(
            "student_interface:view_course_item",
            kwargs={"course_slug": course_slug, "index": index + 1},
        )

    # Calculate retry URL
    retry_url = reverse(
        "student_interface:form_start",
        kwargs={"course_slug": course_slug, "index": index},
    )

    context = {
        "course": course,
        "form": form,
        "form_progress": form_progress,
        "show_scores": True,
        "scores": form_progress.scores if form_progress else None,
        "incorrect_answers": incorrect_answers,
        "is_failed_quiz": is_failed_quiz,
        "next_url": next_url,
        "retry_url": retry_url,
        # Player chrome (outline panel + breadcrumb).
        **_player_chrome_context(request.user, course, form, index),
    }

    # Only include percentage in context for QUIZ forms (avoids None littering the context
    # for non-quiz forms; template branches on form.strategy == "QUIZ" already).
    if percentage is not None:
        context["percentage"] = percentage

    return render(request, "student_interface/course_form_complete.html", context)


@login_required
def course_finish(request, course_slug):
    """Mark the course progress as complete for this user and render a completion page."""

    course = get_object_or_404(Course, slug=course_slug)

    # Get existing course progress (should already exist)
    course_progress = get_object_or_404(
        CourseProgress, user=request.user, course=course
    )

    # Mark as complete if not already
    if not course_progress.completed_time:
        course_progress.completed_time = timezone.now()
        course_progress.save()

        from freedom_ls.webhooks.events import fire_webhook_event

        fire_webhook_event(
            "course.completed",
            {
                "user_id": request.user.pk,
                "user_email": request.user.email,
                "course_id": str(course.id),
                "course_title": course.title,
                "completed_time": course_progress.completed_time.isoformat(),
            },
        )

    context = {
        "course": course,
        "course_progress": course_progress,
        # Outline panel for the completion page (no single current item).
        # can_access_content=True: course_finish is only reachable after completing
        # a course — the learner has had content access throughout.
        "course_index": get_course_index(
            user=request.user, course=course, can_access_content=True
        ),
    }

    return render(request, "student_interface/course_finish.html", context)


@login_required
@require_POST
def form_submit_and_exit(request, course_slug: str, index: int):
    """POST-only endpoint: finalise the learner's current attempt and redirect to results.

    Used by the exit dialog's "Leave and submit" action on submit-on-exit forms.
    Calling complete() is idempotent so double-submits are safe.
    """
    course = get_object_or_404(Course, slug=course_slug)
    form = get_form_for_index(course, index)

    # The exit dialog only renders this POST for submit-on-exit forms, but the
    # endpoint is reachable directly. Save-on-exit forms promise the attempt is
    # saved (resumable), not scored, so never finalise one here — send the
    # learner back to the form start screen instead.
    if not form.submit_on_exit:
        return redirect(
            "student_interface:view_course_item",
            course_slug=course_slug,
            index=index,
        )

    form_progress = FormProgress.get_latest_incomplete(user=request.user, form=form)
    if form_progress is not None:
        form_progress.complete()  # idempotent

    return redirect(
        "student_interface:course_form_complete",
        course_slug=course_slug,
        index=index,
    )


if TYPE_CHECKING:
    from freedom_ls.accounts.models import User


def _is_content_item_completed(content_item: Topic | Form, user: User) -> bool:
    """Check if a content item has been completed by the user."""
    if isinstance(content_item, Topic):
        return TopicProgress.objects.filter(
            user=user, topic=content_item, complete_time__isnull=False
        ).exists()
    else:
        return FormProgress.objects.filter(
            user=user, form=content_item, completed_time__isnull=False
        ).exists()
