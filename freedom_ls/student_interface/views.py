from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from freedom_ls.content_engine.models import (
    Course,
    CoursePart,
    Form,
    FormStrategy,
    Topic,
)
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
from freedom_ls.student_progress.xapi_events import (
    track_course_progressed,
    track_topic_completed,
)

from .utils import (
    form_start_page_buttons,
    get_all_courses,
    get_completed_courses,
    get_course_index,
    get_current_courses,
    get_is_registered,
    get_recommended_courses,
)
from .xapi_events import (
    track_course_registered,
    track_form_attempted,
    track_form_completed,
    track_question_answered,
    track_topic_viewed,
)


def home(request):
    """Home page with list of available courses."""
    # from django.contrib import messages

    # messages.add_message(request, messages.SUCCESS, "whoop whoop")
    return render(request, "student_interface/home.html")


def all_courses(request):
    """Page listing all available courses."""
    courses = list(get_all_courses())

    # Annotate started courses with progress_percentage
    current = get_current_courses(request.user)
    progress_by_id = {c.id: getattr(c, "progress_percentage", 0) for c in current}
    for course in courses:
        if course.id in progress_by_id:
            setattr(course, "progress_percentage", progress_by_id[course.id])  # noqa: B010

    return render(
        request,
        "student_interface/all_courses.html",
        {"all_courses": courses},
    )


def course_home(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)

    children = get_course_index(user=request.user, course=course)
    is_registered = get_is_registered(user=request.user, course=course)

    # Get course progress if user is authenticated
    course_progress = None
    if request.user.is_authenticated:
        course_progress = CourseProgress.objects.filter(
            user=request.user, course=course
        ).first()

    return render(
        request,
        "student_interface/course_home.html",
        {
            "course": course,
            "children": children,
            "is_registered": is_registered,
            "course_progress": course_progress,
        },
    )


def partial_course_toc(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)

    children = get_course_index(user=request.user, course=course)
    is_registered = get_is_registered(user=request.user, course=course)

    return render(
        request,
        "student_interface/partials/course_minimal_toc.html#course-children",
        {"course": course, "children": children, "is_registered": is_registered},
    )


def partial_list_courses(request):
    """Return a partial HTML section listing all available courses."""
    registered_courses = get_current_courses(request.user)
    completed_courses = get_completed_courses(request.user)
    recommended_courses = get_recommended_courses(request.user)

    context = {
        "registered_courses": registered_courses,
        "completed_courses": completed_courses,
        "recommended_courses": recommended_courses,
    }

    return render(request, "student_interface/partials/course_list.html", context)


@login_required
def register_for_course(request, course_slug):
    """Register the current user for a course."""

    course = get_object_or_404(Course, slug=course_slug)

    # Create the course registration directly with user
    registration, _created = UserCourseRegistration.objects.get_or_create(
        user=request.user,
        collection=course,
        defaults={"is_active": True},
    )

    # Delete any existing RecommendedCourse for this user and course
    RecommendedCourse.objects.filter(user=request.user, collection=course).delete()

    track_course_registered(
        request.user,
        course,
        request=request,
        registered_by="self",
        registration=registration,
    )

    # Redirect back to the course home page
    return redirect("student_interface:course_home", course_slug=course_slug)


@login_required
def view_course_item(request, course_slug, index):
    course = get_object_or_404(Course, slug=course_slug)
    children = course.children_flat()
    current_item = children[index - 1]

    # Check if item is locked by a hard deadline
    if (
        config.DEADLINES_ACTIVE
        and request.user.is_authenticated
        and not isinstance(current_item, CoursePart)
    ):
        is_completed = _is_content_item_completed(current_item, request.user)
        if is_item_locked_by_deadline(
            request.user, course, current_item, is_completed=is_completed
        ):
            return redirect("student_interface:course_home", course_slug=course_slug)

    total_children = len(children)

    # Update or create course progress to track last accessed time
    if request.user.is_authenticated:
        course_progress, _ = CourseProgress.objects.get_or_create(
            user=request.user, course=course
        )
        course_progress.save()  # This updates last_accessed_time via auto_now

    # Calculate navigation URLs
    next_url = None
    is_last_item = index >= total_children
    if not is_last_item:
        next_url = reverse(
            "student_interface:view_course_item",
            kwargs={"course_slug": course_slug, "index": index + 1},
        )

    previous_url = None
    if index > 1:
        previous_url = reverse(
            "student_interface:view_course_item",
            kwargs={"course_slug": course_slug, "index": index - 1},
        )

    if isinstance(current_item, Topic):
        return view_topic(
            request,
            topic=current_item,
            course=course,
            next_url=next_url,
            previous_url=previous_url,
            is_last_item=is_last_item,
        )

    if isinstance(current_item, Form):
        return view_form(
            request,
            form=current_item,
            course=course,
            index=index,
            is_last_item=is_last_item,
            next_url=next_url,
        )

    # Handle CoursePart by redirecting to the next item (first child of the part)
    if isinstance(current_item, CoursePart):
        # CourseParts are not directly viewable, redirect to next item
        if next_url:
            return redirect(next_url)
        else:
            # If this is the last item, go to course home
            return redirect("student_interface:course_home", course_slug=course.slug)


