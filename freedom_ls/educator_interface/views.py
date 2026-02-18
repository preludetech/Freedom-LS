from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.core.paginator import Paginator
from django.http import Http404

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


# TODO
# Data Tables
# sort
# pagination
# top level filters (searchable dropdown)
#   use HTMX to only reload that one panel
# Checkboxes and bulk actions (eg. Delete, add to cohort, remove from cohort)
# Export as csv
#
# instance edit
# instance, other actions (eg: send_email)


class Panel:
    def render(self, instance, request) -> str:
        raise NotImplementedError


class DataTable:
    """Abstract class used for rendering data tables"""

    page_size = 5

    def get_queryset(request):
        implement

    def get_columns():
        implement

    @classmethod
    def get_rows(klass, request, filters: dict | None = None):
        queryset = klass.get_queryset(request)
        if filters:
            queryset = queryset.filter(**filters)

        page_number = request.GET.get("page", 1)
        paginator = Paginator(queryset, klass.page_size)
        page_obj = paginator.get_page(page_number)

        return page_obj

    @classmethod
    def render(klass, request, filters: dict | None = None) -> str:
        context = {
            "columns": klass.get_columns(),
            "rows": klass.get_rows(request, filters=filters),
        }
        return render_to_string(
            "educator_interface/partials/list_view.html", context, request=request
        )


class DataTablePanel(Panel):
    data_table: type[DataTable]
    title: str = ""

    def get_filters(self, instance) -> dict:
        return {}

    def render(self, instance, request) -> str:
        parts = []
        if self.title:
            parts.append(f"<h2>{self.title}</h2>")
        parts.append(
            self.data_table.render(request, filters=self.get_filters(instance))
        )
        return "\n".join(parts)


class InstanceDetailsPanel(Panel):
    fields: list[str] = []

    def _resolve_field(self, instance: object, field_path: str) -> tuple[str, object]:
        """Resolve a dot-notation field path to (label, value).

        Supports paths like "user.email" by traversing related objects.
        """
        parts = field_path.split(".")
        obj = instance
        for part in parts[:-1]:
            obj = getattr(obj, part)
        field_name = parts[-1]
        field = obj._meta.get_field(field_name)
        label = field.verbose_name.title()
        value = getattr(obj, field_name)
        return label, value

    def render(self, instance, request) -> str:
        field_data = []
        for field_path in self.fields:
            label, value = self._resolve_field(instance, field_path)
            field_data.append({"label": label, "value": value})
        return render_to_string(
            "educator_interface/partials/instance_details_panel.html",
            {"fields": field_data},
            request=request,
        )


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
                "header": "First Name",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "user.first_name",
                "url_name": "educator_interface:interface",
                "url_path_template": "students/{pk}",
                # "sortable": True,
            },
            {
                "header": "Last Name",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "user.last_name",
                "url_name": "educator_interface:interface",
                "url_path_template": "students/{pk}",
                # "sortable": True,
            },
            {
                "header": "Email",
                "template": "cotton/data-table-cells/text.html",
                "attr": "user.email",
                # "sortable": True,
            },
            {
                "header": "Cohorts",
                "template": "educator_interface/data-table-cells/cohort_links.html",
                "relation_set": "cohortmembership_set.all",
                "link_object_attr": "cohort",
                "link_text_attr": "cohort.name",
            },
            {
                "header": "Registered Courses",
                "template": "educator_interface/data-table-cells/student_courses.html",
            },
        ]


class ListViewConfig:
    model = None
    instance_view = None
    list_view = None

    def __class_getitem__(cls, pk: str):
        instance = get_object_or_404(cls.model, pk=pk)
        return cls.instance_view(instance)

    @classmethod
    def render(cls, request) -> str:
        return cls.list_view.render(request)


class InstanceView:
    """Used for displaying specific instances. For example one User, Student, Etc"""

    panels = []

    def __init__(self, instance):
        self.instance = instance

    def render(self, request) -> str:
        rendered_panels = [
            panel().render(self.instance, request) for panel in self.panels
        ]
        title = f"<h1>{self.instance}</h1>"
        return title + "\n" + "\n".join(rendered_panels)


class StudentDetailsPanel(InstanceDetailsPanel):
    fields = [
        "user.first_name",
        "user.last_name",
        "user.email",
        "id_number",
        "date_of_birth",
        "cellphone",
    ]


class StudentCohortsPanel(DataTablePanel):
    title = "Cohorts"
    data_table = CohortDataTable

    def get_filters(self, instance) -> dict:
        return {"cohortmembership__student": instance}


class StudentInstanceView(InstanceView):
    panels = [StudentDetailsPanel, StudentCohortsPanel]


class CohortDetailsPanel(InstanceDetailsPanel):
    fields = ["name"]


