from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Q
from django.http import HttpRequest
from django.core.paginator import Paginator
from django.urls import reverse
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

    columns = [
        {
            "header": "Cohort Name",
            "template": "cotton/data-table-cells/link.html",
            "text_attr": "name",
            "url_name": "educator_interface:cohort_detail",
            "url_param": "pk",
        },
        {
            "header": "Active Students",
            "template": "cotton/data-table-cells/text.html",
            "attr": "student_count",
        },
        {
            "header": "Registered Courses",
            "template": "educator_interface/data-table-cells/cohort_courses.html",
        },
    ]

    return render(
        request,
        "educator_interface/cohorts_list.html",
        {"cohorts": cohorts, "columns": columns},
    )


def get_student_data_table_context(request):
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

    # Handle search
    search_query = request.GET.get("search", "").strip()
    if search_query:
        students = students.filter(
            Q(user__first_name__icontains=search_query)
            | Q(user__last_name__icontains=search_query)
            | Q(user__email__icontains=search_query)
        )

    # Handle sorting
    sort_by = request.GET.get("sort", "")
    sort_order = request.GET.get("order", "asc")

    # Define sort field mappings
    sort_fields = {
        "name": ["user__first_name", "user__last_name"],
        "email": ["user__email"],
    }

    # Apply sorting if a valid sort field is provided
    if sort_by in sort_fields:
        order_fields = sort_fields[sort_by]
        if sort_order == "desc":
            order_fields = [f"-{field}" for field in order_fields]
        students = students.order_by(*order_fields)
    else:
        # Default ordering
        students = students.order_by("user__first_name", "user__last_name")
        sort_by = ""
        sort_order = "asc"

    # Pagination
    page_number = request.GET.get("page", 1)
    paginator = Paginator(students, 15)
    page_obj = paginator.get_page(page_number)

    columns = [
        {
            "header": "Name",
            "template": "cotton/data-table-cells/text.html",
            "attr": "__str__",
            "sortable": True,
            "sort_field": "name",
        },
        {
            "header": "Email",
            "template": "cotton/data-table-cells/text.html",
            "attr": "user.email",
            "sortable": True,
            "sort_field": "email",
        },
        {
            "header": "Cohorts",
            "template": "educator_interface/data-table-cells/student_cohorts.html",
        },
        {
            "header": "Registered Courses",
            "template": "educator_interface/data-table-cells/student_courses.html",
        },
    ]

    return {
        "rows": page_obj,
        "columns": columns,
        "page_obj": page_obj,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "base_url": reverse("educator_interface:partial_students_table"),
        "show_search": True,
        "search_query": search_query,
    }


def students_list(request: HttpRequest):
    """List all students the user has permission to view."""
    return render(request, "educator_interface/students_list.html")


def partial_students_table(request: HttpRequest):
    """Render the students data table (for HTMX requests)."""
    context = get_student_data_table_context(request)
    return render(
        request,
        "educator_interface/partials/students_table.html",
        context,
    )


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

    columns = [
        {
            "header": "Title",
            "template": "cotton/data-table-cells/text.html",
            "attr": "title",
        },
        {
            "header": "Students",
            "template": "cotton/data-table-cells/text.html",
            "attr": "total_student_count",
        },
        {
            "header": "Cohorts",
            "template": "cotton/data-table-cells/text.html",
            "attr": "cohort_count",
        },
    ]

    return render(
        request,
        "educator_interface/course_list.html",
        {"courses": courses, "columns": columns},
    )


def cohort_detail(request: HttpRequest, cohort_id: str):
    """Display details for a specific cohort."""
    cohort = get_object_or_404(Cohort, pk=cohort_id)
    return render(request, "educator_interface/cohort_detail.html", {"cohort": cohort})
