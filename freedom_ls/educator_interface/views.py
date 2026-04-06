from __future__ import annotations

from datetime import datetime
from typing import TypedDict
from uuid import UUID

from guardian.shortcuts import get_objects_for_user

from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.core.paginator import Page, Paginator
from django.db.models import (
    Count,
    F,
    IntegerField,
    Model,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone as tz

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course, CoursePart, Form, Topic
from freedom_ls.educator_interface.forms import CohortForm
from freedom_ls.panel_framework.actions import (
    CreateInstanceAction,
    DeleteAction,
    PanelAction,
)
from freedom_ls.panel_framework.panels import (
    DataTablePanel,
    InstanceDetailsPanel,
    Panel,
)
from freedom_ls.panel_framework.tables import DataTable
from freedom_ls.panel_framework.tabs import Tab
from freedom_ls.panel_framework.views import (
    InstanceView,
    ListViewConfig,
    panel_framework_view,
)
from freedom_ls.student_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortDeadline,
    CohortMembership,
    UserCohortDeadlineOverride,
    UserCourseRegistration,
)
from freedom_ls.student_progress.models import (
    CourseProgress,
    FormProgress,
    TopicProgress,
)


class FormProgressData(TypedDict):
    latest: FormProgress
    completed_count: int


# TODO
# Data Tables
# top level filters (searchable dropdown)
#   use HTMX to only reload that one panel
# Checkboxes and bulk actions (eg. Delete, add to cohort, remove from cohort)
# Export as csv
#
# instance edit
# instance, other actions (eg: send_email)


