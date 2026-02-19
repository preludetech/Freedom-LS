from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils import timezone
from freedom_ls.content_engine.models import (
    Topic,
    Form,
    Course,
    CoursePart,
    FormStrategy,
)
from freedom_ls.student_progress.models import (
    FormProgress,
    TopicProgress,
    CourseProgress,
)
from freedom_ls.student_management.models import Student, StudentCourseRegistration
from freedom_ls.student_management.models import RecommendedCourse
from .utils import (
    get_course_index,
    get_is_registered,
    form_start_page_buttons,
    get_all_courses,
    get_completed_courses,
    get_current_courses,
    get_recommended_courses,
    _get_student,
)
from freedom_ls.student_management.deadline_utils import is_item_locked


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
    progress_by_id = {c.id: c.progress_percentage for c in current}
    for course in courses:
        if course.id in progress_by_id:
            course.progress_percentage = progress_by_id[course.id]

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
        try:
            course_progress = CourseProgress.objects.get(
                user=request.user, course=course
            )
        except CourseProgress.DoesNotExist:
            pass

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
        "student_interface/partials/course_minimal_toc.html",
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

    # Get or create Student instance for this user
    student, _ = Student.objects.get_or_create(user=request.user)

    # Create the course registration
    StudentCourseRegistration.objects.get_or_create(
        student=student,
        collection=course,
        defaults={"is_active": True},
    )

    # Delete any existing RecommendedCourse for this user and course
    RecommendedCourse.objects.filter(user=request.user, collection=course).delete()

    # Redirect back to the course home page
    return redirect("student_interface:course_home", course_slug=course_slug)


@login_required
def view_course_item(request, course_slug, index):
    course = get_object_or_404(Course, slug=course_slug)
    children = course.children_flat()
    current_item = children[index - 1]

    # Check if item is locked by a hard deadline
    student = _get_student(request.user)
    if student and not isinstance(current_item, CoursePart):
        is_completed = _is_content_item_completed(current_item, request.user)
        if is_item_locked(student, course, current_item, is_completed=is_completed):
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

        if next_url:
            return redirect(next_url)
        else:
            # If no next_url (last item), redirect to course finish page
            return redirect("student_interface:course_finish", course_slug=course.slug)

    # Check if the course is already complete
    is_course_complete = False
    try:
        course_progress = CourseProgress.objects.get(user=request.user, course=course)
        is_course_complete = course_progress.completed_time is not None
    except CourseProgress.DoesNotExist:
        pass

    context = {
        "course": course,
        "topic": topic,
        "is_complete": topic_progress.complete_time is not None,
        "next_url": next_url,
        "previous_url": previous_url,
        "is_last_item": is_last_item,
        "is_course_complete": is_course_complete,
    }
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
        try:
            is_failed_quiz = not form_progress.passed()
        except ValueError:
            pass

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

    context = {
        "course": course,
        "course_progress": course_progress,
    }

    return render(request, "student_interface/course_finish.html", context)


def _is_content_item_completed(content_item: Topic | Form, user) -> bool:
    """Check if a content item has been completed by the user."""
    if isinstance(content_item, Topic):
        return TopicProgress.objects.filter(
            user=user, topic=content_item, complete_time__isnull=False
        ).exists()
    elif isinstance(content_item, Form):
        return FormProgress.objects.filter(
            user=user, form=content_item, completed_time__isnull=False
        ).exists()
    return False
