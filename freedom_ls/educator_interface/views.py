from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.core.paginator import Paginator

from freedom_ls.student_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Student,
    StudentCourseRegistration,
)
from freedom_ls.content_engine.models import Course, CoursePart, Topic, Form


from guardian.shortcuts import get_objects_for_user
from django.db.models import Count, Q


class DataTable:
    """Abstract class used for rendering data tables"""

    page_size = 15

    def get_queryset(request):
        implement

    def get_columns():
        implement

    @classmethod
    def get_rows(klass, request):
        queryset = klass.get_queryset(request)

        page_number = request.GET.get("page", 1)
        paginator = Paginator(queryset, klass.page_size)
        page_obj = paginator.get_page(page_number)

        return page_obj


class CohortDataTable(DataTable):
    def get_queryset(request):
        return (
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

    def get_columns():
        return [
            {
                "header": "Cohort Name",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "name",
                "url_name": "educator_interface:interface",
                "url_path_template": "cohorts/{pk}",
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


class StudentDataTable(DataTable):
    def get_queryset(request):
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
        return (
            (students_with_direct_access | students_from_cohorts)
            .distinct()
            .select_related("user")
            .prefetch_related(
                "cohortmembership_set__cohort",
                "course_registrations__collection",
            )
            .order_by("user__first_name", "user__last_name")
        )

    def get_columns():
        return [
            {
                "header": "Name",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "__str__",
                "url_name": "educator_interface:interface",
                "url_path_template": "students/{pk}",
            },
            {
                "header": "Email",
                "template": "cotton/data-table-cells/text.html",
                "attr": "user.email",
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


class CohortConfig:
    url_name = "cohorts"
    menu_label = "Cohorts"
    list_view = CohortDataTable


class StudentConfig:
    url_name = "students"
    menu_label = "Students"
    list_view = StudentDataTable


class CourseDataTable(DataTable):
    def get_queryset(request):
        courses = (
            Course.objects.all()
            .annotate(
                cohort_count=Count(
                    "cohort_registrations",
                    filter=Q(cohort_registrations__is_active=True),
                    distinct=True,
                ),
                direct_student_count=Count(
                    "student_registrations",
                    filter=Q(student_registrations__is_active=True),
                    distinct=True,
                ),
            )
            .prefetch_related(
                "cohort_registrations__cohort__cohortmembership_set",
                "student_registrations",
            )
            .order_by("title")
        )

        # Calculate total unique active students (direct + through cohorts)
        for course in courses:
            cohort_student_ids = set()
            for cohort_reg in course.cohort_registrations.filter(is_active=True):
                cohort_student_ids.update(
                    cohort_reg.cohort.cohortmembership_set.values_list(
                        "student_id", flat=True
                    )
                )

            direct_student_ids = set(
                course.student_registrations.filter(is_active=True).values_list(
                    "student_id", flat=True
                )
            )

            course.total_student_count = len(cohort_student_ids | direct_student_ids)

        return courses

    def get_columns():
        return [
            {
                "header": "Title",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "title",
                "url_name": "educator_interface:interface",
                "url_path_template": "courses/{slug}",
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


class CourseConfig:
    url_name = "courses"
    menu_label = "Courses"
    list_view = CourseDataTable


interface_config = {
    config.url_name: config for config in [CohortConfig, StudentConfig, CourseConfig]
}


def interface(request, path_string: str = ""):
    parts = path_string.split("/")

    menu_items = [
        {
            "label": conf.menu_label,
            "url": reverse(
                "educator_interface:interface", kwargs={"path_string": conf.url_name}
            ),
        }
        for conf in interface_config.values()
    ]

    content_template = ""
    content_context: dict[str, object] = {}

    model_name = parts[0] if parts[0] else None

    if model_name and model_name in interface_config:
        config = interface_config[model_name]
        if hasattr(config, "list_view") and issubclass(config.list_view, DataTable):
            content_template = "educator_interface/partials/list_view.html"
            content_context = {
                "columns": config.list_view.get_columns(),
                "rows": config.list_view.get_rows(request),
            }
            rendered_content = render_to_string(
                content_template, content_context, request=request
            )
    else:
        rendered_content = ""

    heading = config.menu_label if model_name and model_name in interface_config else ""

    context = {
        "menu_items": menu_items,
        "content": rendered_content,
        "heading": heading,
    }

    return render(request, "educator_interface/interface.html", context)