def view_topic(request, topic, course, next_url, previous_url, is_last_item=False):
    topic_progress, created = TopicProgress.objects.get_or_create(
        user=request.user, topic=topic
    )
    if not created:
        topic_progress.save()

    if request.method == "POST" and "mark_complete" in request.POST:
        topic_progress.complete_time = timezone.now()
        topic_progress.save()

        # Emit (COMPLETED, Topic) then (PROGRESSED, Course) chained off it.
        # The PROGRESSED event carries the COMPLETED event's id as its
        # trigger_event_id — domain-app wrappers handle the composition.
        completed_event = track_topic_completed(
            request.user,
            topic,
            request=request,
            completion_source="manual",
        )
        if completed_event is not None and course is not None:
            metrics = _course_progress_metrics(request.user, course)
            track_course_progressed(
                request.user,
                course,
                trigger_event=completed_event,
                request=request,
                **metrics,
            )

        if next_url:
            return redirect(next_url)
        else:
            # If no next_url (last item), redirect to course finish page
            return redirect("student_interface:course_finish", course_slug=course.slug)

    # Check if the course is already complete
    is_course_complete = False
    course_progress = CourseProgress.objects.filter(
        user=request.user, course=course
    ).first()
    if course_progress:
        is_course_complete = course_progress.completed_time is not None

    context = {
        "course": course,
        "topic": topic,
        "is_complete": topic_progress.complete_time is not None,
        "next_url": next_url,
        "previous_url": previous_url,
        "is_last_item": is_last_item,
        "is_course_complete": is_course_complete,
    }
    # Track one VIEWED event per render — per spec §"(VIEWED, Topic)".
    if request.user.is_authenticated:
        track_topic_viewed(
            request.user,
            topic,
            course=course,
            request=request,
            referrer=request.META.get("HTTP_REFERER"),
        )
    return render(request, "student_interface/course_topic.html", context)


def view_form(request, form, course, index, is_last_item=False, next_url=None):
    """Show the front page of the form"""

    # Try to get existing incomplete form progress (don't create if it doesn't exist)
    incomplete_form_progress = FormProgress.get_latest_incomplete(
        user=request.user, form=form
    )

    page_number = None
    if incomplete_form_progress:
        page_number = incomplete_form_progress.get_current_page_number()

    # Get all completed form submissions for this user and form
    completed_form_progress = FormProgress.objects.filter(
        user=request.user, form=form, completed_time__isnull=False
    ).order_by("-completed_time")

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
    }

    return render(request, "student_interface/course_form.html", context)


@login_required
def form_start(request, course_slug, index):
    """Start or resume a form for the current user."""

    course = get_object_or_404(Course, slug=course_slug)
    children = course.children_flat()
    form = children[index - 1]

    # Create a FormProgress instance if it doesn't yet exist
    form_progress, was_created = _get_or_create_form_progress_with_flag(
        request.user, form
    )

    # Figure out what page of the form the user is on
    page_number = form_progress.get_current_page_number()

    # Track one ATTEMPTED event when this is a new attempt.
    if was_created:
        attempt_number = FormProgress.objects.filter(
            user=request.user, form=form
        ).count()
        track_form_attempted(
            request.user,
            form,
            request=request,
            attempt_number=attempt_number,
        )

    # Redirect the user to form_fill_page
    return redirect(
        "student_interface:form_fill_page",
        course_slug=course_slug,
        index=index,
        page_number=page_number,
    )


def _get_or_create_form_progress_with_flag(
    user: User, form: Form
) -> tuple[FormProgress, bool]:
    """Thin wrapper over FormProgress that also reports whether a new row
    was created — needed so we emit ATTEMPTED exactly once per attempt.
    """
    existing = FormProgress.get_latest_incomplete(user=user, form=form)
    if existing is not None:
        return existing, False
    progress = FormProgress.objects.create(user=user, form=form)
    return progress, True


