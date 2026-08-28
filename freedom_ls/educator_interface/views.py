from __future__ import annotations

from datetime import datetime
from typing import TypedDict, cast
from uuid import UUID

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.core.paginator import Page, Paginator
from django.db.models import (
    Count,
    F,
    IntegerField,
    Model,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone as tz

from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePart,
    Topic,
)
from freedom_ls.educator_interface.exceptions import OrganisationScopeDenied
from freedom_ls.educator_interface.forms import CohortForm
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortDeadline,
    CohortMembership,
    Learner,
    LearnerCohortDeadlineOverride,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    cohorts_visible_to,
    learners_visible_to,
    organisations_accessible_to,
)
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)
from freedom_ls.organisations.models import Organisation
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

#: Session key remembering the educator's last-visited organisation, used
#: only to pick a default for the bare /educator/ redirect. Re-authorised on
#: every use — the session value is never trusted on its own.
LAST_ORGANISATION_SESSION_KEY = "educator_interface_last_organisation_slug"


class _OrganisationScopedRequest(HttpRequest):
    """Typing-only view of a request after interface() has resolved and
    authorised an organisation onto it.

    panel_framework names none of these: the scope it enforces is whatever a
    config lists in required_request_attrs, and the title segment reads
    panel_scope_name. So this class exists purely so this module can
    type-check the attribute access without a type: ignore, and is never
    instantiated; only used with cast().
    """

    organisation: Organisation
    panel_scope_name: str
    panel_url_kwargs: dict[str, str]
    accessible_organisations: list[Organisation]
    path_string: str
    panel_announcement: str
    panel_extra_oob: list[str]


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
        request = cast(_OrganisationScopedRequest, request)
        return (
            cohorts_visible_to(request.user, request.organisation)
            .annotate(
                learner_count=Count("cohortmembership", distinct=True),
            )
            .prefetch_related("course_registrations__course")
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
                "header": "Active Learners",
                "template": "cotton/data-table-cells/text.html",
                "attr": "learner_count",
            },
            {
                "header": "Registered Courses",
                "template": "educator_interface/data-table-cells/cohort_courses.html",
            },
        ]


class LearnerDataTable(DataTable):
    search_fields = ["user__first_name", "user__last_name", "user__email"]

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        request = cast(_OrganisationScopedRequest, request)
        organisation = request.organisation
        return (
            learners_visible_to(request.user, organisation)
            .select_related("user")
            .prefetch_related(
                # A Learner belongs to exactly one organisation, so the course
                # registrations hanging off it are already organisation-local.
                # Its cohort memberships are not narrowed by that: an educator
                # holding a grant on one cohort would otherwise have the
                # organisation's other cohorts named -- and linked -- in the
                # Cohorts cell, which reads this relation through .all().
                Prefetch(
                    "cohortmembership_set",
                    queryset=CohortMembership.objects.filter(
                        cohort__in=cohorts_visible_to(request.user, organisation)
                    ).select_related("cohort"),
                ),
                "learnercourseregistration_set__course",
            )
            .order_by("user__first_name", "user__last_name")
        )

    @staticmethod
    def get_columns() -> list[dict[str, object]]:
        return [
            {
                "header": "First Name",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "user.first_name",
                "url_name": "educator_interface:interface",
                "url_path_template": "learners/{pk}",
                "sortable": True,
                "htmx_nav": True,
            },
            {
                "header": "Last Name",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "user.last_name",
                "url_name": "educator_interface:interface",
                "url_path_template": "learners/{pk}",
                "sortable": True,
                "htmx_nav": True,
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
                "template": "educator_interface/data-table-cells/learner_courses.html",
            },
        ]


class LearnerDetailsPanel(InstanceDetailsPanel):
    fields = [
        "user.first_name",
        "user.last_name",
        "user.email",
    ]


class LearnerCohortsPanel(DataTablePanel):
    title = "Cohorts"
    data_table = CohortDataTable

    def get_filters(self) -> dict:
        return {"cohortmembership__learner": self.instance}