class CohortDataTable(DataTable):
    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
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

    @staticmethod
    def get_columns() -> list[dict[str, object]]:
        return [
            {
                "header": "Cohort Name",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "name",
                "url_name": "educator_interface:interface",
                "url_path_template": "cohorts/{pk}",
                "htmx_nav": True,
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


class UserDataTable(DataTable):
    search_fields = ["first_name", "last_name", "email"]

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        # Get cohorts user has access to
        accessible_cohorts = get_objects_for_user(
            request.user,
            "view_cohort",
            klass=Cohort,
        )

        # Get users from accessible cohorts
        return (
            User.objects.filter(cohortmembership__cohort__in=accessible_cohorts)
            .distinct()
            .prefetch_related(
                "cohortmembership_set__cohort",
                "usercourseregistration_set__collection",
            )
            .order_by("first_name", "last_name")
        )

    @staticmethod
    def get_columns() -> list[dict[str, object]]:
        return [
            {
                "header": "First Name",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "first_name",
                "url_name": "educator_interface:interface",
                "url_path_template": "users/{pk}",
                "sortable": True,
                "htmx_nav": True,
            },
            {
                "header": "Last Name",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "last_name",
                "url_name": "educator_interface:interface",
                "url_path_template": "users/{pk}",
                "sortable": True,
                "htmx_nav": True,
            },
            {
                "header": "Email",
                "template": "cotton/data-table-cells/text.html",
                "attr": "email",
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
                "template": "educator_interface/data-table-cells/user_courses.html",
            },
        ]


class UserDetailsPanel(InstanceDetailsPanel):
    fields = [
        "first_name",
        "last_name",
        "email",
    ]


class UserCohortsPanel(DataTablePanel):
    title = "Cohorts"
    data_table = CohortDataTable

    def get_filters(self) -> dict:
        return {"cohortmembership__user": self.instance}


class UserInstanceView(InstanceView):
    panels = {
        "details": UserDetailsPanel,
        "cohorts": UserCohortsPanel,
    }


class CohortDetailsPanel(InstanceDetailsPanel):
    fields = ["name"]
    editable = True
    form_class = CohortForm


class CohortCourseRegistrationDataTable(DataTable):
    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        return CohortCourseRegistration.objects.select_related("collection").order_by(
            "collection__title"
        )

    @staticmethod
    def get_columns() -> list[dict[str, object]]:
        return [
            {
                "header": "Course",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "collection.title",
                "url_name": "educator_interface:interface",
                "url_path_template": "courses/{collection.pk}",
                "htmx_nav": True,
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
    data_table = UserDataTable

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

    def _get_selected_registration(
        self,
        registrations: list[CohortCourseRegistration],
        selected_reg_pk: str | None,
    ) -> CohortCourseRegistration:
        """Pick the selected registration from the list, defaulting to first active."""
        selected_reg = None
        if selected_reg_pk:
            selected_reg = next(
                (r for r in registrations if str(r.pk) == selected_reg_pk), None
            )
        if not selected_reg:
            active = [r for r in registrations if r.is_active]
            selected_reg = active[0] if active else registrations[0]
        return selected_reg

    def _paginate_course_items(
        self,
        course: Course,
        col_page_num: int | str,
    ) -> tuple[list[Topic | Form], list[dict[str, object]], bool, Page]:
        """Paginate course items and build visible part headers.

        Returns (visible_items, visible_parts, has_parts, col_page).
        """
        all_flat = course.children_flat()
        items: list[Topic | Form] = []
        part_children_map: dict[CoursePart, list[Topic | Form]] = {}
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
        col_page = col_paginator.get_page(col_page_num)
        visible_items = list(col_page.object_list)

        visible_item_pks = {item.pk for item in visible_items}
        visible_parts = []
        for part, children in part_children_map.items():
            visible_children = [c for c in children if c.pk in visible_item_pks]
            if visible_children:
                visible_parts.append({"part": part, "span": len(visible_children)})

        return visible_items, visible_parts, bool(part_children_map), col_page

    def _paginate_students(
        self,
        cohort: Cohort,
        course: Course,
        page_num: int | str,
    ) -> Page:
        """Return a paginated page of cohort memberships annotated with progress."""
        progress_subquery = Subquery(
            CourseProgress.objects.filter(
                user=OuterRef("user"),
                course=course,
            ).values("progress_percentage")[:1],
            output_field=IntegerField(),
        )

        memberships = (
            CohortMembership.objects.filter(cohort=cohort)
            .select_related("user")
            .annotate(progress=Coalesce(progress_subquery, Value(0)))
            .order_by("progress", "user__email")
        )

        student_paginator = Paginator(memberships, self.STUDENT_PAGE_SIZE)
        return student_paginator.get_page(page_num)

    def _fetch_progress_maps(
        self,
        visible_user_ids: list[int],
        visible_items: list[Topic | Form],
    ) -> tuple[
        dict[tuple[int, UUID], TopicProgress],
        dict[tuple[int, UUID], FormProgressData],
    ]:
        """Fetch topic and form progress keyed by (user_id, item_id).

        Returns (topic_progress_map, form_progress_map).
        """
        visible_topic_ids = [
            item.id for item in visible_items if isinstance(item, Topic)
        ]
        visible_form_ids = [item.id for item in visible_items if isinstance(item, Form)]

        topic_progress_map: dict[tuple[int, UUID], TopicProgress] = {}
        if visible_topic_ids:
            for tp in TopicProgress.objects.filter(
                user_id__in=visible_user_ids, topic_id__in=visible_topic_ids
            ).select_related("topic"):
                topic_progress_map[(tp.user_id, tp.topic_id)] = tp

        form_progress_map: dict[tuple[int, UUID], FormProgressData] = {}
        if visible_form_ids:
            for fp in (
                FormProgress.objects.filter(
                    user_id__in=visible_user_ids, form_id__in=visible_form_ids
                )
                .select_related("form")
                .order_by(F("completed_time").desc(nulls_last=True), "-start_time")
            ):
                key = (fp.user_id, fp.form_id)
                if key not in form_progress_map:
                    form_progress_map[key] = FormProgressData(
                        latest=fp, completed_count=0
                    )
                if fp.completed_time is not None:
                    form_progress_map[key]["completed_count"] += 1

        return topic_progress_map, form_progress_map

    def _fetch_deadline_data(
        self,
        selected_reg: CohortCourseRegistration,
        visible_items: list[Topic | Form],
        student_page: Page,
    ) -> tuple[
        CohortDeadline | None,
        dict[tuple[int, UUID | None], CohortDeadline],
        dict[tuple[int, int | None, UUID | None], UserCohortDeadlineOverride],
        DjangoContentType,
        DjangoContentType,
    ]:
        """Fetch cohort deadlines and student overrides for visible items.

        Returns (course_deadline, deadline_map, student_override_map, topic_ct, form_ct).
        """
        topic_ct = DjangoContentType.objects.get_for_model(Topic)
        form_ct = DjangoContentType.objects.get_for_model(Form)

        visible_item_ids = [item.id for item in visible_items]
        deadline_q = Q(content_type__isnull=True, object_id__isnull=True)
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

        deadline_map: dict[tuple[int, UUID | None], CohortDeadline] = {}
        course_deadline = None
        for dl in cohort_deadlines:
            if dl.content_type_id is None:
                course_deadline = dl
            else:
                deadline_map[(dl.content_type_id, dl.object_id)] = dl

        student_override_map: dict[
            tuple[int, int | None, UUID | None], UserCohortDeadlineOverride
        ] = {}
        user_ids = [m.user_id for m in student_page.object_list]
        if user_ids:
            overrides = UserCohortDeadlineOverride.objects.filter(
                cohort_course_registration=selected_reg,
                user_id__in=user_ids,
            ).filter(deadline_q)
            for ovr in overrides:
                student_override_map[
                    (ovr.user_id, ovr.content_type_id, ovr.object_id)
                ] = ovr

        return course_deadline, deadline_map, student_override_map, topic_ct, form_ct

    def _build_topic_cell(
        self,
        item: Topic,
        user: User,
        topic_progress_map: dict[tuple[int, UUID], TopicProgress],
    ) -> dict[str, object]:
        """Build progress fields for a Topic cell."""
        tp = topic_progress_map.get((user.id, item.id))
        return {
            "progress": tp,
            "is_completed": tp is not None and tp.complete_time is not None,
            "is_started": tp is not None,
            "completed_time": tp.complete_time if tp else None,
            "start_time": tp.start_time if tp else None,
        }

    def _build_form_cell(
        self,
        item: Form,
        user: User,
        form_progress_map: dict[tuple[int, UUID], FormProgressData],
    ) -> dict[str, object]:
        """Build progress fields for a Form cell."""
        fp_data = form_progress_map.get((user.id, item.id))
        if not fp_data:
            return {
                "progress": None,
                "is_completed": False,
                "is_started": False,
                "completed_time": None,
                "start_time": None,
            }

        fp = fp_data["latest"]
        cell: dict[str, object] = {
            "progress": fp,
            "is_completed": fp.completed_time is not None,
            "is_started": True,
            "completed_time": fp.completed_time,
            "start_time": fp.start_time,
            "completed_count": fp_data["completed_count"],
            "is_quiz": item.strategy == "QUIZ",
        }
        if cell["is_completed"] and cell["is_quiz"] and fp.scores:
            try:
                cell["quiz_percentage"] = fp.quiz_percentage()
                cell["passed"] = (
                    fp.passed() if item.quiz_pass_percentage is not None else None
                )
            except (KeyError, ValueError):
                cell["quiz_percentage"] = None
                cell["passed"] = None
        return cell

    def _build_cell(
        self,
        item: Topic | Form,
        user: User,
        topic_ct: DjangoContentType,
        form_ct: DjangoContentType,
        topic_progress_map: dict[tuple[int, UUID], TopicProgress],
        form_progress_map: dict[tuple[int, UUID], FormProgressData],
        deadline_map: dict[tuple[int, UUID | None], CohortDeadline],
        student_override_map: dict[
            tuple[int, int | None, UUID | None], UserCohortDeadlineOverride
        ],
        now: datetime,
    ) -> dict[str, object]:
        """Build the cell data dict for one user/item intersection."""
        cell: dict[str, object] = {
            "item": item,
            "is_quiz": False,
            "completed_count": 0,
            "quiz_percentage": None,
            "passed": None,
        }

        if isinstance(item, Topic):
            cell.update(self._build_topic_cell(item, user, topic_progress_map))
        elif isinstance(item, Form):
            cell.update(self._build_form_cell(item, user, form_progress_map))
        else:
            raise NotImplementedError(
                f"Cell building not implemented for {type(item).__name__}"
            )

        item_ct = topic_ct if isinstance(item, Topic) else form_ct
        item_deadline = deadline_map.get((item_ct.id, item.id))
        override = student_override_map.get((user.id, item_ct.id, item.id))
        effective_deadline = override or item_deadline
        cell["deadline"] = item_deadline
        cell["override"] = override
        cell["effective_deadline"] = effective_deadline

        cell["is_overdue"] = False
        cell["is_hard_overdue"] = False
        if (
            effective_deadline
            and not cell["is_completed"]
            and effective_deadline.deadline < now
        ):
            cell["is_overdue"] = True
            cell["is_hard_overdue"] = effective_deadline.is_hard_deadline

        return cell

    def _build_rows(
        self,
        student_page: Page,
        visible_items: list[Topic | Form],
        topic_ct: DjangoContentType,
        form_ct: DjangoContentType,
        topic_progress_map: dict[tuple[int, UUID], TopicProgress],
        form_progress_map: dict[tuple[int, UUID], FormProgressData],
        deadline_map: dict[tuple[int, UUID | None], CohortDeadline],
        student_override_map: dict[
            tuple[int, int | None, UUID | None], UserCohortDeadlineOverride
        ],
    ) -> list[dict[str, object]]:
        """Build row data for each student on the current page."""
        now = tz.now()
        rows = []
        for membership in student_page.object_list:
            user = membership.user
            cells = [
                self._build_cell(
                    item,
                    user,
                    topic_ct,
                    form_ct,
                    topic_progress_map,
                    form_progress_map,
                    deadline_map,
                    student_override_map,
                    now,
                )
                for item in visible_items
            ]

            name_parts = [p for p in (user.first_name, user.last_name) if p]
            display_name = " ".join(name_parts) if name_parts else user.email

            rows.append(
                {
                    "user": user,
                    "display_name": display_name,
                    "student_url": reverse(
                        "educator_interface:interface",
                        kwargs={"path_string": f"users/{user.pk}"},
                    ),
                    "progress": membership.progress,
                    "cells": cells,
                }
            )
        return rows

    def _build_header_items(
        self,
        visible_items: list[Topic | Form],
        deadline_map: dict[tuple[int, UUID | None], CohortDeadline],
        topic_ct: DjangoContentType,
        form_ct: DjangoContentType,
    ) -> list[dict[str, object]]:
        """Build header items with deadline info for the column headers.

        Returns a list of dicts, each containing:
        - "item": the Topic or Form instance for the column
        - "deadline": the CohortDeadline for this item, or None if no deadline is set
        """
        header_items: list[dict[str, object]] = []
        for item in visible_items:
            item_ct = topic_ct if isinstance(item, Topic) else form_ct
            item_deadline = deadline_map.get((item_ct.id, item.id))
            header_items.append({"item": item, "deadline": item_deadline})
        return header_items

    def get_content(self, request, base_url: str = "", panel_name: str = "") -> str:
        if not isinstance(self.instance, Cohort):
            raise TypeError(f"Expected Cohort instance, got {type(self.instance)}")
        cohort = self.instance

        registrations = list(
            CohortCourseRegistration.objects.filter(cohort=cohort)
            .select_related("collection")
            .order_by("-is_active", "collection__title")
        )

        if not registrations:
            return render_to_string(
                "educator_interface/partials/course_progress_panel.html",
                {"registrations": []},
                request=request,
            )

        selected_reg = self._get_selected_registration(
            registrations,
            request.GET.get("registration"),
        )
        course: Course = selected_reg.collection

        visible_items, visible_parts, has_parts, col_page = self._paginate_course_items(
            course,
            request.GET.get("col_page", 1),
        )

        student_page = self._paginate_students(
            cohort,
            course,
            request.GET.get("page", 1),
        )

        visible_user_ids = [m.user.id for m in student_page.object_list]

        topic_progress_map, form_progress_map = self._fetch_progress_maps(
            visible_user_ids,
            visible_items,
        )

        course_deadline, deadline_map, student_override_map, topic_ct, form_ct = (
            self._fetch_deadline_data(selected_reg, visible_items, student_page)
        )

        rows = self._build_rows(
            student_page,
            visible_items,
            topic_ct,
            form_ct,
            topic_progress_map,
            form_progress_map,
            deadline_map,
            student_override_map,
        )

        header_items = self._build_header_items(
            visible_items,
            deadline_map,
            topic_ct,
            form_ct,
        )

        context = {
            "registrations": registrations,
            "selected_reg": selected_reg,
            "course": course,
            "course_deadline": course_deadline,
            "visible_items": visible_items,
            "header_items": header_items,
            "visible_parts": visible_parts,
            "has_parts": has_parts,
            "col_page": col_page,
            "student_page": student_page,
            "rows": rows,
            "deadline_map": deadline_map,
            "topic_ct": topic_ct,
            "form_ct": form_ct,
            "base_url": base_url,
            "now": tz.now(),
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
    tabs = {
        "course_progress": Tab(
            label="Course Progress",
            panels={
                "course_progress": CohortCourseProgressPanel,
            },
        ),
        "details": Tab(
            label="Details",
            panels={
                "details": CohortDetailsPanel,
                "courses": CourseRegistrationsPanel,
                "students": CohortStudentsPanel,
            },
        ),
    }

    def get_actions(self) -> list[PanelAction]:
        return [
            DeleteAction(
                success_url=reverse(
                    "educator_interface:interface", kwargs={"path_string": "cohorts"}
                )
            ),
        ]


class CreateCohortAction(CreateInstanceAction):
    label = "Create Cohort"
    form_class = CohortForm
    form_title = "Create Cohort"
    action_name = "create_cohort"

    def get_success_url(self, instance: Model) -> str:
        return reverse(
            "educator_interface:interface",
            kwargs={"path_string": f"cohorts/{instance.pk}"},
        )

    def get_created_event_name(self) -> str:
        return "cohortCreated"


class CohortConfig(ListViewConfig):
    url_name = "cohorts"
    menu_label = "Cohorts"
    model = Cohort
    list_view = CohortDataTable
    instance_view = CohortInstanceView

    @classmethod
    def get_actions(cls, request: HttpRequest) -> list[PanelAction]:
        return [CreateCohortAction()]


class UserConfig(ListViewConfig):
    url_name = "users"
    menu_label = "Users"
    model = User
    list_view = UserDataTable
    instance_view = UserInstanceView


class CourseDataTable(DataTable):
    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        qs: QuerySet = (
            Course.objects.all()
            .annotate(
                cohort_count=Count(
                    "cohort_registrations",
                    filter=Q(cohort_registrations__is_active=True),
                    distinct=True,
                ),
                direct_student_count=Count(
                    "user_registrations",
                    filter=Q(user_registrations__is_active=True),
                    distinct=True,
                ),
            )
            .prefetch_related(
                "cohort_registrations__cohort__cohortmembership_set",
                "user_registrations",
            )
            .order_by("title")
        )
        return qs

    @staticmethod
    def _annotate_total_student_count(page_obj: Page) -> None:
        """Calculate total unique active users (direct + through cohorts) for each course.

        Uses .all() instead of .filter() to leverage the prefetch cache and avoid N+1 queries.
        """
        for course in page_obj.object_list:
            cohort_user_ids: set[UUID] = set()
            for cohort_reg in course.cohort_registrations.all():
                if not cohort_reg.is_active:
                    continue
                cohort_user_ids.update(
                    m.user_id for m in cohort_reg.cohort.cohortmembership_set.all()
                )

            direct_user_ids = {
                reg.user_id for reg in course.user_registrations.all() if reg.is_active
            }

            course.total_student_count = len(cohort_user_ids | direct_user_ids)

    @classmethod
    def get_rows(
        cls, request: HttpRequest, columns: list[dict], filters: dict | None = None
    ) -> Page:
        page_obj = super().get_rows(request, columns, filters=filters)
        cls._annotate_total_student_count(page_obj)
        return page_obj

    @staticmethod
    def get_columns() -> list[dict[str, object]]:
        return [
            {
                "header": "Title",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "title",
                "url_name": "educator_interface:interface",
                "url_path_template": "courses/{pk}",
                "htmx_nav": True,
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
    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        return CohortCourseRegistration.objects.select_related(
            "cohort", "collection"
        ).order_by("cohort__name")

    @staticmethod
    def get_columns() -> list[dict[str, object]]:
        return [
            {
                "header": "Cohort",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "cohort.name",
                "url_name": "educator_interface:interface",
                "url_path_template": "cohorts/{cohort.pk}",
                "htmx_nav": True,
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
    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        return UserCourseRegistration.objects.select_related(
            "user", "collection"
        ).order_by("user__first_name", "user__last_name")

    @staticmethod
    def get_columns() -> list[dict[str, object]]:
        return [
            {
                "header": "First Name",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "user.first_name",
                "url_name": "educator_interface:interface",
                "url_path_template": "users/{user.pk}",
                "htmx_nav": True,
            },
            {
                "header": "Last Name",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "user.last_name",
                "url_name": "educator_interface:interface",
                "url_path_template": "users/{user.pk}",
                "htmx_nav": True,
            },
            {
                "header": "Email",
                "template": "cotton/data-table-cells/text.html",
                "attr": "user.email",
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
    title = "Direct Registrations"
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


interface_config: dict[str, type[ListViewConfig]] = {
    config.url_name: config for config in [CohortConfig, UserConfig, CourseConfig]
}


@login_required
def interface(request: HttpRequest, path_string: str = "") -> HttpResponse:
    return panel_framework_view(
        config=interface_config,
        request=request,
        path_string=path_string,
        template_name="educator_interface/interface.html",
        url_name="educator_interface:interface",
        root_label="Educator",
    )