@login_required
def form_fill_page(request, course_slug, index, page_number):
    course = get_object_or_404(Course, slug=course_slug)
    children = course.children_flat()
    form = children[index - 1]
    all_pages = list(form.pages.all())
    total_pages = len(all_pages)
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
        # Snapshot previous answers before overwrite so we can compute
        # `changed_answer` for each ANSWERED event.
        previous_answers = form_progress.existing_answers_dict(questions)

        # Process each question's answer
        form_progress.save_answers(questions, request.POST)

        # Count attempts once per request — the value is constant across
        # the question loop and the subsequent COMPLETED emission.
        attempt_number = FormProgress.objects.filter(
            user=request.user, form=form
        ).count()

        # Emit one ANSWERED event per question that was on this page.
        for question in questions:
            posted_answer = request.POST.get(str(question.id)) or request.POST.get(
                f"question_{question.id}"
            )
            previous = previous_answers.get(question.id) if previous_answers else None
            track_question_answered(
                request.user,
                question,
                form_attempt_id=form_progress.id,
                attempt_number=attempt_number,
                response=posted_answer if posted_answer is not None else "",
                # TODO: capture real answer-duration once the form-fill UI
                # tracks per-question timing. PT0S is the xAPI-valid
                # placeholder until then.
                duration="PT0S",
                # Treat only a truly-missing prior answer as "no change"; a
                # falsy stored value (e.g. "0" or "") is still a real answer.
                changed_answer=previous is not None and previous != posted_answer,
                request=request,
            )

        if next_page_url:
            return redirect(next_page_url)

        # Mark form as completed and calculate scores
        form_progress.complete()

        # Emit COMPLETED Form once the whole form is submitted.
        scores = getattr(form_progress, "scores", {}) or {}
        try:
            passed = form_progress.passed()
        except (ValueError, AttributeError):
            passed = None
        completed_event = track_form_completed(
            request.user,
            form,
            request=request,
            success=passed,
            score_raw=scores.get("raw") if isinstance(scores, dict) else None,
            score_max=scores.get("max") if isinstance(scores, dict) else None,
            score_scaled=scores.get("scaled") if isinstance(scores, dict) else None,
            # TODO: capture real form-fill duration once the form-fill UI
            # tracks per-attempt timing. PT0S is the xAPI-valid placeholder.
            duration="PT0S",
            attempt_number=attempt_number,
            pass_threshold=(
                float(form.quiz_pass_percentage) / 100
                if getattr(form, "quiz_pass_percentage", None) is not None
                else None
            ),
            # TODO: aggregate ``changed_answer`` across the attempt's
            # ANSWERED events and surface the total here. Hardcoded to 0
            # until per-attempt change accounting lands.
            answers_changed=0,
            timed_out=False,
        )
        # Chain PROGRESSED Course off the COMPLETED Form event, same
        # pattern as the topic-mark-complete branch.
        if completed_event is not None and course is not None:
            metrics = _course_progress_metrics(request.user, course)
            track_course_progressed(
                request.user,
                course,
                trigger_event=completed_event,
                request=request,
                **metrics,
            )

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
    }

    return render(request, "student_interface/course_form_page.html", context)


@login_required
def course_form_complete(request, course_slug, index):
    course = get_object_or_404(Course, slug=course_slug)
    children = course.children_flat()
    form = children[index - 1]

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

    # Calculate next URL for continue button
    total_children = len(children)
    is_last_item = index >= total_children
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
    }

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
    }

    return render(request, "student_interface/course_finish.html", context)


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


def _course_progress_metrics(user, course) -> dict:
    """Compute the per-course progress metrics used by the PROGRESSED event.

    Counts topic / form completions against totals in the course's flat
    children. Not exhaustive (doesn't cover nested structures beyond
    children_flat) but matches how completion propagation is calculated
    today.
    """
    children = course.children_flat()
    topics = [c for c in children if isinstance(c, Topic)]
    forms = [c for c in children if isinstance(c, Form)]
    topics_total = len(topics)
    forms_total = len(forms)

    completed_topic_ids = set(
        TopicProgress.objects.filter(
            user=user,
            topic__in=topics,
            complete_time__isnull=False,
        ).values_list("topic_id", flat=True)
    )
    completed_form_ids = set(
        FormProgress.objects.filter(
            user=user,
            form__in=forms,
            completed_time__isnull=False,
        ).values_list("form_id", flat=True)
    )

    topics_completed = len(completed_topic_ids)
    forms_completed = len(completed_form_ids)
    total = topics_total + forms_total
    completed = topics_completed + forms_completed
    scaled = float(completed) / total if total else 0.0
    return {
        "completion": scaled >= 1.0,
        "progress_scaled": scaled,
        "progress_topics_completed": topics_completed,
        "progress_topics_total": topics_total,
        "progress_forms_completed": forms_completed,
        "progress_forms_total": forms_total,
    }