class CohortCourseRegistrationDataTable(DataTable):
    def get_queryset(request):
        return CohortCourseRegistration.objects.select_related("collection").order_by(
            "collection__title"
        )

    def get_columns():
        return [
            {
                "header": "Course",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "collection.title",
                "url_name": "educator_interface:interface",
                "url_path_template": "courses/{collection.pk}",
            },
            {
                "header": "Active",
                "template": "cotton/data-table-cells/boolean.html",
                "attr": "is_active",
            },
            {
                "header": "Registered",
                "template": "cotton/data-table-cells/text.html",
                "attr": "registered_at",
            },
        ]


class CohortStudentsPanel(DataTablePanel):
    title = "Students"
    data_table = StudentDataTable

    def get_filters(self, instance) -> dict:
        return {"cohortmembership__cohort": instance}


class CourseRegistrationsPanel(DataTablePanel):
    title = "Course Registrations"
    data_table = CohortCourseRegistrationDataTable

    def get_filters(self, instance) -> dict:
        return {"cohort": instance}


class CohortInstanceView(InstanceView):
    panels = [
        CohortDetailsPanel,
        CourseRegistrationsPanel,
        CohortStudentsPanel,
    ]


class CohortConfig(ListViewConfig):
    url_name = "cohorts"
    menu_label = "Cohorts"
    model = Cohort
    list_view = CohortDataTable
    instance_view = CohortInstanceView


class StudentConfig(ListViewConfig):
    url_name = "students"
    menu_label = "Students"
    model = Student
    list_view = StudentDataTable
    instance_view = StudentInstanceView


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
                "url_path_template": "courses/{pk}",
            },
            {
                "header": "Active Students",
                "template": "cotton/data-table-cells/text.html",
                "attr": "total_student_count",
            },
            {
                "header": "Active Cohorts",
                "template": "cotton/data-table-cells/text.html",
                "attr": "cohort_count",
            },
            {
                "header": "Cohorts",
                "template": "educator_interface/data-table-cells/cohort_links.html",
                "relation_set": "cohort_registrations.all",
                "link_object_attr": "cohort",
                "link_text_attr": "cohort.name",
            },
        ]


class CourseDetailsPanel(InstanceDetailsPanel):
    fields = ["title", "category"]


class CourseCohortRegistrationDataTable(DataTable):
    def get_queryset(request):
        return CohortCourseRegistration.objects.select_related(
            "cohort", "collection"
        ).order_by("cohort__name")

    def get_columns():
        return [
            {
                "header": "Cohort",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "cohort.name",
                "url_name": "educator_interface:interface",
                "url_path_template": "cohorts/{cohort.pk}",
            },
            {
                "header": "Active",
                "template": "cotton/data-table-cells/boolean.html",
                "attr": "is_active",
            },
            {
                "header": "Registered",
                "template": "cotton/data-table-cells/text.html",
                "attr": "registered_at",
            },
        ]


class CourseCohortRegistrationsPanel(DataTablePanel):
    title = "Cohort Registrations"
    data_table = CourseCohortRegistrationDataTable

    def get_filters(self, instance) -> dict:
        return {"collection": instance}


class CourseStudentRegistrationDataTable(DataTable):
    def get_queryset(request):
        return StudentCourseRegistration.objects.select_related(
            "student__user", "collection"
        ).order_by("student__user__first_name", "student__user__last_name")

    def get_columns():
        return [
            {
                "header": "First Name",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "student.user.first_name",
                "url_name": "educator_interface:interface",
                "url_path_template": "students/{student.pk}",
            },
            {
                "header": "Last Name",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "student.user.last_name",
                "url_name": "educator_interface:interface",
                "url_path_template": "students/{student.pk}",
            },
            {
                "header": "Email",
                "template": "cotton/data-table-cells/text.html",
                "attr": "student.user.email",
            },
            {
                "header": "Active",
                "template": "cotton/data-table-cells/boolean.html",
                "attr": "is_active",
            },
            {
                "header": "Registered",
                "template": "cotton/data-table-cells/text.html",
                "attr": "registered_at",
            },
        ]


class CourseStudentRegistrationsPanel(DataTablePanel):
    title = "Student Registrations"
    data_table = CourseStudentRegistrationDataTable

    def get_filters(self, instance) -> dict:
        return {"collection": instance}


class CourseInstanceView(InstanceView):
    panels = [
        CourseDetailsPanel,
        CourseCohortRegistrationsPanel,
        CourseStudentRegistrationsPanel,
    ]


class CourseConfig(ListViewConfig):
    url_name = "courses"
    menu_label = "Courses"
    model = Course
    list_view = CourseDataTable
    instance_view = CourseInstanceView


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

    parts = [p for p in parts if p]

    if not parts:
        rendered_content = ""
        heading = ""
    else:
        current = interface_config[parts[0]]
        for part in parts[1:]:
            current = current[part]
        rendered_content = current.render(request)
        heading = current.menu_label if hasattr(current, "menu_label") else ""

    context = {
        "menu_items": menu_items,
        "content": rendered_content,
        "heading": heading,
    }

    return render(request, "educator_interface/interface.html", context)
