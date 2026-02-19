from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse

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
# top level filters (searchable dropdown)
#   use HTMX to only reload that one panel
# Checkboxes and bulk actions (eg. Delete, add to cohort, remove from cohort)
# Export as csv
#
# instance edit
# instance, other actions (eg: send_email)


class Panel:
    title: str = ""

    def __init__(self, instance: object):
        self.instance = instance

    def get_content(self, request, base_url: str = "", panel_name: str = "") -> str:
        raise NotImplementedError

    def render(self, request, base_url: str = "", panel_name: str = "") -> str:
        content = self.get_content(request, base_url=base_url, panel_name=panel_name)
        return render_to_string(
            "educator_interface/partials/panel_container.html",
            {"title": self.title, "content": content},
            request=request,
        )


class DataTable:
    """Abstract class used for rendering data tables"""

    page_size = 5
    search_fields: list[str] = []

    def get_queryset(request):
        implement

    def get_columns():
        implement

    @classmethod
    def _prepare_columns(klass) -> list[dict]:
        """Enrich columns: derive sort_field from text_attr/attr for sortable columns."""
        columns = klass.get_columns()
        for col in columns:
            if col.get("sortable") and "sort_field" not in col:
                attr = col.get("text_attr") or col.get("attr", "")
                col["sort_field"] = attr.replace(".", "__")
        return columns

    @classmethod
    def get_rows(klass, request, columns: list[dict], filters: dict | None = None):
        queryset = klass.get_queryset(request)
        if filters:
            queryset = queryset.filter(**filters)

        search_query = request.GET.get("search", "").strip()
        if search_query and klass.search_fields:
            search_filter = Q()
            for field in klass.search_fields:
                search_filter |= Q(**{f"{field}__icontains": search_query})
            queryset = queryset.filter(search_filter)

        sort_by = request.GET.get("sort", "")
        sort_order = request.GET.get("order", "asc")
        sortable_fields = {col["sort_field"] for col in columns if col.get("sortable")}
        if sort_by in sortable_fields:
            order_expr = f"-{sort_by}" if sort_order == "desc" else sort_by
            queryset = queryset.order_by(order_expr)

        page_number = request.GET.get("page", 1)
        paginator = Paginator(queryset, klass.page_size)
        page_obj = paginator.get_page(page_number)

        return page_obj

    @classmethod
    def render(
        klass,
        request,
        filters: dict | None = None,
        base_url: str = "",
        table_id: str = "data-table-container",
    ) -> str:
        columns = klass._prepare_columns()
        sort_by = request.GET.get("sort", "")
        sort_order = request.GET.get("order", "asc")
        search_query = request.GET.get("search", "").strip()
        page_obj = klass.get_rows(request, columns, filters=filters)
        context = {
            "columns": columns,
            "rows": page_obj,
            "page_obj": page_obj,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "base_url": base_url,
            "show_search": bool(klass.search_fields),
            "search_query": search_query,
            "table_id": table_id,
        }
        return render_to_string(
            "educator_interface/partials/list_view.html", context, request=request
        )


class DataTablePanel(Panel):
    data_table: type[DataTable]

    def get_filters(self) -> dict:
        return {}

    def get_content(self, request, base_url: str = "", panel_name: str = "") -> str:
        table_id = f"table-{panel_name}" if panel_name else "data-table-container"
        return self.data_table.render(
            request,
            filters=self.get_filters(),
            base_url=base_url,
            table_id=table_id,
        )

    def render(self, request, base_url: str = "", panel_name: str = "") -> str:
        is_htmx = request.headers.get("HX-Request") == "true"
        if is_htmx:
            return self.get_content(request, base_url=base_url, panel_name=panel_name)
        return super().render(request, base_url=base_url, panel_name=panel_name)


