from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils import timezone
from content_engine.models import Topic, Form, Course
from student_progress.models import FormProgress, TopicProgress
from student_management.models import Student, StudentCourseRegistration

from .utils import get_course_index, get_is_registered


def home(request):
    """Home page with list of available courses."""
    return render(request, "student_interface/home.html")


def course_home(request, collection_slug):
    from student_progress.models import CourseProgress

    course = get_object_or_404(Course, slug=collection_slug)

    children = get_course_index(course=course, request=request)
    is_registered = get_is_registered(request, course)

    # Get course progress if user is authenticated
    course_progress = None
    if request.user.is_authenticated:
        try:
            course_progress = CourseProgress.objects.get(user=request.user, course=course)
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


def partial_course_toc(request, collection_slug):
    course = get_object_or_404(Course, slug=collection_slug)

    children = get_course_index(course=course, request=request)
    is_registered = get_is_registered(request, course)

    return render(
        request,
        "student_interface/partials/course_minimal_toc.html",
        {"course": course, "children": children, "is_registered": is_registered},
    )


def partial_list_courses(request):
    """Return a partial HTML section listing all available courses."""
    from student_management.models import Student

    all_courses = Course.objects.all()
    registered_courses = []

    if request.user.is_authenticated:
        try:
            student = Student.objects.get(user=request.user)
            registered_courses = student.get_course_registrations()
        except Student.DoesNotExist:
            registered_courses = []

    context = {
        "all_courses": all_courses,
        "registered_courses": registered_courses,
    }

    return render(request, "student_interface/partials/course_list.html", context)


@login_required
def register_for_course(request, collection_slug):
    """Register the current user for a course."""
    from student_management.models import RecommendedCourse

    course = get_object_or_404(Course, slug=collection_slug)

    # Get or create Student instance for this user
    student, _ = Student.objects.get_or_create(user=request.user)

    # Create the course registration
    StudentCourseRegistration.objects.get_or_create(
        student=student,
        collection=course,
        defaults={"is_active": True},
    )

    # Delete any existing RecommendedCourse for this user and course
    RecommendedCourse.objects.filter(
        user=request.user,
        collection=course
    ).delete()

    # Redirect back to the course home page
    return redirect("student_interface:course_home", collection_slug=collection_slug)


def view_course_item(request, collection_slug, index):
    from student_progress.models import CourseProgress

    course = get_object_or_404(Course, slug=collection_slug)
    children = course.children()
    current_item = children[index - 1]

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
            kwargs={"collection_slug": collection_slug, "index": index + 1},
        )

    previous_url = None
    if index > 1:
        previous_url = reverse(
            "student_interface:view_course_item",
            kwargs={"collection_slug": collection_slug, "index": index - 1},
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
        return view_form(request, form=current_item, course=course, index=index)


def view_topic(request, topic, course, next_url, previous_url, is_last_item=False):
    from student_progress.models import CourseProgress

    topic_progress, created = TopicProgress.objects.get_or_create(
        user=request.user, topic=topic
    )
    if not created:
        topic_progress.save()

    if request.method == "POST" and "mark_complete" in request.POST:
        topic_progress.complete_time = timezone.now()
        topic_progress.save()

        # If this is the last item, mark the course as complete
        if is_last_item:
            course_progress, _ = CourseProgress.objects.get_or_create(
                user=request.user, course=course
            )
            if not course_progress.completed_time:
                course_progress.completed_time = timezone.now()
                course_progress.save()

        if next_url:
            return redirect(next_url)
        else:
            # If no next_url (last item), redirect to course home
            return redirect("student_interface:course_home", collection_slug=course.slug)

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


def view_form(request, form, course, index):
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

    context = {
        "course": course,
        "form": form,
        "incomplete_form_progress": incomplete_form_progress,
        "completed_form_progress": completed_form_progress,
        "index": index,
        "page_number": page_number,
    }

    return render(request, "student_interface/course_form.html", context)


@login_required
def form_start(request, collection_slug, index):
    """Start or resume a form for the current user."""

    course = get_object_or_404(Course, slug=collection_slug)
    children = course.children()
    form = children[index - 1]

    # Create a FormProgress instance if it doesn't yet exist
    form_progress = FormProgress.get_or_create_incomplete(request.user, form)

    # Figure out what page of the form the user is on
    page_number = form_progress.get_current_page_number()

    # Redirect the user to form_fill_page
    return redirect(
        "student_interface:form_fill_page",
        collection_slug=collection_slug,
        index=index,
        page_number=page_number,
    )


@login_required
def form_fill_page(request, collection_slug, index, page_number):
    course = get_object_or_404(Course, slug=collection_slug)
    children = course.children()
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
                "collection_slug": collection_slug,
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
            collection_slug=collection_slug,
            index=index,
        )

    previous_page_url = (
        reverse(
            "student_interface:form_fill_page",
            kwargs={
                "collection_slug": collection_slug,
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
                        "collection_slug": collection_slug,
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
def course_form_complete(request, collection_slug, index):
    course = get_object_or_404(Course, slug=collection_slug)
    children = course.children()
    form = children[index - 1]

    # Get the most recent completed form progress
    form_progress = (
        FormProgress.objects.filter(
            user=request.user, form=form, completed_time__isnull=False
        )
        .order_by("-completed_time")
        .first()
    )

    context = {
        "course": course,
        "form": form,
        "form_progress": form_progress,
        "show_scores": True,
        "scores": form_progress.scores if form_progress else None,
    }

    return render(request, "student_interface/course_form_complete.html", context)
