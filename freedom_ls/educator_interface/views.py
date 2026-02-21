from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.db.models import Count, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.contrib.contenttypes.models import ContentType as DjangoContentType

from freedom_ls.student_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortDeadline,
    CohortMembership,
    Student,
    StudentCohortDeadlineOverride,
    StudentCourseRegistration,
)
from freedom_ls.content_engine.models import Course, CoursePart, Topic, Form
from freedom_ls.student_progress.models import (
    CourseProgress,
    FormProgress,
    TopicProgress,
)
from django.utils import timezone as tz

from guardian.shortcuts import get_objects_for_user


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


class CohortCourseProgressPanel(Panel):
    title = "Course Progress"

    COLUMN_PAGE_SIZE = 15
    STUDENT_PAGE_SIZE = 20

    def get_content(self, request, base_url: str = "", panel_name: str = "") -> str:
        cohort = self.instance

        # 1. Course selection
        registrations = list(
            CohortCourseRegistration.objects.filter(cohort=cohort)
            .select_related("collection")
            .order_by("-is_active", "collection__title")
        )

        if not registrations:
            return render_to_string(
                "educator_interface/partials/course_progress_panel.html",
                {"empty_state": True},
                request=request,
            )

        # Determine selected registration
        selected_reg_pk = request.GET.get("registration")
        selected_reg = None
        if selected_reg_pk:
            selected_reg = next(
                (r for r in registrations if str(r.pk) == selected_reg_pk), None
            )
        if not selected_reg:
            # Default to first active, or first inactive
            active = [r for r in registrations if r.is_active]
            selected_reg = active[0] if active else registrations[0]

        course = selected_reg.collection

        # 2. Column pagination (course items)
        all_flat = course.children_flat()
        # Separate items from CourseParts and build part->children mapping
        items = []
        part_children_map: dict = {}  # CoursePart -> list of items
        current_part = None
        for child in all_flat:
            if isinstance(child, CoursePart):
                current_part = child
                part_children_map[child] = []
            else:
                items.append(child)
                if current_part is not None:
                    part_children_map[current_part].append(child)

        col_paginator = Paginator(items, self.COLUMN_PAGE_SIZE)
        col_page_num = request.GET.get("col_page", 1)
        col_page = col_paginator.get_page(col_page_num)
        visible_items = list(col_page.object_list)

        # Build visible part headers for the current column page
        visible_item_pks = {item.pk for item in visible_items}
        visible_parts = []
        for part, children in part_children_map.items():
            visible_children = [c for c in children if c.pk in visible_item_pks]
            if visible_children:
                visible_parts.append(
                    {
                        "part": part,
                        "span": len(visible_children),
                    }
                )

        # 3. Student pagination (rows)
        progress_subquery = Subquery(
            CourseProgress.objects.filter(
                user=OuterRef("student__user"),
                course=course,
            ).values("progress_percentage")[:1],
            output_field=IntegerField(),
        )

        memberships = (
            CohortMembership.objects.filter(cohort=cohort)
            .select_related("student__user")
            .annotate(
                progress=Coalesce(progress_subquery, Value(0)),
            )
            .order_by("progress", "student__user__email")
        )

        student_paginator = Paginator(memberships, self.STUDENT_PAGE_SIZE)
        student_page_num = request.GET.get("page", 1)
        student_page = student_paginator.get_page(student_page_num)

        # 4. Cell data fetching (Phase 2) — scoped to visible window
        visible_student_users = [m.student.user for m in student_page.object_list]
        visible_user_ids = [u.id for u in visible_student_users]

        visible_topic_ids = [
            item.id for item in visible_items if isinstance(item, Topic)
        ]
        visible_form_ids = [item.id for item in visible_items if isinstance(item, Form)]

        # Topic progress: keyed by (user_id, topic_id)
        topic_progress_map: dict = {}
        if visible_topic_ids:
            for tp in TopicProgress.objects.filter(
                user_id__in=visible_user_ids, topic_id__in=visible_topic_ids
            ).select_related("topic"):
                topic_progress_map[(tp.user_id, tp.topic_id)] = tp

        # Form progress: keyed by (user_id, form_id) -> latest completed + attempt count
        form_progress_map: dict = {}
        if visible_form_ids:
            for fp in (
                FormProgress.objects.filter(
                    user_id__in=visible_user_ids, form_id__in=visible_form_ids
                )
                .select_related("form")
                .order_by("-completed_time", "-start_time")
            ):
                key = (fp.user_id, fp.form_id)
                if key not in form_progress_map:
                    form_progress_map[key] = {
                        "latest": fp,
                        "completed_count": 0,
                    }
                if fp.completed_time is not None:
                    form_progress_map[key]["completed_count"] += 1

        # Cohort deadlines
        topic_ct = DjangoContentType.objects.get_for_model(Topic)
        form_ct = DjangoContentType.objects.get_for_model(Form)

        visible_item_ids = [item.id for item in visible_items]
        deadline_q = Q(
            content_type__isnull=True, object_id__isnull=True
        )  # course-level
        if visible_item_ids:
            deadline_q |= Q(
                content_type__in=[topic_ct, form_ct],
                object_id__in=visible_item_ids,
            )

        cohort_deadlines = list(
            CohortDeadline.objects.filter(
                cohort_course_registration=selected_reg,
            ).filter(deadline_q)
        )
        # Keyed by (content_type_id, object_id) or (None, None) for course-level
        deadline_map: dict = {}
        course_deadline = None
        for dl in cohort_deadlines:
            if dl.content_type_id is None:
                course_deadline = dl
            else:
                deadline_map[(dl.content_type_id, dl.object_id)] = dl

        # Student deadline overrides
        student_override_map: dict = {}  # (student_id, content_type_id, object_id) -> override
        if visible_user_ids:
            student_ids = [m.student_id for m in student_page.object_list]
            overrides = StudentCohortDeadlineOverride.objects.filter(
                cohort_course_registration=selected_reg,
                student_id__in=student_ids,
            ).filter(deadline_q)
            for ovr in overrides:
                student_override_map[
                    (ovr.student_id, ovr.content_type_id, ovr.object_id)
                ] = ovr

        # 5. Build cell data for template
        now = tz.now()
        rows = []
        for membership in student_page.object_list:
            student = membership.student
            user = student.user
            cells = []
            for item in visible_items:
                cell = {"item": item}
                item_ct = topic_ct if isinstance(item, Topic) else form_ct

                # Get deadline info
                item_deadline = deadline_map.get((item_ct.id, item.id))
                override = student_override_map.get((student.id, item_ct.id, item.id))
                effective_deadline = override or item_deadline
                cell["deadline"] = item_deadline
                cell["override"] = override
                cell["effective_deadline"] = effective_deadline

                if isinstance(item, Topic):
                    tp = topic_progress_map.get((user.id, item.id))
                    cell["progress"] = tp
                    cell["is_completed"] = tp and tp.complete_time is not None
                    cell["is_started"] = tp is not None
                    cell["completed_time"] = tp.complete_time if tp else None
                    cell["start_time"] = tp.start_time if tp else None
                elif isinstance(item, Form):
                    fp_data = form_progress_map.get((user.id, item.id))
                    if fp_data:
                        fp = fp_data["latest"]
                        cell["progress"] = fp
                        cell["is_completed"] = fp.completed_time is not None
                        cell["is_started"] = True
                        cell["completed_time"] = fp.completed_time
                        cell["start_time"] = fp.start_time
                        cell["completed_count"] = fp_data["completed_count"]
                        cell["is_quiz"] = item.strategy == "QUIZ"
                        if cell["is_completed"] and cell["is_quiz"] and fp.scores:
                            try:
                                cell["quiz_percentage"] = fp.quiz_percentage()
                                cell["passed"] = (
                                    fp.passed()
                                    if item.quiz_pass_percentage is not None
                                    else None
                                )
                            except (KeyError, ValueError):
                                cell["quiz_percentage"] = None
                                cell["passed"] = None
                    else:
                        cell["progress"] = None
                        cell["is_completed"] = False
                        cell["is_started"] = False
                        cell["completed_time"] = None
                        cell["start_time"] = None

                # Overdue check
                cell["is_overdue"] = False
                cell["is_hard_overdue"] = False
                if (
                    effective_deadline
                    and not cell["is_completed"]
                    and effective_deadline.deadline < now
                ):
                    cell["is_overdue"] = True
                    cell["is_hard_overdue"] = effective_deadline.is_hard_deadline

                cells.append(cell)

            name_parts = [p for p in (user.first_name, user.last_name) if p]
            display_name = " ".join(name_parts) if name_parts else user.email

            rows.append(
                {
                    "student": student,
                    "user": user,
                    "display_name": display_name,
                    "student_url": f"/educator/students/{student.pk}",
                    "progress": membership.progress,
                    "cells": cells,
                }
            )

        # Build header items with deadline info for the template
        header_items = []
        for item in visible_items:
            item_ct = topic_ct if isinstance(item, Topic) else form_ct
            item_deadline = deadline_map.get((item_ct.id, item.id))
            header_items.append({
                "item": item,
                "deadline": item_deadline,
            })

        context = {
            "empty_state": False,
            "registrations": registrations,
            "selected_reg": selected_reg,
            "course": course,
            "course_deadline": course_deadline,
            "visible_items": visible_items,
            "header_items": header_items,
            "visible_parts": visible_parts,
            "has_parts": bool(part_children_map),
            "col_page": col_page,
            "student_page": student_page,
            "rows": rows,
            "deadline_map": deadline_map,
            "topic_ct": topic_ct,
            "form_ct": form_ct,
            "base_url": base_url,
            "now": now,
        }

        return render_to_string(
            "educator_interface/partials/course_progress_panel.html",
            context,
            request=request,
        )

    def render(self, request, base_url: str = "", panel_name: str = "") -> str:
        is_htmx = request.headers.get("HX-Request") == "true"
        if is_htmx:
            return self.get_content(request, base_url=base_url, panel_name=panel_name)
        return super().render(request, base_url=base_url, panel_name=panel_name)


class CohortInstanceView(InstanceView):
    panels = {
        "details": CohortDetailsPanel,
        "course_progress": CohortCourseProgressPanel,
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