class InstanceDetailsPanel(Panel):
    title = "Details"
    fields: list[str] = []

    def _resolve_field(self, field_path: str) -> tuple[str, object]:
        """Resolve a dot-notation field path to (label, value).

        Supports paths like "user.email" by traversing related objects.
        """
        parts = field_path.split(".")
        obj = self.instance
        for part in parts[:-1]:
            obj = getattr(obj, part)
        field_name = parts[-1]
        field = obj._meta.get_field(field_name)
        label = field.verbose_name.title()
        value = getattr(obj, field_name)
        return label, value

    def get_content(self, request, base_url: str = "", panel_name: str = "") -> str:
        field_data = []
        for field_path in self.fields:
            label, value = self._resolve_field(field_path)
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
    search_fields = ["user__first_name", "user__last_name", "user__email"]

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
                "sortable": True,
            },
            {
                "header": "Last Name",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "user.last_name",
                "url_name": "educator_interface:interface",
                "url_path_template": "students/{pk}",
                "sortable": True,
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
    def render(cls, request, base_url: str = "") -> str:
        return cls.list_view.render(request, base_url=base_url)


class PanelGetter:
    """Subscriptable object that instantiates panels bound to an instance."""

    def __init__(self, panel_classes: dict[str, type[Panel]], instance: object):
        self._panel_classes = panel_classes
        self._instance = instance

    def __getitem__(self, name: str) -> Panel:
        if name not in self._panel_classes:
            raise Http404(f"Panel '{name}' not found")
        return self._panel_classes[name](self._instance)


class InstanceView:
    """Used for displaying specific instances. For example one User, Student, Etc"""

    panels: dict[str, type[Panel]] = {}

    def __init__(self, instance: object):
        self.instance = instance

    def panel_getter(self) -> PanelGetter:
        return PanelGetter(self.panels, self.instance)

    def render(self, request, base_url: str = "") -> str:
        getter = self.panel_getter()
        rendered_panels = []
        for name in self.panels:
            panel_url = f"{base_url.rstrip('/')}/__panels/{name}"
            rendered_panels.append(
                getter[name].render(request, base_url=panel_url, panel_name=name)
            )
        title = f"<h1>{self.instance}</h1>"
        panels_html = '<div class="space-y-6">' + "\n".join(rendered_panels) + "</div>"
        return title + "\n" + panels_html


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

    def get_filters(self) -> dict:
        return {"cohortmembership__student": self.instance}


class StudentInstanceView(InstanceView):
    panels = {
        "details": StudentDetailsPanel,
        "cohorts": StudentCohortsPanel,
    }


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

    def get_filters(self) -> dict:
        return {"cohortmembership__cohort": self.instance}


class CourseRegistrationsPanel(DataTablePanel):
    title = "Course Registrations"
    data_table = CohortCourseRegistrationDataTable

    def get_filters(self) -> dict:
        return {"cohort": self.instance}


class CohortInstanceView(InstanceView):
    panels = {
        "details": CohortDetailsPanel,
        "courses": CourseRegistrationsPanel,
        "students": CohortStudentsPanel,
    }


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

    def get_filters(self) -> dict:
        return {"collection": self.instance}


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

    def get_filters(self) -> dict:
        return {"collection": self.instance}


class CourseInstanceView(InstanceView):
    panels = {
        "details": CourseDetailsPanel,
        "cohorts": CourseCohortRegistrationsPanel,
        "students": CourseStudentRegistrationsPanel,
    }


class CourseConfig(ListViewConfig):
    url_name = "courses"
    menu_label = "Courses"
    model = Course
    list_view = CourseDataTable
    instance_view = CourseInstanceView


interface_config = {
    config.url_name: config for config in [CohortConfig, StudentConfig, CourseConfig]
}


def _resolve_path(parts: list[str]) -> object:
    """Walk the interface config tree according to URL path parts.

    Special segments like __panels resolve to the corresponding attribute
    on the current object, allowing further traversal.
    """
    current = interface_config[parts[0]]
    for part in parts[1:]:
        if part == "__panels":
            current = (
                current.panel_getter()
            )  # panel_getter.__getitem__ instantiates the panel and returns it
        else:
            current = current[part]

    return current


def interface(request, path_string: str = ""):
    parts = [p for p in path_string.split("/") if p]
    is_htmx = request.headers.get("HX-Request") == "true"
    base_url = request.path

    if not parts:
        rendered_content = ""
        heading = ""
    else:
        current = _resolve_path(parts)

        if isinstance(current, Panel):
            return HttpResponse(current.render(request, base_url=base_url))

        rendered_content = current.render(request, base_url=base_url)

        if is_htmx:
            return HttpResponse(rendered_content)

        heading = current.menu_label if hasattr(current, "menu_label") else ""

    menu_items = [
        {
            "label": conf.menu_label,
            "url": reverse(
                "educator_interface:interface", kwargs={"path_string": conf.url_name}
            ),
        }
        for conf in interface_config.values()
    ]

    context = {
        "menu_items": menu_items,
        "content": rendered_content,
        "heading": heading,
    }

    return render(request, "educator_interface/interface.html", context)
