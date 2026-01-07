from django.shortcuts import render, get_object_or_404
from django.db.models import Count
from django.http import HttpRequest
from guardian.shortcuts import get_objects_for_user
from freedom_ls.content_engine.models import Course
from freedom_ls.student_management.models import Cohort, Student


def home(request: HttpRequest):
    """Educator interface home page."""
    # Get cohorts that the user has view permission for

    return render(request, "educator_interface/home.html")


def cohorts_list(request):
    cohorts = (
        get_objects_for_user(
            request.user,
            "view_cohort",
            klass=Cohort,
        )
        .annotate(
            student_count=Count("cohortmembership", distinct=True),
        )
        .prefetch_related("course_registrations__collection")
        .order_by("name")
    )

    return render(request, "educator_interface/cohorts_list.html", {"cohorts": cohorts})


def students_list(request):
    """List all students the user has permission to view."""
    # Get students with direct view permission
    students_with_direct_access = get_objects_for_user(
        request.user,
        "view_student",
        klass=Student,
    )

    # Get cohorts user has access to
    accessible_cohorts = get_objects_for_user(
        request.user,
        "view_cohort",
        klass=Cohort,
    )

    # Get students from accessible cohorts
    students_from_cohorts = Student.objects.filter(
        cohortmembership__cohort__in=accessible_cohorts
    )

    # Combine both querysets and remove duplicates
    students = (students_with_direct_access | students_from_cohorts).distinct()

    return render(request, "educator_interface/students_list.html", {"students": students})


def course_student_progress(request, course_slug):
    """Show student progress for a specific course."""
    course = get_object_or_404(Course, slug=course_slug)
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
                cohort_reg.cohort.cohortmembership_set.values_list(
                    "student_id", flat=True
                )
            )

        # Get direct student registrations
        direct_student_ids = set(
            course.student_registrations.values_list("student_id", flat=True)
        )

        # Total unique students
        course.total_student_count = len(cohort_student_ids | direct_student_ids)

    return render(request, "educator_interface/course_list.html", {"courses": courses})
