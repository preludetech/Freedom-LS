from django.shortcuts import render, get_object_or_404
from django.db.models import Count
from content_engine.models import Course


def home(request):
    """Educator interface home page."""
    return render(request, "educator_interface/home.html")


def course_student_progress(request, collection_slug):
    """Show student progress for a specific course."""
    course = get_object_or_404(Course, slug=collection_slug)
    return render(
        request,
        "educator_interface/course_student_progress.html",
        {"course": course},
    )


def course_list(request):
    """List all courses in alphabetical order."""
    courses = (
        Course.objects.all()
        .annotate(
            cohort_count=Count("cohort_registrations", distinct=True),
            direct_student_count=Count("student_registrations", distinct=True),
        )
        .order_by("title")
    )

    # Calculate total unique students (direct + through cohorts) for each course
    for course in courses:
        # Get students through cohort registrations
        cohort_student_ids = set()
        for cohort_reg in course.cohort_registrations.all():
            cohort_student_ids.update(
                cohort_reg.cohort.cohortmembership_set.values_list("student_id", flat=True)
            )

        # Get direct student registrations
        direct_student_ids = set(
            course.student_registrations.values_list("student_id", flat=True)
        )

        # Total unique students
        course.total_student_count = len(cohort_student_ids | direct_student_ids)

    return render(request, "educator_interface/course_list.html", {"courses": courses})