class LearnerInstanceView(InstanceView):
    panels = {
        "details": LearnerDetailsPanel,
        "cohorts": LearnerCohortsPanel,
    }


class CohortDetailsPanel(InstanceDetailsPanel):
    fields = ["name"]
    editable = True
    form_class = CohortForm


class CohortCourseRegistrationDataTable(DataTable):
    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        return CohortCourseRegistration.objects.select_related("course").order_by(
            "course__title"
        )

    @staticmethod
    def get_columns() -> list[dict[str, object]]:
        return [
            {
                "header": "Course",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "course.title",
                "url_name": "educator_interface:interface",
                "url_path_template": "courses/{course.pk}",
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


class CohortLearnersPanel(DataTablePanel):
    title = "Learners"
    data_table = LearnerDataTable

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
    LEARNER_PAGE_SIZE = 20

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
    ) -> tuple[list[ContentCollectionItem], list[dict[str, object]], bool, Page]:
        """Paginate the course's collection items and build visible part headers.

        Columns are placements, not content: one topic placed twice in a course
        is two columns, and each carries its own progress.

        Returns (visible_collection_items, visible_parts, has_parts, col_page).
        """
        all_flat = course.collection_items_flat()
        collection_items: list[ContentCollectionItem] = []
        part_children_map: dict[CoursePart, list[ContentCollectionItem]] = {}
        current_part = None
        for collection_item in all_flat:
            child = collection_item.child
            if isinstance(child, CoursePart):
                current_part = child
                part_children_map[child] = []
            else:
                collection_items.append(collection_item)
                if current_part is not None:
                    part_children_map[current_part].append(collection_item)

        col_paginator = Paginator(collection_items, self.COLUMN_PAGE_SIZE)
        col_page = col_paginator.get_page(col_page_num)
        visible_collection_items = list(col_page.object_list)

        visible_collection_item_pks = {item.pk for item in visible_collection_items}
        visible_parts = []
        for part, children in part_children_map.items():
            visible_children = [
                c for c in children if c.pk in visible_collection_item_pks
            ]
            if visible_children:
                visible_parts.append({"part": part, "span": len(visible_children)})

        return (
            visible_collection_items,
            visible_parts,
            bool(part_children_map),
            col_page,
        )

    def _paginate_learners(
        self,
        cohort: Cohort,
        selected_reg: CohortCourseRegistration,
        page_num: int | str,
    ) -> Page:
        """Return a paginated page of cohort memberships annotated with progress.

        The percentage is the one this registration granted, so a member who
        also studies the course through another organisation or an individual
        registration is read here at their progress in *this* cohort.

        No tiebreak is needed: one_course_progress_per_cohort_registration
        makes at most one row possible. The [:1] is the belt to that
        constraint's braces -- an unbounded scalar subquery turns a second row
        into a Postgres "more than one row returned" error for the whole
        panel, and the slice costs nothing.
        """
        progress_subquery = Subquery(
            CourseProgress.objects.filter(
                learner=OuterRef("learner"),
                cohort_registration=selected_reg,
            ).values("progress_percentage")[:1],
            output_field=IntegerField(),
        )

        memberships = (
            CohortMembership.objects.filter(cohort=cohort)
            .select_related("learner__user")
            .annotate(progress=Coalesce(progress_subquery, Value(0)))
            .order_by("progress", "learner__user__email")
        )

        learner_paginator = Paginator(memberships, self.LEARNER_PAGE_SIZE)
        return learner_paginator.get_page(page_num)

    def _fetch_progress_maps(
        self,
        visible_learner_ids: list[UUID],
        visible_collection_items: list[ContentCollectionItem],
        selected_reg: CohortCourseRegistration,
    ) -> tuple[
        dict[tuple[UUID, UUID], TopicProgress],
        dict[tuple[UUID, UUID], FormProgressData],
    ]:
        """Fetch topic and form progress keyed by (learner_id, collection_item_id).

        Only rows hanging off this registration's records are read, so the
        cells describe the same enrolment the percentage column does.

        Returns (topic_progress_map, form_progress_map).
        """
        visible_topic_item_ids = [
            item.id
            for item in visible_collection_items
            if isinstance(item.child, Topic)
        ]
        visible_form_item_ids = [
            item.id for item in visible_collection_items if isinstance(item.child, Form)
        ]

        topic_progress_map: dict[tuple[UUID, UUID], TopicProgress] = {}
        if visible_topic_item_ids:
            for tp in TopicProgress.objects.filter(
                course_progress__cohort_registration=selected_reg,
                course_progress__learner_id__in=visible_learner_ids,
                collection_item_id__in=visible_topic_item_ids,
            ).select_related("course_progress", "topic"):
                topic_progress_map[
                    (tp.course_progress.learner_id, tp.collection_item_id)
                ] = tp

        form_progress_map: dict[tuple[UUID, UUID], FormProgressData] = {}
        if visible_form_item_ids:
            for course_attempt in (
                CourseFormAttempt.objects.filter(
                    course_progress__cohort_registration=selected_reg,
                    course_progress__learner_id__in=visible_learner_ids,
                    collection_item_id__in=visible_form_item_ids,
                )
                .select_related("course_progress", "form_progress__form")
                .order_by(
                    F("form_progress__completed_time").desc(nulls_last=True),
                    "-form_progress__start_time",
                )
            ):
                fp = course_attempt.form_progress
                key = (
                    course_attempt.course_progress.learner_id,
                    course_attempt.collection_item_id,
                )
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
        learner_page: Page,
    ) -> tuple[
        CohortDeadline | None,
        dict[tuple[int, UUID | None], CohortDeadline],
        dict[tuple[UUID, int | None, UUID | None], LearnerCohortDeadlineOverride],
        DjangoContentType,
        DjangoContentType,
    ]:
        """Fetch cohort deadlines and learner overrides for visible items.

        Returns (course_deadline, deadline_map, learner_override_map, topic_ct, form_ct).
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

        learner_override_map: dict[
            tuple[UUID, int | None, UUID | None], LearnerCohortDeadlineOverride
        ] = {}
        learner_ids = [m.learner_id for m in learner_page.object_list]
        if learner_ids:
            overrides = LearnerCohortDeadlineOverride.objects.filter(
                cohort_course_registration=selected_reg,
                learner_id__in=learner_ids,
            ).filter(deadline_q)
            for ovr in overrides:
                learner_override_map[
                    (ovr.learner_id, ovr.content_type_id, ovr.object_id)
                ] = ovr

        return course_deadline, deadline_map, learner_override_map, topic_ct, form_ct

    def _build_topic_cell(
        self,
        collection_item: ContentCollectionItem,
        learner_id: UUID,
        topic_progress_map: dict[tuple[UUID, UUID], TopicProgress],
    ) -> dict[str, object]:
        """Build progress fields for a Topic cell."""
        tp = topic_progress_map.get((learner_id, collection_item.id))
        return {
            "progress": tp,
            "is_completed": tp is not None and tp.complete_time is not None,
            "is_started": tp is not None,
            "completed_time": tp.complete_time if tp else None,
            "start_time": tp.start_time if tp else None,
        }

    def _build_form_cell(
        self,
        collection_item: ContentCollectionItem,
        form: Form,
        learner_id: UUID,
        form_progress_map: dict[tuple[UUID, UUID], FormProgressData],
    ) -> dict[str, object]:
        """Build progress fields for a Form cell."""
        fp_data = form_progress_map.get((learner_id, collection_item.id))
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
            "is_quiz": form.strategy == "QUIZ",
        }
        if cell["is_completed"] and cell["is_quiz"] and fp.scores:
            try:
                cell["quiz_percentage"] = fp.quiz_percentage()
                cell["passed"] = (
                    fp.passed() if form.quiz_pass_percentage is not None else None
                )
            except ValueError:
                cell["quiz_percentage"] = None
                cell["passed"] = None
        return cell

    def _build_cell(
        self,
        collection_item: ContentCollectionItem,
        learner_id: UUID,
        topic_ct: DjangoContentType,
        form_ct: DjangoContentType,
        topic_progress_map: dict[tuple[UUID, UUID], TopicProgress],
        form_progress_map: dict[tuple[UUID, UUID], FormProgressData],
        deadline_map: dict[tuple[int, UUID | None], CohortDeadline],
        learner_override_map: dict[
            tuple[UUID, int | None, UUID | None], LearnerCohortDeadlineOverride
        ],
        now: datetime,
    ) -> dict[str, object]:
        """Build the cell data dict for one learner/placement intersection."""
        child = collection_item.child
        cell: dict[str, object] = {
            "item": child,
            "is_quiz": False,
            "completed_count": 0,
            "quiz_percentage": None,
            "passed": None,
        }

        if isinstance(child, Topic):
            cell.update(
                self._build_topic_cell(collection_item, learner_id, topic_progress_map)
            )
        elif isinstance(child, Form):
            cell.update(
                self._build_form_cell(
                    collection_item, child, learner_id, form_progress_map
                )
            )
        else:
            raise NotImplementedError(
                f"Cell building not implemented for {type(child).__name__}"
            )

        # Deadlines point at the Topic or Form, never at the placement, so the
        # lookup stays keyed on the content id.
        item_ct = topic_ct if isinstance(child, Topic) else form_ct
        item_deadline = deadline_map.get((item_ct.id, child.id))
        override = learner_override_map.get((learner_id, item_ct.id, child.id))
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
        learner_page: Page,
        visible_collection_items: list[ContentCollectionItem],
        topic_ct: DjangoContentType,
        form_ct: DjangoContentType,
        topic_progress_map: dict[tuple[UUID, UUID], TopicProgress],
        form_progress_map: dict[tuple[UUID, UUID], FormProgressData],
        deadline_map: dict[tuple[int, UUID | None], CohortDeadline],
        learner_override_map: dict[
            tuple[UUID, int | None, UUID | None], LearnerCohortDeadlineOverride
        ],
        organisation_slug: str,
    ) -> list[dict[str, object]]:
        """Build row data for each learner on the current page."""
        now = tz.now()
        rows = []
        for membership in learner_page.object_list:
            user = membership.learner.user
            cells = [
                self._build_cell(
                    collection_item,
                    membership.learner_id,
                    topic_ct,
                    form_ct,
                    topic_progress_map,
                    form_progress_map,
                    deadline_map,
                    learner_override_map,
                    now,
                )
                for collection_item in visible_collection_items
            ]

            name_parts = [p for p in (user.first_name, user.last_name) if p]
            display_name = " ".join(name_parts) if name_parts else user.email

            rows.append(
                {
                    "user": user,
                    "display_name": display_name,
                    "learner_url": reverse(
                        "educator_interface:interface",
                        kwargs={
                            "organisation_slug": organisation_slug,
                            "path_string": f"learners/{membership.learner_id}",
                        },
                    ),
                    "progress": membership.progress,
                    "cells": cells,
                }
            )
        return rows

    def _build_header_items(
        self,
        visible_collection_items: list[ContentCollectionItem],
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
        for collection_item in visible_collection_items:
            child = cast("Topic | Form", collection_item.child)
            item_ct = topic_ct if isinstance(child, Topic) else form_ct
            item_deadline = deadline_map.get((item_ct.id, child.id))
            header_items.append({"item": child, "deadline": item_deadline})
        return header_items

    def get_content(self, request, base_url: str = "", panel_name: str = "") -> str:
        if not isinstance(self.instance, Cohort):
            raise TypeError(f"Expected Cohort instance, got {type(self.instance)}")
        cohort = self.instance

        registrations = list(
            CohortCourseRegistration.objects.filter(cohort=cohort)
            .select_related("course")
            .order_by("-is_active", "course__title")
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
        course: Course = selected_reg.course

        visible_collection_items, visible_parts, has_parts, col_page = (
            self._paginate_course_items(
                course,
                request.GET.get("col_page", 1),
            )
        )
        # Deadlines are set against the Topic or Form, so the deadline fetch
        # takes the resolved children while everything else takes placements.
        visible_items = [
            cast("Topic | Form", ci.child) for ci in visible_collection_items
        ]

        learner_page = self._paginate_learners(
            cohort,
            selected_reg,
            request.GET.get("page", 1),
        )

        visible_learner_ids = [m.learner_id for m in learner_page.object_list]

        topic_progress_map, form_progress_map = self._fetch_progress_maps(
            visible_learner_ids,
            visible_collection_items,
            selected_reg,
        )

        course_deadline, deadline_map, learner_override_map, topic_ct, form_ct = (
            self._fetch_deadline_data(selected_reg, visible_items, learner_page)
        )

        rows = self._build_rows(
            learner_page,
            visible_collection_items,
            topic_ct,
            form_ct,
            topic_progress_map,
            form_progress_map,
            deadline_map,
            learner_override_map,
            cohort.organisation.slug,
        )

        header_items = self._build_header_items(
            visible_collection_items,
            deadline_map,
            topic_ct,
            form_ct,
        )

        context = {
            "registrations": registrations,
            "selected_reg": selected_reg,
            "course": course,
            "course_deadline": course_deadline,
            "header_items": header_items,
            "visible_parts": visible_parts,
            "has_parts": has_parts,
            "col_page": col_page,
            "learner_page": learner_page,
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
        if request.headers.get("HX-Target") == "course-progress-content":
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
                "learners": CohortLearnersPanel,
            },
        ),
    }

    def get_actions(self) -> list[PanelAction]:
        # The instance already carries its own organisation — no request
        # available here, so no need for one.
        cohort = cast(Cohort, self.instance)
        return [
            DeleteAction(
                success_url=reverse(
                    "educator_interface:interface",
                    kwargs={
                        "organisation_slug": cohort.organisation.slug,
                        "path_string": "cohorts",
                    },
                )
            ),
        ]


class CreateCohortAction(CreateInstanceAction):
    label = "Create Cohort"
    form_class = CohortForm
    form_title = "Create Cohort"
    action_name = "create_cohort"

    def get_form(
        self, request: HttpRequest, instance: Model | None = None
    ) -> forms.ModelForm:
        # The organisation is not a user choice — CohortForm never exposes
        # the field — so it comes from the URL the request already resolved
        # and authorised, not from anything the form submitted. It is attached
        # here rather than in form_valid because the per-organisation
        # uniqueness constraint can only be checked while cleaning if the
        # instance already carries its organisation.
        form = super().get_form(request, instance)
        organisation = cast(_OrganisationScopedRequest, request).organisation
        cast(Cohort, form.instance).organisation = organisation
        self._organisation_slug = organisation.slug
        return form

    def get_success_url(self, instance: Model) -> str:
        return reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": self._organisation_slug,
                "path_string": f"cohorts/{instance.pk}",
            },
        )

    def get_created_event_name(self) -> str:
        return "cohortCreated"


class CohortConfig(ListViewConfig):
    url_name = "cohorts"
    menu_label = "Cohorts"
    model = Cohort
    list_view = CohortDataTable
    instance_view = CohortInstanceView

    required_request_attrs = ("organisation",)

    @classmethod
    def get_actions(cls, request: HttpRequest) -> list[PanelAction]:
        return [CreateCohortAction()]

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        organisation = cast(_OrganisationScopedRequest, request).organisation
        if (
            not cohorts_visible_to(request.user, organisation)
            .filter(pk=instance.pk)
            .exists()
        ):
            raise OrganisationScopeDenied


class LearnerConfig(ListViewConfig):
    url_name = "learners"
    menu_label = "Learners"
    model = Learner
    list_view = LearnerDataTable
    instance_view = LearnerInstanceView

    required_request_attrs = ("organisation",)

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        organisation = cast(_OrganisationScopedRequest, request).organisation
        if (
            not learners_visible_to(request.user, organisation)
            .filter(pk=instance.pk)
            .exists()
        ):
            raise OrganisationScopeDenied


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
                direct_learner_count=Count(
                    "learner_registrations",
                    filter=Q(learner_registrations__is_active=True),
                    distinct=True,
                ),
                interest_count=Count("interests", distinct=True),
            )
            .prefetch_related(
                "cohort_registrations__cohort__cohortmembership_set__learner",
                "learner_registrations__learner",
            )
            .order_by("title")
        )
        return qs

    @staticmethod
    def _annotate_total_learner_count(page_obj: Page) -> None:
        """Calculate total unique active users (direct + through cohorts) for each course.

        Uses .all() instead of .filter() to leverage the prefetch cache and avoid N+1 queries.
        """
        for course in page_obj.object_list:
            cohort_user_ids: set[UUID] = set()
            for cohort_reg in course.cohort_registrations.all():
                if not cohort_reg.is_active:
                    continue
                cohort_user_ids.update(
                    m.learner.user_id
                    for m in cohort_reg.cohort.cohortmembership_set.all()
                )

            direct_user_ids = {
                reg.learner.user_id
                for reg in course.learner_registrations.all()
                if reg.is_active
            }

            course.total_learner_count = len(cohort_user_ids | direct_user_ids)

    @classmethod
    def get_rows(
        cls, request: HttpRequest, columns: list[dict], filters: dict | None = None
    ) -> Page:
        page_obj = super().get_rows(request, columns, filters=filters)
        cls._annotate_total_learner_count(page_obj)
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
                "header": "Visibility",
                "template": "cotton/data-table-cells/text.html",
                "attr": "get_visibility_display",
            },
            {
                "header": "Interest",
                "template": "cotton/data-table-cells/text.html",
                "attr": "interest_count",
            },
            {
                "header": "Active Learners",
                "template": "cotton/data-table-cells/text.html",
                "attr": "total_learner_count",
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
            "cohort", "course"
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
        return {"course": self.instance}


class CourseLearnerRegistrationDataTable(DataTable):
    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        # Courses themselves are not organisation-scoped (CourseConfig is
        # exempt), but the individual registrations rendered here belong to
        # one organisation each and must not leak across them.
        organisation = cast(_OrganisationScopedRequest, request).organisation
        return (
            LearnerCourseRegistration.objects.select_related("learner__user", "course")
            .filter(learner__organisation=organisation)
            .order_by("learner__user__first_name", "learner__user__last_name")
        )

    @staticmethod
    def get_columns() -> list[dict[str, object]]:
        return [
            {
                "header": "First Name",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "learner.user.first_name",
                "url_name": "educator_interface:interface",
                "url_path_template": "learners/{learner.pk}",
                "htmx_nav": True,
            },
            {
                "header": "Last Name",
                "template": "cotton/data-table-cells/link.html",
                "text_attr": "learner.user.last_name",
                "url_name": "educator_interface:interface",
                "url_path_template": "learners/{learner.pk}",
                "htmx_nav": True,
            },
            {
                "header": "Email",
                "template": "cotton/data-table-cells/text.html",
                "attr": "learner.user.email",
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


class CourseLearnerRegistrationsPanel(DataTablePanel):
    title = "Direct Registrations"
    data_table = CourseLearnerRegistrationDataTable

    def get_filters(self) -> dict:
        return {"course": self.instance}


class CourseInstanceView(InstanceView):
    panels = {
        "details": CourseDetailsPanel,
        "cohorts": CourseCohortRegistrationsPanel,
        "learners": CourseLearnerRegistrationsPanel,
    }


class CourseConfig(ListViewConfig):
    url_name = "courses"
    menu_label = "Courses"
    model = Course
    list_view = CourseDataTable
    instance_view = CourseInstanceView

    required_request_attrs = ("organisation",)

    check_access_exempt_reason = (
        "Courses are shared across the Site and are not organisation-scoped "
        "in this cut. The list is also currently unguarded entirely."
    )

    # @claude: CourseDataTable.get_queryset returns Course.objects.all(), so every
    # logged-in user sees every course on the Site with no permission check. The
    # real check belongs to critical_security_fixes; this override keeps today's
    # behaviour while making the gap declared and greppable rather than invisible.
    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        return


interface_config: dict[str, type[ListViewConfig]] = {
    config.url_name: config for config in [CohortConfig, LearnerConfig, CourseConfig]
}


@login_required
def interface_root(request: HttpRequest) -> HttpResponse:
    """Redirect a bare /educator/ to a concrete organisation URL.

    The session remembers the last-visited organisation only to decide this
    redirect, and that value is re-authorised on every use — once a URL
    names an organisation, the URL always wins over the session.
    """
    accessible = organisations_accessible_to(request.user)
    remembered_slug = request.session.get(LAST_ORGANISATION_SESSION_KEY)
    organisation = (
        accessible.filter(slug=remembered_slug).first() if remembered_slug else None
    ) or accessible.first()  # accessible is ordered by name
    if organisation is None:
        raise Http404
    return redirect(
        "educator_interface:interface",
        organisation_slug=organisation.slug,
        path_string="cohorts",
    )


@login_required
def interface(
    request: HttpRequest, organisation_slug: str, path_string: str = ""
) -> HttpResponse:
    """Resolve and authorise the organisation named in the URL, once.

    Selecting an organisation is an authorisation decision, not a filter:
    unlike Site, which is derived from the request host and cannot be
    forged, an organisation comes from user-supplied URL input. "No such
    slug" and "slug exists but you have no access" both 404 identically — a
    403 would confirm the slug is real and let an attacker enumerate a
    Site's organisation names.
    """
    organisation = get_object_or_404(Organisation, slug=organisation_slug)
    if (
        not organisations_accessible_to(request.user)
        .filter(pk=organisation.pk)
        .exists()
    ):
        raise Http404
    scoped_request = cast(_OrganisationScopedRequest, request)
    scoped_request.organisation = organisation
    scoped_request.panel_scope_name = organisation.name
    scoped_request.panel_url_kwargs = {"organisation_slug": organisation.slug}
    scoped_request.accessible_organisations = list(
        organisations_accessible_to(request.user)
    )
    scoped_request.path_string = path_string
    # Rendered into the same OOB bundle panel_framework already assembles
    # for breadcrumbs/sidebar/title/announcer (panel_framework/views.py) —
    # on every navigation, not only a switch, because the switcher's
    # per-organisation links embed the current path_string, which changes
    # on every navigation and would otherwise go stale the moment the user
    # moves to a different section without switching organisation.
    scoped_request.panel_extra_oob = [
        "educator_interface/partials/organisation_switcher.html"
    ]
    # Guarded so the session store is only written when the value actually
    # changes — an unconditional assignment would mark the session dirty on
    # every educator page load.
    if request.session.get(LAST_ORGANISATION_SESSION_KEY) != organisation.slug:
        request.session[LAST_ORGANISATION_SESSION_KEY] = organisation.slug

    is_switch = request.headers.get("X-Organisation-Switch") == "true"
    if is_switch:
        scoped_request.panel_announcement = f"Now viewing {organisation.name}"

    try:
        response = panel_framework_view(
            config=interface_config,
            request=scoped_request,
            path_string=path_string,
            template_name="educator_interface/interface.html",
            url_name="educator_interface:interface",
        )
    except OrganisationScopeDenied:
        # Only a switch request gets the softened "wrong organisation"
        # reply — every other 404 from path resolution (unknown segment,
        # missing tab/panel/action, deleted object) must still propagate,
        # switch header or not.
        if not is_switch:
            raise
        section = path_string.split("/", 1)[0]
        section_model = interface_config[section].model
        # authorise_instance only ever raises OrganisationScopeDenied from a
        # config with a real model — get_instance_view (panel_framework/
        # views.py) requires one to resolve the detail view in the first
        # place — so this is an internal-consistency check, not a real
        # runtime path.
        if section_model is None:
            raise Http404 from None
        label = section_model._meta.verbose_name
        messages.info(
            request,
            f"Switched to {organisation.name} — that {label} isn't in this organisation",
        )
        scoped_request.path_string = section
        response = panel_framework_view(
            config=interface_config,
            request=scoped_request,
            path_string=section,
            template_name="educator_interface/interface.html",
            url_name="educator_interface:interface",
        )
        response["HX-Push-Url"] = reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": section},
        )

    return response
