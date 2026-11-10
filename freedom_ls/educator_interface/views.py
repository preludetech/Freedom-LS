from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Literal, NamedTuple, cast
from uuid import UUID, uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.core.paginator import Page, Paginator
from django.db import transaction
from django.db.models import (
    Count,
    F,
    Max,
    Model,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Subquery,
    Window,
    prefetch_related_objects,
)
from django.db.models.functions import RowNumber
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode

from freedom_ls.accounts.models import User
from freedom_ls.audit_log.actions import SUMMARY_ACTIONS
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.audit_log.writer import RUN_ROWS_KEPT, record_entry, subject_key
from freedom_ls.base.csv_import import (
    MAX_UPLOAD_BYTES,
    CsvImportError,
    write_error_csv,
)
from freedom_ls.comms.config import config as comms_config
from freedom_ls.comms.messaging import (
    decode_cursor,
    other_participant,
    refusal_alert_copy,
    send_message,
)
from freedom_ls.comms.messaging_views import (
    CONVERSATION_CHANGED,
    READ_ONLY_THREAD_ID,
    composer_context,
    older_page_response,
    posted_client_key,
    read_only_thread_context,
    thread_context,
)
from freedom_ls.comms.views import login_required_htmx_to
from freedom_ls.content_engine.models import Course, CoursePart
from freedom_ls.educator_interface.actions import (
    AddExistingLearnersAction,
    AddLearnerAction,
    AddLearnerToCohortAction,
    AddStaffMemberAction,
    AddStaffMemberToCohortAction,
    AddToCohortAction,
    ChangeCohortsAction,
    DeactivateCohortRegistrationAction,
    DeactivateRegistrationAction,
    DeactivateRoleAction,
    DeactivateStaffMemberAction,
    DeleteEmptyCohortAction,
    EditCohortAction,
    EditLearnerNameAction,
    ImportLearnersAction,
    MoveToCohortAction,
    ReactivateRegistrationAction,
    ReactivateStaffMemberAction,
    RegisterCohortForCourseAction,
    RegisterLearnerForCourseAction,
    RemoveFromCohortAction,
    ResendSetupEmailAction,
    bulk_actions_for_table,
    cohort_not_empty_sentence,
    cohort_state_actions,
    grantable_roles_for,
    learner_state_actions,
)
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
    REGISTRATION_CHANGED,
    STAFF_CHANGED,
)
from freedom_ls.educator_interface.exceptions import OrganisationScopeDenied
from freedom_ls.educator_interface.filters import (
    AuditActionFilter,
    AuditActorFilter,
    AuditPeriodFilter,
    LearnerCohortFilter,
    LearnerCourseFilter,
    LearnerStatusFilter,
    ShowInactiveFilter,
    StaffRoleFilter,
    VisibleCourseFilter,
)
from freedom_ls.educator_interface.forms import CohortForm, LearnerImportForm
from freedom_ls.educator_interface.learner_import import (
    ERROR_CSV_HEADER,
    FULL_EXAMPLE_ROW,
    HEADER_DESCRIPTIONS,
    HEADERS,
    NOT_ADDED_LABELS,
    PREVIEW_LABEL_TONES,
    REQUIRED_HEADERS,
    TEMPLATE_EXAMPLE_ROWS,
    check_import_gate,
    create_learner_import,
    error_reason,
    error_rows,
    run_learner_import,
)
from freedom_ls.educator_interface.messaging import (
    OwnConversation,
    other_educator_conversations,
    own_conversation_with,
)
from freedom_ls.educator_interface.paths import interface_path
from freedom_ls.educator_interface.quick_views import (
    CohortQuickView,
    LearnerQuickView,
)
from freedom_ls.educator_interface.reporting import (
    DOWNLOAD_COHORT_REPORT,
    CohortNeedsAttentionPanel,
    CohortReportStack,
    DashboardPanel,
    LearnerCoursesPanel,
)
from freedom_ls.educator_interface.staff import staff_role_entries
from freedom_ls.educator_interface.tasks import _run_learner_import_task
from freedom_ls.form_engine.conditions import full_path
from freedom_ls.form_engine.models import Form
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.config import config as learner_management_config
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    ImportLabel,
    ImportStatus,
    Learner,
    LearnerCourseRegistration,
    LearnerImport,
    LearnerImportRow,
    StaffMember,
)
from freedom_ls.learner_management.queries import (
    DELETE_COHORTMEMBERSHIP,
    STAFF_ROLES,
    VIEW_CONVERSATION,
    LearnerStatus,
    active_organisation_admins,
    cohort_counts,
    cohort_educators,
    cohorts_visible_to,
    courses_visible_to,
    learner_status,
    learners_visible_to,
    organisations_accessible_to,
    site_level_admins,
    staff_assignments,
    staff_of,
)
from freedom_ls.learner_management.role_assignment import GrantableRole
from freedom_ls.learner_management.utils import record_cohort_entry
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.actions import (
    CreateInstanceAction,
    PanelAction,
)
from freedom_ls.panel_framework.bulk_actions import BulkAction
from freedom_ls.panel_framework.config import config as panel_framework_config
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.filters import TableFilter
from freedom_ls.panel_framework.models import RunStatus
from freedom_ls.panel_framework.panels import (
    DataTablePanel,
    InstanceDetailsPanel,
    Panel,
    PanelStack,
    TabSet,
)
from freedom_ls.panel_framework.tables import (
    Column,
    DataTable,
    ExportColumn,
    TableQuery,
)
from freedom_ls.panel_framework.views import (
    BaseViewConfig,
    InstanceView,
    ListViewConfig,
    NavGroup,
    SectionConfigBase,
    StatusBadge,
    build_menu_items,
    panel_framework_view,
    sections_by_url_name,
)
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.services import report_file_response
from freedom_ls.role_based_permissions.loader import get_role_config
from freedom_ls.site_aware_models.models import get_cached_site

#: Session key remembering the educator's last-visited organisation, used
#: only to pick a default for the bare /educator/ redirect. Re-authorised on
#: every use — the session value is never trusted on its own.
LAST_ORGANISATION_SESSION_KEY = "educator_interface_last_organisation_slug"


class OrganisationScopedRequest(HttpRequest):
    """Typing-only view of a request after interface() has resolved and
    authorised an organisation onto it.

    panel_framework names none of these: the scope it enforces is whatever a
    config lists in required_request_attrs, and the title segment reads
    panel_scope_name. So this class exists purely so this module -- and
    quick_views.py, which imports it only under TYPE_CHECKING to avoid a
    runtime import cycle -- can type-check the attribute access without a
    type: ignore. Never instantiated; only used with cast().
    """

    organisation: Organisation
    panel_scope_name: str
    panel_url_kwargs: dict[str, str]
    accessible_organisations: list[Organisation]
    path_string: str
    panel_announcement: str
    panel_extra_oob: list[str]
    grantable_roles: list[GrantableRole]


class OrganisationSectionConfig(SectionConfigBase):
    """Shared by every section scoped to the organisation interface() resolves."""

    required_request_attrs = ("organisation",)

    @classmethod
    def get_scope(cls, request: HttpRequest) -> Model | None:
        return cast(OrganisationScopedRequest, request).organisation

    @classmethod
    def has_capability(
        cls, request: HttpRequest, capability: str, scope: Model
    ) -> bool:
        return can(request.user, capability, scope)

    @classmethod
    def get_denied_context(
        cls, request: HttpRequest, capability: str | None, scope: Model | None
    ) -> dict[str, str]:
        organisation = cast(OrganisationScopedRequest, request).organisation
        who = f"Ask an organisation admin of {organisation.name}."
        if can(
            request.user,
            "freedom_ls_learner_management.view_staffmember",
            organisation,
        ):
            names = [
                admin.display_name for admin in active_organisation_admins(organisation)
            ]
            if names:
                who = (
                    f"Ask an organisation admin of {organisation.name}: "
                    f"{', '.join(names)}."
                )
        return {"who_to_ask": who}


# TODO
# Data Tables
# top level filters (searchable dropdown)
#   use HTMX to only reload that one panel
# Bulk delete
# Export as csv
#
# instance edit
# instance, other actions (eg: send_email)


@dataclass
class RelationLinkColumn(Column):
    """A cell listing every related object in `relation_set`, each linked
    through `url_name`/`url_path_template` (inherited from `Column`) and
    resolved against `link_object_attr`."""

    relation_set: str = ""
    link_object_attr: str = ""
    link_text_attr: str = ""


def _interface_link(
    header: str,
    text_attr: str,
    path_template: str,
    *,
    sortable: bool = False,
    card: Literal["primary", "secondary", "md_only"] = "secondary",
    quick_view: bool = False,
    fallback_text_attr: str = "",
) -> Column:
    """A link column into the educator interface, the shape every table's
    name/title column shares. The link always navigates to the row's page;
    quick_view adds a trigger beside it that opens the row in the quick-view
    drawer instead."""
    return Column(
        header=header,
        template="cotton/data-table-cells/link.html",
        text_attr=text_attr,
        fallback_text_attr=fallback_text_attr,
        url_name="educator_interface:interface",
        url_path_template=path_template,
        htmx_nav=True,
        quick_view=quick_view,
        sortable=sortable,
        card=card,
    )


def _learner_column(attr: str = "") -> Column:
    """The shared learner cell. `attr` names the row's learner; empty means
    the row is the learner."""
    prefix = f"{attr}__" if attr else ""
    return Column(
        header="Learner",
        template="educator_interface/data-table-cells/learner.html",
        attr=attr,
        sortable=True,
        sort_field=f"{prefix}user__first_name",
        card="primary",
    )


def _registration_columns() -> list[Column]:
    """The Status/Registered columns the three registration tables share."""
    return [
        Column(
            header="Status",
            template="educator_interface/data-table-cells/active_status.html",
            attr="is_active",
        ),
        Column(
            header="Registered",
            template="cotton/data-table-cells/datetime.html",
            attr="registered_at",
            card="md_only",
        ),
    ]


class CohortDataTable(DataTable):
    empty_message = "No cohorts yet. Cohorts you create will appear here."
    empty_no_results = "No cohorts match these filters."
    search_fields = ["name"]
    default_sort = "name"

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        request = cast(OrganisationScopedRequest, request)
        return (
            cohorts_visible_to(request.user, request.organisation)
            .annotate(
                learner_count=Count(
                    "cohortmembership",
                    filter=Q(cohortmembership__learner__is_active=True),
                    distinct=True,
                ),
            )
            .prefetch_related(
                Prefetch(
                    "course_registrations",
                    queryset=CohortCourseRegistration.objects.filter(
                        is_active=True
                    ).select_related("course"),
                )
            )
            .order_by("name", "pk")
        )

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            _interface_link(
                "Name",
                "name",
                "cohorts/{pk}",
                sortable=True,
                card="primary",
                quick_view=True,
            ),
            Column(
                header="Status",
                template="educator_interface/data-table-cells/active_status.html",
                attr="is_active",
            ),
            Column(
                header="Learners",
                template="educator_interface/data-table-cells/learner_count.html",
                attr="learner_count",
                sortable=True,
            ),
            Column(
                header="Courses",
                template="educator_interface/data-table-cells/cohort_courses.html",
            ),
            Column(
                header="Created",
                template="cotton/data-table-cells/datetime.html",
                attr="created_at",
                sortable=True,
                card="md_only",
            ),
        ]

    @staticmethod
    def get_row_label(row: Model) -> str:
        return cast(Cohort, row).name

    @classmethod
    def get_filters(cls) -> list[TableFilter]:
        return [
            ShowInactiveFilter("inactive", "Show inactive"),
            VisibleCourseFilter(
                "course", "Course", lookup="course_registrations__course"
            ),
        ]

    @classmethod
    def filter_queryset(
        cls, request: HttpRequest, queryset: QuerySet, query: TableQuery
    ) -> QuerySet:
        # The toggle can only widen, so the table excludes inactive cohorts
        # itself whenever it offers the toggle and the toggle is unset.
        toggle = next(
            (f for f in cls.get_filters() if isinstance(f, ShowInactiveFilter)), None
        )
        if toggle is not None and toggle.key not in query.filters:
            queryset = queryset.filter(is_active=True)
        return super().filter_queryset(request, queryset, query)


class LearnerCohortDataTable(CohortDataTable):
    """The learner page's cohorts: every cohort the learner belongs to, active
    or not, with search, sort and pagination but no filters. `joined_at` is
    annotated by the panel that lists them."""

    empty_message = (
        "This learner is not in any cohorts yet. Their cohorts will appear here."
    )
    empty_no_results = "No cohorts match this search."

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            *CohortDataTable.get_columns(),
            Column(
                header="Joined",
                template="cotton/data-table-cells/datetime.html",
                attr="joined_at",
                sortable=True,
                card="md_only",
            ),
            Column(
                header="",
                template="educator_interface/data-table-cells/membership_actions.html",
                card="secondary",
            ),
        ]

    @classmethod
    def get_filters(cls) -> list[TableFilter]:
        return []


@dataclass(frozen=True)
class LearnerCourseSummary:
    """One course a learner reaches, with the furthest of their course
    progress records for it, or None when nothing has been minted yet."""

    course: Course
    progress_percentage: int | None


def learner_course_summaries(learner: Learner) -> list[LearnerCourseSummary]:
    """The courses a learner reaches through an active individual registration
    or an active registration of an active cohort, in the order found.

    Reads only the caches `LearnerDataTable.get_queryset` prefetches, so a
    page of learners costs the same number of queries as one learner.
    """
    courses: dict[UUID, Course] = {
        registration.course_id: registration.course
        for registration in learner.learnercourseregistration_set.all()
    }
    for membership in learner.cohortmembership_set.all():
        if not membership.cohort.is_active:
            continue
        for registration in membership.cohort.course_registrations.all():
            courses.setdefault(registration.course_id, registration.course)

    furthest: dict[UUID, int] = {}
    for record in learner.course_progress_records.all():
        furthest[record.course_id] = max(
            furthest.get(record.course_id, 0), record.progress_percentage
        )
    return [
        LearnerCourseSummary(course, furthest.get(course_id))
        for course_id, course in courses.items()
    ]


class LearnerDataTable(DataTable):
    empty_message = "No learners yet. Learners you add or import will appear here."
    empty_no_results = "No learners match these filters."
    search_fields = ["user__first_name", "user__last_name", "user__email"]
    default_sort = "user__first_name"

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        request = cast(OrganisationScopedRequest, request)
        organisation = request.organisation
        return (
            learners_visible_to(request.user, organisation, include_inactive=True)
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
                Prefetch(
                    "cohortmembership_set__cohort__course_registrations",
                    queryset=CohortCourseRegistration.objects.filter(
                        is_active=True
                    ).select_related("course"),
                ),
                Prefetch(
                    "learnercourseregistration_set",
                    queryset=LearnerCourseRegistration.objects.filter(
                        is_active=True
                    ).select_related("course"),
                ),
                "course_progress_records",
            )
            .annotate(last_active=Max("course_progress_records__last_accessed_time"))
            .order_by("user__first_name", "user__last_name")
        )

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            _learner_column(),
            Column(
                header="Status",
                template="educator_interface/data-table-cells/learner_status.html",
            ),
            RelationLinkColumn(
                header="Cohorts",
                template="educator_interface/data-table-cells/cohort_links.html",
                relation_set="cohortmembership_set.all",
                link_object_attr="cohort",
                link_text_attr="cohort.name",
                url_name="educator_interface:interface",
                url_path_template="cohorts/{pk}",
            ),
            Column(
                header="Courses",
                template="educator_interface/data-table-cells/learner_courses.html",
            ),
            Column(
                header="Last active",
                template="educator_interface/data-table-cells/learner_last_active.html",
                attr="last_active",
                sortable=True,
            ),
        ]

    @staticmethod
    def get_row_label(row: Model) -> str:
        return cast(Learner, row).user.display_name

    @staticmethod
    def get_filters() -> list[TableFilter]:
        return [
            LearnerStatusFilter(),
            LearnerCohortFilter("cohort", "Cohort", lookup=""),
            LearnerCourseFilter("course", "Course", lookup=""),
        ]

    @staticmethod
    def get_export_columns() -> list[ExportColumn]:
        # Every value reads the caches get_queryset prefetches or annotates,
        # so the export streams without a query per learner.
        return [
            ExportColumn("Name", "user.display_name"),
            ExportColumn("Email", "user.email"),
            ExportColumn(
                "Status", lambda row: learner_status(cast(Learner, row)).label
            ),
            ExportColumn(
                "Cohorts",
                lambda row: ", ".join(
                    membership.cohort.name
                    for membership in cast(Learner, row).cohortmembership_set.all()
                ),
            ),
            ExportColumn(
                "Courses",
                lambda row: ", ".join(
                    summary.course.title
                    for summary in learner_course_summaries(cast(Learner, row))
                ),
            ),
            ExportColumn("Last active", _last_active_cell),
        ]


def _last_active_cell(row: Model) -> str:
    """The annotated last_active as a date, matching the on-screen cell."""
    last_active = getattr(row, "last_active", None)
    if not isinstance(last_active, datetime):
        return ""
    return timezone.localtime(last_active).strftime("%Y-%m-%d")


class CohortLearnerDataTable(LearnerDataTable):
    """The cohort page's learners: the learners table plus a Remove cell."""

    empty_message = (
        "This cohort has no learners yet. Learners you add to it will appear here."
    )

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            *LearnerDataTable.get_columns(),
            Column(
                header="",
                template="educator_interface/data-table-cells/cohort_member_actions.html",
                card="secondary",
            ),
        ]


class LearnerDetailsPanel(Panel):
    model = Learner
    title = "Details"
    template_name = "educator_interface/panels/learner_details.html"
    refresh_events = (LEARNER_CHANGED,)

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context["learner"] = cast(Learner, self.instance)
        return context


class LearnerCohortsPanel(DataTablePanel):
    title = "Cohorts"
    data_table = LearnerCohortDataTable
    table_key = "cohorts"
    refresh_events = (LEARNER_CHANGED, COHORT_CHANGED)

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        joined_at = Subquery(
            CohortMembership.objects.filter(
                cohort=OuterRef("pk"), learner=self.instance
            ).values("created_at")[:1]
        )
        queryset: QuerySet = (
            super()
            .get_queryset(request)
            .filter(cohortmembership__learner=self.instance)
        )
        annotated: QuerySet = queryset.annotate(joined_at=joined_at)
        return annotated

    def get_actions(self) -> list[PanelAction]:
        # Add to cohort sits with the cohorts it changes; the row actions
        # render per row through row_action_urls.
        return [AddToCohortAction(), RemoveFromCohortAction(), MoveToCohortAction()]

    def get_context_data(self) -> dict[str, object]:
        request = cast(OrganisationScopedRequest, self.request)
        context = super().get_context_data()
        # A grant on only some of the learner's cohorts shows Remove on
        # those rows alone.
        context["manageable_cohort_ids"] = set(
            cohorts_visible_to(
                request.user,
                request.organisation,
                capability=DELETE_COHORTMEMBERSHIP,
            ).values_list("pk", flat=True)
        )
        return context


@dataclass(frozen=True)
class RegistrationRow:
    """One course the learner is registered for on the Registrations card.
    `via` is "Individual" or "via <cohort name>"."""

    course: Course
    via: str
    is_active: bool
    registration: LearnerCourseRegistration | CohortCourseRegistration

    @property
    def is_individual(self) -> bool:
        return isinstance(self.registration, LearnerCourseRegistration)


class LearnerRegistrationsPanel(Panel):
    model = Learner
    title = "Registrations"
    template_name = "educator_interface/panels/learner_registrations.html"
    refresh_events = (LEARNER_CHANGED, REGISTRATION_CHANGED)

    def get_actions(self) -> list[PanelAction]:
        return [
            DeactivateRegistrationAction(),
            ReactivateRegistrationAction(),
        ]

    def get_context_data(self) -> dict[str, object]:
        learner = cast(Learner, self.instance)
        request = cast(OrganisationScopedRequest, self.request)
        visible_cohorts = cohorts_visible_to(request.user, request.organisation)
        individual = LearnerCourseRegistration.objects.filter(
            learner=learner
        ).select_related("course")
        # A registration through an inactive cohort is not shown at all; the
        # learner reaches that course only while the cohort is active.
        through_cohorts = CohortCourseRegistration.objects.filter(
            cohort__in=visible_cohorts,
            cohort__is_active=True,
            cohort__cohortmembership__learner=learner,
        ).select_related("course", "cohort")
        rows = [
            RegistrationRow(r.course, "Individual", r.is_active, r) for r in individual
        ] + [
            RegistrationRow(r.course, f"via {r.cohort.name}", r.is_active, r)
            for r in through_cohorts
        ]
        context = super().get_context_data()
        context["rows"] = sorted(rows, key=lambda row: row.course.title)
        return context


class LearnerOverviewStack(PanelStack):
    """No refresh events of its own: each child re-fetches itself on
    LEARNER_CHANGED, so a stack refresh would render them all twice."""

    title = "Overview"
    children = {
        "details": LearnerDetailsPanel,
        "cohorts": LearnerCohortsPanel,
        "registrations": LearnerRegistrationsPanel,
    }


class LearnerCoursesStack(PanelStack):
    title = "Courses"
    refresh_events = (LEARNER_CHANGED,)
    children = {"courses": LearnerCoursesPanel}


#: Target models that are a person: the user pk is the target itself, or the row's user.
_PERSON_TARGETS: tuple[type[User] | type[Learner] | type[StaffMember], ...] = (
    User,
    Learner,
    StaffMember,
)


def _attach_target_users(entries: Sequence[AuditLogEntry]) -> None:
    """Set `target_is_person` and `target_user_pk` on every entry.

    A person target gets the live user's pk (None once the row is gone, so
    the template shows the neutral circle beside the stored label); any
    other target is not a person and renders as plain text. Keyed on the
    stored content type id against the registry's ids, so no entry's
    `target_content_type` relation is read, and one lookup per model type
    regardless of the page size. No `is_active` filter: an inactive user
    keeps their avatar.
    """
    person_models_by_type_id = {
        ContentType.objects.get_for_model(model).pk: model for model in _PERSON_TARGETS
    }
    by_model: dict[
        type[User] | type[Learner] | type[StaffMember], list[AuditLogEntry]
    ] = {}
    for entry in entries:
        model = person_models_by_type_id.get(entry.target_content_type_id)
        entry.target_is_person = model is not None
        entry.target_user_pk = None
        if model is not None:
            by_model.setdefault(model, []).append(entry)
    for model, typed in by_model.items():
        user_field = "pk" if model is User else "user_id"
        rows = model.objects.filter(pk__in={entry.target_object_id for entry in typed})
        found = {str(pk): user_pk for pk, user_pk in rows.values_list("pk", user_field)}
        for entry in typed:
            entry.target_user_pk = found.get(entry.target_object_id)


def _export_when(row: Model) -> str:
    return timezone.localtime(cast(AuditLogEntry, row).created_at).isoformat()


def _export_who(row: Model) -> str:
    return cast(AuditLogEntry, row).actor_label or "System"


def _export_run_id(row: Model) -> str:
    run_id = cast(AuditLogEntry, row).run_id
    return "" if run_id is None else str(run_id)


class AuditLogEntryTable(DataTable):
    """A log: sortable on when, who and what, and filterable on the same
    three, wherever it appears (the organisation's Audit log and every
    History tab alike). The model's own ordering is newest first, which
    default_sort names so the When header reads as sorted that way."""

    page_size = 25
    card_template = "educator_interface/partials/audit_log_card.html"
    default_sort = "-created_at"
    noun = "entries"
    noun_singular = "entry"
    empty_message = "Nothing has been recorded yet."
    empty_no_results = "No entries match these filters."

    row_detail_template = "educator_interface/partials/audit_row_detail.html"

    @staticmethod
    def get_row_label(row: Model) -> str:
        entry = cast(AuditLogEntry, row)
        return f"{entry.label}: {entry.target_label}"

    @staticmethod
    def has_row_detail(row: Model) -> bool:
        entry = cast(AuditLogEntry, row)
        return bool(
            entry.description or entry.reason or getattr(entry, "run_entries", [])
        )

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        organisation = cast(OrganisationScopedRequest, request).organisation
        return AuditLogEntry.objects.filter(organisation=organisation)

    @classmethod
    def get_rows(
        cls, request: HttpRequest, queryset: QuerySet, query: TableQuery
    ) -> Page:
        page_obj = super().get_rows(request, queryset, query)
        _attach_target_users(list(page_obj.object_list))
        return page_obj

    @staticmethod
    def get_filters() -> list[TableFilter]:
        return [AuditActorFilter(), AuditActionFilter(), AuditPeriodFilter()]

    @staticmethod
    def get_export_columns() -> list[ExportColumn]:
        # The screen names a column once; a column only the CSV carries is
        # named for the field it holds. `actor.email` reads the actor the
        # export queryset select_relates, and is empty once the actor is gone.
        return [
            ExportColumn("When", _export_when),
            ExportColumn("Who", _export_who),
            ExportColumn("Actor email", "actor.email"),
            ExportColumn("What", "label"),
            ExportColumn("Action", "action"),
            ExportColumn("Target", "target_label"),
            ExportColumn("Description", "description"),
            ExportColumn("Reason", "reason"),
            ExportColumn("Run ID", _export_run_id),
        ]

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            Column(
                header="When",
                template="cotton/data-table-cells/datetime.html",
                attr="created_at",
                sortable=True,
                cell_class="whitespace-nowrap py-2",
            ),
            Column(
                header="Who",
                template="educator_interface/data-table-cells/audit_who.html",
                sortable=True,
                sort_field="actor_label",
                cell_class="py-2",
            ),
            Column(
                header="What",
                template="educator_interface/data-table-cells/audit_what.html",
                card="primary",
                sortable=True,
                sort_field="action",
                # The description is clipped inside this width rather than
                # widening the table past its wrapper.
                cell_class="max-w-md py-2",
            ),
        ]


class TargetedAuditLogEntryTable(AuditLogEntryTable):
    """Audit log entries that may be about different objects, so each row names its target."""

    card_template = "educator_interface/partials/audit_log_card_targeted.html"

    @staticmethod
    def get_columns() -> list[Column]:
        when, who, what = AuditLogEntryTable.get_columns()
        target = Column(
            header="Target",
            template="educator_interface/data-table-cells/audit_target.html",
            sortable=True,
            sort_field="target_label",
            cell_class="py-2",
        )
        return [when, who, what, target]


def _record_export(
    request: HttpRequest,
    rows: QuerySet,
    *,
    table: type[AuditLogEntryTable],
    table_key: str,
    scope: str,
    scope_label: str,
) -> QuerySet:
    """Write the entry for an audit log export and return the rows without it.

    The count is taken now, at request time, so the entry describes what the
    person asked for even if rows are written while the CSV streams. The
    entry targets the organisation, so it appears on the organisation's
    Audit log and on neither History tab. Excluding its pk keeps a CSV from
    containing a record of its own download.
    """
    scoped = cast(OrganisationScopedRequest, request)
    query = table.parse_query(request, table_key)
    entry = record_entry(
        action="audit_log.exported",
        actor=cast(User, request.user),
        target=scoped.organisation,
        target_label=scoped.organisation.name,
        organisation=scoped.organisation,
        details={
            "scope": scope,
            "scope_label": scope_label,
            "count": rows.count(),
            "filters": ", ".join(table.applied_filter_text(request, query)),
        },
    )
    return rows.exclude(pk=entry.pk)


class HistoryPanel(DataTablePanel):
    """The History tab of one learner or cohort: every entry whose subjects name it."""

    title = "History"
    data_table = AuditLogEntryTable
    table_key = "history"
    capability = "freedom_ls_audit_log.view_auditlogentry"
    empty_message: str
    #: What the export's entry says it covered: "learner" or "cohort".
    export_scope: str

    @property
    def scope_label(self) -> str:
        """The learner's or cohort's name, for the entry and the filename."""
        raise NotImplementedError

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context["empty_message"] = self.empty_message
        return context

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return (
            super()
            .get_queryset(request)
            .filter(subjects__contains=[subject_key(cast(Model, self.instance))])
        )

    def get_export_queryset(self, request: HttpRequest) -> QuerySet:
        return self.get_queryset(request).select_related("actor")

    def get_export_scope_slug(self, request: HttpRequest) -> str:
        return self.scope_label

    def before_export(self, request: HttpRequest, rows: QuerySet) -> QuerySet:
        return _record_export(
            request,
            rows,
            table=self.data_table,
            table_key=self.table_key,
            scope=self.export_scope,
            scope_label=self.scope_label,
        )


class LearnerHistoryPanel(HistoryPanel):
    model = Learner
    export_scope = "learner"
    refresh_events = (LEARNER_CHANGED,)
    empty_message = (
        "No history for this learner yet. Actions such as moving or "
        "deactivating them are recorded here."
    )

    @property
    def scope_label(self) -> str:
        return cast(Learner, self.instance).user.display_name


class LearnerMessagesPanel(Panel):
    """The learner's Messages tab: the educator's own conversation with them.

    It declares no refresh events: a re-fetch would mark the thread read again
    for nothing, and the thread polls for new messages itself.
    """

    model = Learner
    title = "Messages"
    template_name = "educator_interface/panels/learner_messages.html"
    card_flush = True

    def has_permission(self, request: HttpRequest) -> bool:
        return comms_config.MESSAGING_ENABLED and super().has_permission(request)

    def get_actions(self) -> list[PanelAction]:
        return [SendToLearnerAction(), ViewConversationAction()]

    def get_context_data(
        self,
        *,
        own: OwnConversation | None = None,
        draft: str = "",
        client_key: UUID | None = None,
        alert: str = "",
    ) -> dict[str, object]:
        """The tab's context. ``own`` is the educator's side when the caller
        has already looked it up. The other keyword arguments re-render the
        tab after a refused send with the educator's draft and the refusal,
        which shows even when the policy no longer lets them write."""
        context = super().get_context_data()
        learner = cast(Learner, self.instance)
        if own is None:
            own = own_conversation_with(self.request, learner)
        may_write = own.allowed or bool(alert)
        context["learner"] = learner
        context["own_shown"] = own.conversation is not None or may_write
        if own.conversation is not None:
            context.update(thread_context(self.request, own.conversation))
            context.pop("back_url")
        else:
            context["other"] = learner.user
        if may_write:
            context["composer"] = composer_context(
                client_key=client_key or uuid4(),
                draft=draft,
                alert=alert,
                conversation=own.conversation,
                recipient=None if own.conversation is not None else learner.user,
                action_url=SendToLearnerAction().get_action_url(self.ctx),
                swap_target=self.region_id,
            )
        row_action_urls = cast(dict[str, str], context["row_action_urls"])
        if ViewConversationAction.action_name in row_action_urls:
            rows = other_educator_conversations(cast(User, self.request.user), learner)
            context["oversight_rows"] = [
                (c, other_participant(c, learner.user)) for c in rows
            ]
        return context


class SendToLearnerAction(PanelAction):
    """The Messages tab's composer posts here, so the answer is the tab itself
    re-rendered, never a redirect to the messages page."""

    action_name = "send"
    renders_in_footer = False

    def has_permission(self, ctx: PanelContext) -> bool:
        return comms_config.MESSAGING_ENABLED and super().has_permission(ctx)

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        request = ctx.request
        learner = cast(Learner, ctx.instance)
        own = own_conversation_with(request, learner)
        client_key = posted_client_key(request)
        draft = request.POST.get("body", "")
        result = send_message(
            sender=cast(User, request.user),
            body=draft,
            client_key=client_key,
            site=cast(Site, get_cached_site(request)),
            conversation=own.conversation,
            recipient=None if own.conversation is not None else learner.user,
        )
        panel = LearnerMessagesPanel(ctx)
        if result.message is not None:
            # A first send created the conversation, so look it up afresh.
            response = render(
                request,
                panel.template_name,
                panel.get_context_data(
                    own=own if own.conversation is not None else None
                ),
            )
            response["HX-Trigger"] = CONVERSATION_CHANGED
            return response
        alert = result.body_error or refusal_alert_copy(result.refusal, learner.user)
        return render(
            request,
            panel.template_name,
            panel.get_context_data(
                own=own, draft=draft, client_key=client_key, alert=alert
            ),
            status=422,
        )


class ViewConversationAction(PanelAction):
    """Opens one of the learner's educator conversations read-only in the app
    modal, for someone who holds oversight of the learner. Every open is
    recorded in the learner's history, so only the page's own htmx request
    may open one: a plain GET from a prefetch or a cross-site tag must not
    leave a false entry."""

    action_name = "view_conversation"
    capability = VIEW_CONVERSATION
    renders_in_footer = False
    template_name = "educator_interface/modal/conversation_oversight.html"

    def has_permission(self, ctx: PanelContext) -> bool:
        return comms_config.MESSAGING_ENABLED and super().has_permission(ctx)

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        request = ctx.request
        if request.headers.get("HX-Request") != "true":
            raise Http404
        learner = cast(Learner, ctx.instance)
        viewer = cast(User, request.user)
        conversation = get_object_or_404(
            other_educator_conversations(viewer, learner),
            pk=uuid_or_404(request.GET.get("conversation")),
        )
        educator = other_participant(conversation, learner.user)
        record_entry(
            action="conversation.viewed",
            actor=viewer,
            target=conversation,
            target_label=(
                f"Conversation with {educator.display_name if educator else 'Deleted user'}"
            ),
            organisation=learner.organisation,
            subjects=[learner],
        )
        return {
            **read_only_thread_context(
                conversation,
                other=educator,
                older_url=reverse(
                    "educator_interface:oversight_thread_older",
                    kwargs={
                        "organisation_slug": learner.organisation.slug,
                        "learner_pk": str(learner.pk),
                        "conversation_pk": str(conversation.pk),
                    },
                ),
            ),
            "viewer_role_label": _oversight_role_label(viewer, learner),
        }

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        # Opening is a read; there is nothing to submit.
        raise Http404


def uuid_or_404(raw: str | None) -> UUID:
    """A pk from a query string or a URL; a 404 when it is not a UUID."""
    try:
        return UUID(raw or "")
    except ValueError:
        raise Http404("not a uuid") from None


def _oversight_role_label(viewer: User, learner: Learner) -> str:
    """How the read-only banner names the viewer's access: a site admin reads
    through the site grant, anyone else holding the permission is an
    organisation admin of the learner's organisation."""
    if site_level_admins(learner.site).filter(pk=viewer.pk).exists():
        return "a site admin"
    return "an organisation admin"


class LearnerSettingsPanel(Panel):
    """The learner's Settings tab: the actions with no home of their own
    (name, setup email, active state). Add to cohort lives on the Cohorts
    panel and Register for a course on the Courses tab, beside what they
    change. Shown to anyone who may take at least one action."""

    model = Learner
    title = "Settings"
    template_name = "educator_interface/panels/learner_settings.html"
    refresh_events = (LEARNER_CHANGED,)

    def has_permission(self, request: HttpRequest) -> bool:
        return super().has_permission(request) and bool(self.available_actions)

    def get_actions(self) -> list[PanelAction]:
        return settings_actions(cast(Learner, self.instance))

    def get_context_data(self) -> dict[str, object]:
        learner = cast(Learner, self.instance)
        context = super().get_context_data()
        context["learner"] = learner
        context["status"] = learner_status(learner)
        return context


def settings_actions(learner: Learner) -> list[PanelAction]:
    """The Settings tab's actions on one learner, in the order it offers
    them: those with no home beside the thing they change."""
    return [
        EditLearnerNameAction(learner),
        ResendSetupEmailAction(),
        *learner_state_actions(),
    ]


def learner_actions(learner: Learner) -> list[PanelAction]:
    """Every action on one learner, so each keeps its instance-level URL.
    The Settings tab, the Cohorts panel and the Courses tab draw the
    triggers; the page header draws none."""
    return [
        *settings_actions(learner),
        AddToCohortAction(),
        RegisterLearnerForCourseAction(),
    ]


class LearnerTabSet(TabSet):
    title = "Learner sections"
    children = {
        "overview": LearnerOverviewStack,
        "courses": LearnerCoursesStack,
        "messages": LearnerMessagesPanel,
        "settings": LearnerSettingsPanel,
        "history": LearnerHistoryPanel,
    }


class LearnerInstanceView(InstanceView):
    panel = LearnerTabSet
    header_refresh_events = (LEARNER_CHANGED,)

    def get_status_badge(self) -> StatusBadge | None:
        """Active is the default state, so only Pending and Inactive show."""
        learner = cast(Learner, self.instance)
        if learner_status(learner) is LearnerStatus.ACTIVE:
            return None
        return learner_status_badge(learner)

    def get_subtitle(self) -> str:
        return cast(Learner, self.instance).user.email

    def get_actions(self) -> list[PanelAction]:
        # The actions keep their instance-level URLs; the Settings tab
        # draws their triggers, so the header draws none.
        return learner_actions(cast(Learner, self.instance))

    def get_header_actions(self) -> list[PanelAction]:
        return []


_LEARNER_STATUS_TONES: dict[LearnerStatus, str] = {
    LearnerStatus.ACTIVE: "success",
    LearnerStatus.PENDING: "info",
    LearnerStatus.INACTIVE: "muted",
}


def learner_status_badge(learner: Learner) -> StatusBadge:
    """The badge for a learner's status: Active, Pending or Inactive."""
    status = learner_status(learner)
    return StatusBadge(_LEARNER_STATUS_TONES[status], status.label)


def active_status_badge(is_active: bool) -> StatusBadge:
    """The badge for an `is_active` flag, matching `<c-active-status-badge>`."""
    if is_active:
        return StatusBadge("success", "Active")
    return StatusBadge("muted", "Inactive")


def inactive_badge(is_active: bool) -> StatusBadge | None:
    """A page header's badge for an `is_active` flag: Active is the default
    state and shows nothing, so only Inactive is drawn."""
    if is_active:
        return None
    return StatusBadge("muted", "Inactive")


class CohortDetailsPanel(Panel):
    model = Cohort
    title = "Details"
    template_name = "educator_interface/panels/cohort_details.html"
    refresh_events = (COHORT_CHANGED,)

    def get_context_data(self) -> dict[str, object]:
        cohort = cast(Cohort, self.instance)
        context = super().get_context_data()
        context["cohort"] = cohort
        counts = cohort_counts(cohort)
        context["cohort_learner_count"] = counts.learners
        context["cohort_course_count"] = counts.courses
        return context


class CohortCourseRegistrationDataTable(DataTable):
    empty_message = "This cohort is not registered for any courses yet. Its course registrations will appear here."
    empty_no_results = "No course registrations match these filters."

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        request = cast(OrganisationScopedRequest, request)
        visible_cohorts = cohorts_visible_to(request.user, request.organisation)
        return (
            CohortCourseRegistration.objects.select_related("course", "cohort")
            .filter(cohort__in=visible_cohorts)
            .order_by("course__title")
        )

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            _interface_link(
                "Course", "course.title", "courses/{course.pk}", card="primary"
            ),
            *_registration_columns(),
            Column(
                header="",
                template="educator_interface/data-table-cells/deactivate_registration.html",
                card="secondary",
            ),
        ]


class CohortLearnersPanel(DataTablePanel):
    title = "Learners"
    data_table = CohortLearnerDataTable
    table_key = "learners"
    refresh_events = (COHORT_CHANGED,)

    def get_actions(self) -> list[PanelAction]:
        return [
            AddExistingLearnersAction(),
            AddLearnerToCohortAction(),
            ImportLearnersAction(),
            RemoveFromCohortAction(),
            MoveToCohortAction(),
        ]

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context["cohort_is_active"] = cast(Cohort, self.instance).is_active
        return context

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return (
            super().get_queryset(request).filter(cohortmembership__cohort=self.instance)
        )

    def get_export_scope_slug(self, request: HttpRequest) -> str:
        return cast(Cohort, self.instance).name

    def get_tab_count(self) -> int | None:
        # The table lists inactive learners too; the tab counts current ones.
        return self.get_queryset(self.request).filter(is_active=True).count()


class CohortCoursesPanel(DataTablePanel):
    title = "Courses"
    data_table = CohortCourseRegistrationDataTable
    table_key = "cohort_courses"
    refresh_events = (COHORT_CHANGED, REGISTRATION_CHANGED)

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).filter(cohort=self.instance)

    def get_actions(self) -> list[PanelAction]:
        # Deactivate renders per row, not in the footer: the registration cell
        # reads its URL from row_action_urls.
        return [RegisterCohortForCourseAction(), DeactivateCohortRegistrationAction()]

    def get_tab_count(self) -> int | None:
        return self.get_queryset(self.request).filter(is_active=True).count()


@dataclass(frozen=True)
class CourseCompletion:
    """How far one course registration's current members have got."""

    course: Course
    completed_count: int
    record_count: int
    percentage: int


class CohortCourseCompletionPanel(Panel):
    model = Cohort
    title = "Course completion"
    template_name = "educator_interface/panels/cohort_course_completion.html"
    refresh_events = (COHORT_CHANGED, REGISTRATION_CHANGED)

    def get_context_data(self) -> dict[str, object]:
        cohort = cast(Cohort, self.instance)
        # Course progress records minted for members who have since been
        # deactivated or have left the cohort are kept for ever, so the counts are
        # narrowed to current, active members or they would disagree with the
        # Learners tab.
        current_member = Q(
            course_progress_records__learner__is_active=True,
            course_progress_records__learner__cohortmembership__cohort_id=F(
                "cohort_id"
            ),
        )
        registrations = (
            cohort.course_registrations.filter(is_active=True)
            .select_related("course")
            .annotate(
                record_count=Count(
                    "course_progress_records", filter=current_member, distinct=True
                ),
                completed_count=Count(
                    "course_progress_records",
                    filter=current_member
                    & Q(course_progress_records__completed_time__isnull=False),
                    distinct=True,
                ),
            )
            .order_by("course__title")
        )
        context = super().get_context_data()
        context["completions"] = [
            CourseCompletion(
                course=registration.course,
                completed_count=registration.completed_count,
                record_count=registration.record_count,
                percentage=(
                    registration.completed_count * 100 // registration.record_count
                    if registration.record_count
                    else 0
                ),
            )
            for registration in registrations
        ]
        return context


class CohortSettingsPanel(Panel):
    """The cohort's Settings tab: its name as a field, its staff with the
    Add button, and the state and delete actions in the footer. Everything
    that changes the cohort itself, in one place."""

    title = "Settings"
    capability = "freedom_ls_learner_management.change_cohort"
    template_name = "educator_interface/panels/cohort_settings.html"
    refresh_events = (COHORT_CHANGED, STAFF_CHANGED)

    def get_actions(self) -> list[PanelAction]:
        cohort = cast(Cohort, self.instance)
        return [
            EditCohortAction(
                form_class=CohortForm,
                form_title=f"Edit {cohort}",
                instance=cohort,
                success_events=(COHORT_CHANGED,),
            ),
            AddStaffMemberToCohortAction(),
            *cohort_state_actions(),
            DeleteEmptyCohortAction(
                success_url=interface_path(cohort.organisation, "cohorts"),
            ),
        ]

    def get_context_data(self) -> dict[str, object]:
        cohort = cast(Cohort, self.instance)
        context = super().get_context_data()
        by_name = {action.action_name: action for action in self.available_actions}
        edit = by_name.get("edit")
        context["cohort"] = cohort
        context["rename"] = edit.get_context_data(self.ctx) if edit else None
        context["add_staff"] = by_name.get("add_staff_member")
        context["educators"] = cohort_educators(cohort)
        context["not_empty_sentence"] = cohort_not_empty_sentence(cohort)
        context["is_empty"] = not context["not_empty_sentence"]
        return context


class CohortOverviewStack(PanelStack):
    title = "Overview"
    refresh_events = (COHORT_CHANGED,)
    children = {
        "details": CohortDetailsPanel,
        "completion": CohortCourseCompletionPanel,
        "attention": CohortNeedsAttentionPanel,
    }


class CohortHistoryPanel(HistoryPanel):
    model = Cohort
    data_table = TargetedAuditLogEntryTable
    # A role assigned from the Educators panel is a cohort entry too.
    refresh_events = (COHORT_CHANGED, STAFF_CHANGED)
    export_scope = "cohort"
    empty_message = "No history for this cohort yet. Actions such as adding learners or registering it for a course are recorded here."

    @property
    def scope_label(self) -> str:
        return cast(Cohort, self.instance).name


class CohortTabSet(TabSet):
    title = "Cohort sections"
    children = {
        "overview": CohortOverviewStack,
        "learners": CohortLearnersPanel,
        "courses": CohortCoursesPanel,
        "report": CohortReportStack,
        "settings": CohortSettingsPanel,
        "history": CohortHistoryPanel,
    }


class CohortInstanceView(InstanceView):
    panel = CohortTabSet
    header_refresh_events = (COHORT_CHANGED,)

    def get_status_badge(self) -> StatusBadge | None:
        return inactive_badge(cast(Cohort, self.instance).is_active)

    def get_actions(self) -> list[PanelAction]:
        # The actions keep their instance-level URLs; the Settings tab draws
        # their triggers, so the header draws none. The instance already
        # carries its own organisation, so the success URL needs nothing
        # from the request.
        cohort = cast(Cohort, self.instance)
        return [
            EditCohortAction(
                form_class=CohortForm,
                form_title=f"Edit {cohort}",
                instance=cohort,
                success_events=(COHORT_CHANGED,),
            ),
            *cohort_state_actions(),
        ]

    def get_header_actions(self) -> list[PanelAction]:
        return []


class CreateCohortAction(CreateInstanceAction):
    label = "Create cohort"
    form_class = CohortForm
    form_title = "Create cohort"
    action_name = "create_cohort"
    success_events = (COHORT_CHANGED,)

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
        organisation = cast(OrganisationScopedRequest, request).organisation
        cast(Cohort, form.instance).organisation = organisation
        self._organisation = organisation
        return form

    def get_success_url(self, instance: Model) -> str:
        return interface_path(self._organisation, f"cohorts/{instance.pk}")

    def form_valid(self, request: HttpRequest, form: forms.ModelForm) -> HttpResponse:
        with transaction.atomic():
            response = super().form_valid(request, form)
            record_cohort_entry(
                cast(Cohort, form.instance), "cohort.created", cast(User, request.user)
            )
        return response


class CohortConfig(OrganisationSectionConfig, ListViewConfig):
    url_name = "cohorts"
    menu_label = "Cohorts"
    icon = "cohort"
    model = Cohort
    list_view = CohortDataTable
    table_key = "cohorts"
    instance_view = CohortInstanceView
    refresh_events = (COHORT_CHANGED,)
    quick_view = CohortQuickView

    @classmethod
    def get_actions(cls, request: HttpRequest) -> list[PanelAction]:
        return [CreateCohortAction()]

    @classmethod
    def get_bulk_actions(cls, request: HttpRequest) -> list[BulkAction]:
        return list(bulk_actions_for_table(cls.table_key))

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        organisation = cast(OrganisationScopedRequest, request).organisation
        if (
            not cohorts_visible_to(request.user, organisation)
            .filter(pk=instance.pk)
            .exists()
        ):
            raise OrganisationScopeDenied


class LearnerConfig(OrganisationSectionConfig, ListViewConfig):
    url_name = "learners"
    menu_label = "Learners"
    icon = "user"
    model = Learner
    list_view = LearnerDataTable
    table_key = "learners"
    instance_view = LearnerInstanceView
    refresh_events = (LEARNER_CHANGED,)
    quick_view = LearnerQuickView

    @classmethod
    def get_actions(cls, request: HttpRequest) -> list[PanelAction]:
        return [AddLearnerAction(), ImportLearnersAction()]

    @classmethod
    def get_bulk_actions(cls, request: HttpRequest) -> list[BulkAction]:
        return list(bulk_actions_for_table(cls.table_key))

    @classmethod
    def get_instance_label(cls, instance: Model) -> str:
        return cast(Learner, instance).user.display_name

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        organisation = cast(OrganisationScopedRequest, request).organisation
        if (
            not learners_visible_to(request.user, organisation, include_inactive=True)
            .filter(pk=instance.pk)
            .exists()
        ):
            raise OrganisationScopeDenied


class CourseDataTable(DataTable):
    empty_message = (
        "No courses yet. Courses open to this organisation will appear here."
    )
    empty_no_results = "No courses match these filters."

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        # Most courses are shared across the site, and a course that belongs
        # to organisations is listed only for the ones it is open to. The
        # list, the counts and the cells are all read through the organisation
        # in view: the cohorts and learners counted and linked on each row are
        # narrowed to what this educator may see, and another organisation's
        # cohorts never show through a shared course.
        scoped = cast(OrganisationScopedRequest, request)
        visible_cohorts = cohorts_visible_to(scoped.user, scoped.organisation)
        visible_learners = learners_visible_to(scoped.user, scoped.organisation)
        qs: QuerySet = (
            courses_visible_to(scoped.user, scoped.organisation)
            .annotate(
                cohort_count=Count(
                    "cohort_registrations",
                    filter=Q(cohort_registrations__is_active=True)
                    & Q(cohort_registrations__cohort__is_active=True)
                    & Q(cohort_registrations__cohort__in=visible_cohorts),
                    distinct=True,
                ),
                direct_learner_count=Count(
                    "learner_registrations",
                    filter=Q(learner_registrations__is_active=True)
                    & Q(learner_registrations__learner__in=visible_learners),
                    distinct=True,
                ),
                interest_count=Count("interests", distinct=True),
            )
            .prefetch_related(
                Prefetch(
                    "cohort_registrations",
                    queryset=CohortCourseRegistration.objects.filter(
                        cohort__in=visible_cohorts, cohort__is_active=True
                    ).prefetch_related("cohort__cohortmembership_set__learner"),
                ),
                Prefetch(
                    "learner_registrations",
                    queryset=LearnerCourseRegistration.objects.filter(
                        learner__in=visible_learners
                    ).select_related("learner"),
                ),
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
        cls, request: HttpRequest, queryset: QuerySet, query: TableQuery
    ) -> Page:
        page_obj = super().get_rows(request, queryset, query)
        cls._annotate_total_learner_count(page_obj)
        return page_obj

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            _interface_link("Title", "title", "courses/{pk}", card="primary"),
            Column(
                header="Visibility",
                template="cotton/data-table-cells/text.html",
                attr="get_visibility_display",
            ),
            Column(
                header="Interest",
                template="cotton/data-table-cells/text.html",
                attr="interest_count",
                card="md_only",
            ),
            Column(
                header="Active Learners",
                template="cotton/data-table-cells/text.html",
                attr="total_learner_count",
            ),
            Column(
                header="Active Cohorts",
                template="cotton/data-table-cells/text.html",
                attr="cohort_count",
                card="md_only",
            ),
            RelationLinkColumn(
                header="Cohorts",
                template="educator_interface/data-table-cells/cohort_links.html",
                relation_set="cohort_registrations.all",
                link_object_attr="cohort",
                link_text_attr="cohort.name",
                url_name="educator_interface:interface",
                url_path_template="cohorts/{pk}",
            ),
        ]


class CourseDetailsPanel(InstanceDetailsPanel):
    model = Course
    fields = [
        "title",
        "subtitle",
        "dashboard_category",
        "get_visibility_display",
        "get_difficulty_display",
        "display_estimated_duration",
        "display_time_limit",
        "learning_outcomes",
        "lesson_count",
    ]
    # The learner details page's words, so an educator and a learner
    # read the same label for the same fact.
    labels: ClassVar[dict[str, str]] = {
        "get_visibility_display": "Visibility",
        "get_difficulty_display": "Level",
        "display_estimated_duration": "Duration",
        "display_time_limit": "Time limit",
        "lesson_count": "Lessons",
    }

    def get_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for name, row in zip(self.fields, super().get_rows(), strict=True):
            if row["value"] in ("", self.empty_value_display):
                continue
            rows.append({**row, "label": self.labels.get(name, row["label"])})
        return rows


class CourseContentPanel(Panel):
    model = Course
    title = "Course content"
    template_name = "educator_interface/panels/course_content.html"

    def get_context_data(self) -> dict[str, object]:
        course = cast(Course, self.instance)
        return {
            **super().get_context_data(),
            "course": course,
            "outline": course.collection_items(),
        }

    def get_actions(self) -> list[PanelAction]:
        return [PreviewContentAction()]


def _form_preview_context(form: Form) -> dict[str, object]:
    """Every page of the form, on or off any condition, laid out the way
    the form page partial expects, with no sitting behind it."""
    # A conditional page's heading names the question its condition is on.
    prefetch_related_objects([form], "pages__condition_option__question")
    path = full_path(form)
    return {
        "form": form,
        "preview_pages": [
            {"page": page, "page_children": path.children_of(page)}
            for page in path.pages
        ],
        "question_positions": path.question_positions(),
        "existing_answers": {},
        "rejected_answers": {},
        "read_only": True,
        "show_answer_key": True,
    }


class PreviewContentAction(PanelAction):
    """Shows one child of the course read-only in the app modal. The
    target is found among the authorised course's own collection items,
    so an id from any other course is as missing as a made-up one."""

    action_name = "preview_content"
    capability = None
    renders_in_footer = False
    template_name = "educator_interface/modal/content_preview.html"

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        if ctx.request.headers.get("HX-Request") != "true":
            raise Http404
        course = cast(Course, ctx.instance)
        pk = uuid_or_404(ctx.request.GET.get("item"))
        collection_item = next(
            (item for item in course.collection_items_flat() if item.pk == pk), None
        )
        if collection_item is None or isinstance(collection_item.child, CoursePart):
            raise Http404
        context: dict[str, object] = {
            "collection_item": collection_item,
            "child": collection_item.child,
        }
        if isinstance(collection_item.child, Form):
            context.update(_form_preview_context(collection_item.child))
        return context

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        # Opening is a read; there is nothing to submit.
        raise Http404


class CourseCohortRegistrationDataTable(DataTable):
    empty_message = "No cohorts are registered for this course yet. Cohort registrations will appear here."
    empty_no_results = "No cohort registrations match these filters."

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        organisation = cast(OrganisationScopedRequest, request).organisation
        return (
            CohortCourseRegistration.objects.select_related("cohort", "course")
            .filter(cohort__in=cohorts_visible_to(request.user, organisation))
            .order_by("cohort__name")
        )

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            _interface_link(
                "Cohort", "cohort.name", "cohorts/{cohort.pk}", card="primary"
            ),
            Column(
                header="Cohort status",
                template="educator_interface/data-table-cells/active_status.html",
                attr="cohort.is_active",
            ),
            *_registration_columns(),
        ]


class CourseCohortRegistrationsPanel(DataTablePanel):
    title = "Cohort registrations"
    data_table = CourseCohortRegistrationDataTable
    table_key = "cohort_registrations"

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).filter(course=self.instance)


class CourseLearnerRegistrationDataTable(DataTable):
    empty_message = "No learners are registered for this course yet. Learner registrations will appear here."
    empty_no_results = "No learner registrations match these filters."
    default_sort = "learner__user__first_name"

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        # Most courses are shared across the site, so the registrations are scoped through the organisation's learners rather than through the course.
        organisation = cast(OrganisationScopedRequest, request).organisation
        return (
            LearnerCourseRegistration.objects.select_related("learner__user", "course")
            .filter(learner__in=learners_visible_to(request.user, organisation))
            .order_by("learner__user__first_name", "learner__user__last_name")
        )

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            _learner_column("learner"),
            *_registration_columns(),
        ]


class CourseLearnerRegistrationsPanel(DataTablePanel):
    title = "Direct registrations"
    data_table = CourseLearnerRegistrationDataTable
    table_key = "learner_registrations"

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).filter(course=self.instance)


class CoursePanelStack(PanelStack):
    children = {
        "details": CourseDetailsPanel,
        "content": CourseContentPanel,
        "cohorts": CourseCohortRegistrationsPanel,
        "learners": CourseLearnerRegistrationsPanel,
    }


class CourseInstanceView(InstanceView):
    panel = CoursePanelStack


class CourseConfig(OrganisationSectionConfig, ListViewConfig):
    url_name = "courses"
    menu_label = "Courses"
    icon = "course"
    model = Course
    list_view = CourseDataTable
    table_key = "courses"
    instance_view = CourseInstanceView

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        organisation = cast(OrganisationScopedRequest, request).organisation
        if (
            not courses_visible_to(request.user, organisation)
            .filter(pk=instance.pk)
            .exists()
        ):
            raise OrganisationScopeDenied


class DashboardConfig(OrganisationSectionConfig, BaseViewConfig):
    url_name = "dashboard"
    menu_label = "Dashboard"
    icon = "home"
    panel = DashboardPanel


class StaffDataTable(DataTable):
    noun = "staff members"
    noun_singular = "staff member"
    search_fields = ["first_name", "last_name", "email"]
    default_sort = "first_name"
    empty_message = "No staff yet. Add the first staff member to give someone access to this organisation."
    empty_no_results = "No staff members match these filters."

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        organisation = cast(OrganisationScopedRequest, request).organisation
        return staff_of(organisation).prefetch_related(
            Prefetch(
                "object_role_assignments",
                queryset=staff_assignments(organisation)
                .select_related("assigned_by")
                .prefetch_related("target"),
                to_attr="held_assignments",
            ),
            Prefetch(
                "staffmember_set",
                queryset=StaffMember.objects.filter(organisation=organisation),
                to_attr="member_rows",
            ),
            Prefetch(
                "learner_set",
                queryset=Learner.objects.filter(
                    organisation=organisation, is_active=True
                ),
                to_attr="learner_rows",
            ),
        )

    @staticmethod
    def get_filters() -> list[TableFilter]:
        return [StaffRoleFilter()]

    @classmethod
    def get_rows(
        cls, request: HttpRequest, queryset: QuerySet, query: TableQuery
    ) -> Page:
        page_obj = super().get_rows(request, queryset, query)
        site = cast(OrganisationScopedRequest, request).organisation.site
        site_level_ids = set(
            site_level_admins(site)
            .filter(pk__in=[row.pk for row in page_obj.object_list])
            .values_list("pk", flat=True)
        )
        for row in page_obj.object_list:
            row.is_site_level = row.pk in site_level_ids
            row.role_entries = staff_role_entries(row, site)
            row.is_inactive = not any(m.is_active for m in row.member_rows)
        return page_obj

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            Column(
                header="Staff member",
                template="educator_interface/data-table-cells/staff_member.html",
                sortable=True,
                sort_field="first_name",
                card="primary",
            ),
            Column(
                header="Roles",
                template="educator_interface/data-table-cells/staff_roles.html",
                card="secondary",
            ),
        ]

    @staticmethod
    def get_row_label(row: Model) -> str:
        return cast(User, row).display_name


class StaffConfig(OrganisationSectionConfig, ListViewConfig):
    url_name = "staff"
    menu_label = "Staff"
    icon = "user"
    model = User
    list_view = StaffDataTable
    table_key = "staff"
    view_capability = "freedom_ls_learner_management.view_staffmember"
    # Rows have no page of their own, so there is nothing to authorise.
    check_access_exempt_reason = "staff members have no instance pages"

    intro_template_name = "educator_interface/partials/staff_only_admin_callout.html"
    refresh_events = (STAFF_CHANGED,)

    @classmethod
    def get_actions(cls, request: HttpRequest) -> list[PanelAction]:
        return [
            AddStaffMemberAction(),
            DeactivateRoleAction(),
            ChangeCohortsAction(),
            DeactivateStaffMemberAction(),
            ReactivateStaffMemberAction(),
        ]

    @classmethod
    def get_cell_context(cls, request: HttpRequest) -> dict[str, object]:
        return {
            "viewer": request.user,
            "grantable_role_keys": {g.role for g in grantable_roles_for(request)},
        }

    @classmethod
    def get_intro_context(cls, request: HttpRequest) -> dict[str, object]:
        scoped = cast(OrganisationScopedRequest, request)
        config = get_role_config(scoped.organisation.site.name)
        staff = staff_of(scoped.organisation)
        return {
            "roles": [config[role] for role in STAFF_ROLES],
            # One query: the first two staff pks are the viewer's alone only
            # when the viewer is the sole staff member.
            "only_staff_member_is_viewer": set(staff.values_list("pk", flat=True)[:2])
            == {scoped.user.pk},
        }


class OrganisationAuditLogTable(TargetedAuditLogEntryTable):
    empty_message = "Nothing has been recorded for this organisation yet."

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        # A bulk run's per-object entries show on the learner and cohort History
        # tabs; here only its summary row stands for the run.
        return AuditLogEntryTable.get_queryset(request).exclude(
            Q(run_id__isnull=False) & ~Q(action__in=SUMMARY_ACTIONS)
        )

    @classmethod
    def get_rows(
        cls, request: HttpRequest, queryset: QuerySet, query: TableQuery
    ) -> Page:
        # Skips AuditLogEntryTable.get_rows: the page's entries and the run
        # entries attached below take one target lookup together.
        page_obj = super(AuditLogEntryTable, cls).get_rows(request, queryset, query)
        summaries = [row for row in page_obj.object_list if row.run_id is not None]
        if not summaries:
            _attach_target_users(list(page_obj.object_list))
            return page_obj
        organisation = cast(OrganisationScopedRequest, request).organisation
        run_ids = {row.run_id for row in summaries}
        per_object = AuditLogEntry.objects.filter(
            organisation=organisation, run_id__in=run_ids
        ).exclude(action__in=SUMMARY_ACTIONS)
        entries_by_run: dict[UUID, list[AuditLogEntry]] = {}
        for entry in per_object.annotate(
            position=Window(
                RowNumber(),
                partition_by=F("run_id"),
                order_by=[F("created_at").desc(), F("id").desc()],
            )
        ).filter(position__lte=RUN_ROWS_KEPT):
            entries_by_run.setdefault(cast(UUID, entry.run_id), []).append(entry)
        totals = dict(per_object.values_list("run_id").annotate(total=Count("pk")))
        for row in summaries:
            row.run_entries = entries_by_run.get(row.run_id, [])
            row.run_entry_total = totals.get(row.run_id, 0)
            row.run_entries_more = row.run_entry_total - len(row.run_entries)
        _attach_target_users(
            [*page_obj.object_list, *(e for row in summaries for e in row.run_entries)]
        )
        return page_obj


class AuditLogConfig(OrganisationSectionConfig, ListViewConfig):
    url_name = "audit-log"
    menu_label = "Audit log"
    icon = "notes"
    model = AuditLogEntry
    list_view = OrganisationAuditLogTable
    table_key = "audit_log"
    view_capability = "freedom_ls_audit_log.view_auditlogentry"
    # Entries are rows in a log, never pages of their own, so there is nothing to authorise per row.
    check_access_exempt_reason = "audit log entries have no instance pages"

    @classmethod
    def get_export_queryset(cls, request: HttpRequest) -> QuerySet:
        # Auditors get a bulk run's per-object entries, which the screen
        # folds under the run's summary row, so this starts from the
        # unexcluded table queryset.
        return AuditLogEntryTable.get_queryset(request).select_related("actor")

    @classmethod
    def get_export_scope_slug(cls, request: HttpRequest) -> str:
        return cast(OrganisationScopedRequest, request).organisation.slug

    @classmethod
    def before_export(cls, request: HttpRequest, rows: QuerySet) -> QuerySet:
        return _record_export(
            request,
            rows,
            table=cls.list_view,
            table_key=cls.table_key,
            scope="organisation",
            scope_label="",
        )


interface_config = [
    NavGroup(
        "Teaching",
        [DashboardConfig, CohortConfig, LearnerConfig, CourseConfig],
    ),
    NavGroup("Administration", [StaffConfig, AuditLogConfig]),
]


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
        path_string="dashboard",
    )


def _resolve_organisation(user: User, organisation_slug: str) -> Organisation:
    """The organisation named by `organisation_slug`, if `user` can access it.

    "No such slug" and "slug exists but you have no access" both 404
    identically.
    """
    organisation = get_object_or_404(Organisation, slug=organisation_slug)
    if not organisations_accessible_to(user).filter(pk=organisation.pk).exists():
        raise Http404
    return organisation


def _attach_organisation(request: HttpRequest, organisation_slug: str) -> Organisation:
    """Resolve and authorise the organisation once and put it on the request.

    Everything the section configs list in required_request_attrs is set
    here, so a page and a file download start from the same scoped request.
    """
    organisation = _resolve_organisation(cast(User, request.user), organisation_slug)
    scoped_request = cast(OrganisationScopedRequest, request)
    scoped_request.organisation = organisation
    scoped_request.panel_scope_name = organisation.name
    scoped_request.panel_url_kwargs = {"organisation_slug": organisation.slug}
    return organisation


def _scoped_cohort(
    request: HttpRequest, organisation_slug: str, cohort_pk: str
) -> Cohort:
    """The cohort named in a file URL, after the organisation and cohort checks a page runs."""
    _attach_organisation(request, organisation_slug)
    return cast(Cohort, CohortConfig.get_instance_view(request, cohort_pk).instance)


@login_required
def cohort_report_download(
    request: HttpRequest, organisation_slug: str, cohort_pk: str, report_pk: str
) -> FileResponse:
    cohort = _scoped_cohort(request, organisation_slug, cohort_pk)
    report = get_object_or_404(
        GeneratedReport.objects.select_related("cohort__organisation"),
        pk=report_pk,
        cohort=cohort,
    )
    if not can(request.user, DOWNLOAD_COHORT_REPORT, cohort):
        raise Http404
    return report_file_response(report)


@login_required_htmx_to("educator_interface:root")
def partial_oversight_thread_older(
    request: HttpRequest, organisation_slug: str, learner_pk: str, conversation_pk: str
) -> HttpResponse:
    """Older messages of a conversation under oversight. Authorised the way the
    learner page is, then by the oversight permission and the oversight set;
    records nothing, since the open that reached this page already did."""
    if not comms_config.MESSAGING_ENABLED:
        raise Http404
    _attach_organisation(request, organisation_slug)
    learner = cast(
        Learner, LearnerConfig.get_instance_view(request, learner_pk).instance
    )
    if not can(request.user, VIEW_CONVERSATION, learner):
        raise Http404
    conversation = get_object_or_404(
        other_educator_conversations(cast(User, request.user), learner),
        pk=uuid_or_404(conversation_pk),
    )
    cursor = decode_cursor(request.GET.get("before", ""))
    if cursor is None:
        return HttpResponseBadRequest("before must be a cursor")
    return older_page_response(
        request,
        conversation,
        cursor,
        older_url=request.path,
        thread_id=READ_ONLY_THREAD_ID,
    )


def scope_request(
    request: HttpRequest, organisation_slug: str
) -> OrganisationScopedRequest:
    """Resolve and authorise the organisation named in the URL, and set the
    attributes the shell and the panels read off the request.

    Selecting an organisation is an authorisation decision, not a filter:
    unlike Site, which is derived from the request host and cannot be
    forged, an organisation comes from user-supplied URL input. "No such
    slug" and "slug exists but you have no access" both 404 identically — a
    403 would confirm the slug is real and let an attacker enumerate a
    Site's organisation names.
    """
    _attach_organisation(request, organisation_slug)
    scoped_request = cast(OrganisationScopedRequest, request)
    scoped_request.accessible_organisations = list(
        organisations_accessible_to(request.user)
    )
    # Rendered into the same OOB bundle panel_framework already assembles
    # for breadcrumbs/sidebar/title/announcer (panel_framework/views.py) —
    # on every navigation, not only a switch, because the switcher's
    # per-organisation links embed the current path_string, which changes
    # on every navigation and would otherwise go stale the moment the user
    # moves to a different section without switching organisation.
    scoped_request.panel_extra_oob = [
        "educator_interface/partials/organisation_switcher.html"
    ]
    return scoped_request


def standalone_page_context(
    request: OrganisationScopedRequest, heading: str, section: str
) -> dict[str, object]:
    """The shell context for a page outside the panel framework: the menu
    with `section` marked, and a trail back to the section, shaped like the
    one an instance page gets so the shell renders it as a back link."""
    extra_url_kwargs = request.panel_url_kwargs
    url_name = "educator_interface:interface"
    # The switcher links to the same path in another organisation; a run or
    # import belongs to one organisation, so the other lands on the section.
    request.path_string = section
    section_config = sections_by_url_name(interface_config)[section]
    return {
        "menu_groups": build_menu_items(
            interface_config,
            url_name,
            request,
            active_section=section,
            extra_url_kwargs=extra_url_kwargs,
        ),
        "breadcrumbs": [
            {
                "label": section_config.menu_label,
                "url": reverse(
                    url_name, kwargs={"path_string": section, **extra_url_kwargs}
                ),
            },
            {"label": heading},
        ],
        "heading": heading,
    }


def _see_other(url: str) -> HttpResponseRedirect:
    """A 303, so the browser follows a POST with a GET of the next page."""
    return HttpResponseRedirect(url, status=303)


def _learners_url(organisation: Organisation) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": "learners"},
    )


def _import_url(name: str, organisation: Organisation, *args: str) -> str:
    return reverse(
        f"educator_interface:{name}",
        kwargs={
            "organisation_slug": organisation.slug,
            **({"import_id": args[0]} if args else {}),
        },
    )


class FormatRow(NamedTuple):
    name: str
    requirement: str
    description: str
    example: str


def _format_rows(cohort: Cohort | None) -> list[FormatRow]:
    """One row per accepted column, in header order. On a cohort import the
    cohort column is never read, so its row says so instead of describing it."""
    rows = []
    for index, name in enumerate(HEADERS):
        description = HEADER_DESCRIPTIONS[name]
        if cohort is not None and name == "cohort":
            description = f"Ignored: everyone goes into {cohort.name}."
        rows.append(
            FormatRow(
                name=name,
                requirement="Required" if name in REQUIRED_HEADERS else "Optional",
                description=description,
                example=FULL_EXAMPLE_ROW[index],
            )
        )
    return rows


def _import_page(
    request: HttpRequest,
    scoped: OrganisationScopedRequest,
    template: str,
    context: dict[str, object],
    status: int = 200,
) -> HttpResponse:
    page = standalone_page_context(
        scoped, heading="Import learners", section="learners"
    )
    page.update(context)
    return render(request, template, page, status=status)


def _import_denied(
    request: HttpRequest, scoped: OrganisationScopedRequest
) -> HttpResponse:
    """The 403 page for a user who can see the organisation but may not import."""
    return _import_page(
        request,
        scoped,
        "educator_interface/learner_import_denied.html",
        {
            **LearnerConfig.get_denied_context(scoped, None, None),
            "back_url": _learners_url(scoped.organisation),
        },
        status=403,
    )


IMPORT_PREVIEW_PAGE_SIZE = 50
IMPORT_RESULT_ERROR_ROWS = 50


def _label_counts(
    rows: QuerySet[LearnerImportRow], field: str
) -> list[dict[str, object]]:
    """The rows per label, in the order labels are declared, for the labels
    that occur."""
    counted = {
        item[field]: item["total"]
        for item in rows.exclude(**{f"{field}__isnull": True})
        .values(field)
        .annotate(total=Count("pk"))
    }
    return [
        {"label": label.value, "name": label.label, "count": counted[label.value]}
        for label in ImportLabel
        if label.value in counted
    ]


def _count_of(counts: list[dict[str, object]], *labels: str) -> int:
    return sum(cast(int, item["count"]) for item in counts if item["label"] in labels)


def _requested_import_or_404(
    request: HttpRequest, scoped: OrganisationScopedRequest, import_id: str
) -> LearnerImport:
    """The import only its requester may see. Anyone else, and an import of
    another organisation, gets the 404 a missing one does."""
    return cast(
        LearnerImport,
        get_object_or_404(
            LearnerImport.objects.select_related("organisation", "cohort").filter(
                organisation=scoped.organisation, requested_by=cast(User, request.user)
            ),
            pk=import_id,
        ),
    )


def _cohort_learners_url(cohort: Cohort) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": cohort.organisation.slug,
            "path_string": f"cohorts/{cohort.pk}/__tabs/learners",
        },
    )


def _cohort_import_url(
    name: str, organisation: Organisation, cohort: Cohort | None
) -> str:
    """An import page's URL, carrying `?cohort=` for a cohort import."""
    url = _import_url(name, organisation)
    if cohort is None:
        return url
    return f"{url}?{urlencode({'cohort': str(cohort.pk)})}"


def _import_upload_url(learner_import: LearnerImport) -> str:
    """The upload page that made this import: the cohort's, for a cohort import."""
    return _cohort_import_url(
        "learner_import", learner_import.organisation, learner_import.cohort
    )


def _import_cohort_or_404(
    request: HttpRequest, organisation: Organisation
) -> Cohort | None:
    """The cohort named by `?cohort=`, among the cohorts the user can see in
    the organisation; None when the parameter is absent. A value that is not a
    cohort id is a 404 like an unknown one."""
    cohort_id = request.GET.get("cohort")
    if not cohort_id:
        return None
    try:
        return get_object_or_404(
            cohorts_visible_to(cast(User, request.user), organisation).select_related(
                "organisation"
            ),
            pk=cohort_id,
        )
    except ValidationError as error:
        raise Http404("No such cohort.") from error


@login_required
def learner_import(request: HttpRequest, organisation_slug: str) -> HttpResponse:
    """The upload page of a learner import; a valid file becomes a previewed
    import and the reader is sent to its preview. With `?cohort=<id>` the
    learners are added to that cohort."""
    scoped = scope_request(request, organisation_slug)
    organisation = scoped.organisation
    user = cast(User, request.user)
    cohort = _import_cohort_or_404(request, organisation)
    if not check_import_gate(user, organisation, cohort):
        return _import_denied(request, scoped)
    form = LearnerImportForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
    )
    if request.method == "POST" and form.is_valid():
        try:
            created = create_learner_import(
                user, organisation, cohort, form.cleaned_data["file"]
            )
        except CsvImportError as error:
            form.add_error("file", str(error))
        else:
            return _see_other(
                _import_url("learner_import_preview", organisation, str(created.pk))
            )
    return _import_page(
        request,
        scoped,
        "educator_interface/learner_import_upload.html",
        {
            "form": form,
            "cohort": cohort,
            "format_rows": _format_rows(cohort),
            "max_rows": f"{learner_management_config.LEARNER_IMPORT_MAX_ROWS:,}",
            "max_file_size": filesizeformat(MAX_UPLOAD_BYTES),
            "template_url": _cohort_import_url(
                "learner_import_template", organisation, cohort
            ),
        },
        status=422 if form.errors else 200,
    )


@login_required
def learner_import_preview(
    request: HttpRequest, organisation_slug: str, import_id: str
) -> HttpResponse:
    """What confirming an import will do (GET), and the confirmation (POST)."""
    scoped = scope_request(request, organisation_slug)
    learner_import = _requested_import_or_404(request, scoped, import_id)
    user = cast(User, request.user)
    if not check_import_gate(user, learner_import.organisation, learner_import.cohort):
        return _import_denied(request, scoped)
    result_url = _import_url("learner_import_result", scoped.organisation, import_id)
    if learner_import.status != ImportStatus.PREVIEWED:
        return _see_other(result_url)
    rows = LearnerImportRow.objects.filter(learner_import=learner_import)
    counts = _label_counts(rows, "preview_label")
    add_count = learner_import.row_count - _count_of(counts, *NOT_ADDED_LABELS)
    in_background = add_count > panel_framework_config.BULK_BACKGROUND_THRESHOLD
    if request.method == "POST":
        # Only one of two simultaneous confirmations changes a row, so only one
        # of them runs or enqueues the import. Either way the runner claims
        # the queued import itself.
        started = LearnerImport.objects.filter(
            pk=learner_import.pk, status=ImportStatus.PREVIEWED
        ).update(status=ImportStatus.QUEUED)
        if started:
            site_id = scoped.organisation.site_id
            if in_background:
                _run_learner_import_task.enqueue(str(learner_import.pk), site_id)
            else:
                run_learner_import(str(learner_import.pk), site_id)
        return _see_other(result_url)
    # An unknown label shows every row rather than none.
    label = request.GET.get("label", "")
    if label not in ImportLabel.values:
        label = ""
    if label:
        shown = rows.filter(preview_label=label)
    else:
        # Error rows have their own block above the table, so the unfiltered
        # table holds only the rows that will be added or are already members.
        shown = rows.exclude(preview_label=ImportLabel.ERROR)
    page_obj = Paginator(
        shown.order_by("line_number"), IMPORT_PREVIEW_PAGE_SIZE
    ).get_page(request.GET.get("page"))
    for row in page_obj:
        row.tone = PREVIEW_LABEL_TONES[row.preview_label]
    return _import_page(
        request,
        scoped,
        "educator_interface/learner_import_preview.html",
        {
            "learner_import": learner_import,
            "page_obj": page_obj,
            "label": label,
            "preview_url": _import_url(
                "learner_import_preview", scoped.organisation, import_id
            ),
            "upload_url": _import_upload_url(learner_import),
            "errors_url": _import_url(
                "learner_import_errors", scoped.organisation, import_id
            ),
            "label_counts": counts,
            "new_account_count": _count_of(counts, ImportLabel.NEW_ACCOUNT),
            "error_count": _count_of(counts, ImportLabel.ERROR),
            "error_rows": _capped_error_rows(learner_import),
            "add_count": add_count,
            "in_background": in_background,
        },
    )


def _csv_attachment(chunks: Iterator[str], filename: str) -> StreamingHttpResponse:
    response = StreamingHttpResponse(chunks, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def learner_import_template(
    request: HttpRequest, organisation_slug: str
) -> HttpResponse | StreamingHttpResponse:
    """A CSV with the accepted headers and two example rows. Gated like the
    upload page that links to it, so `?cohort=` names the same cohort."""
    scoped = scope_request(request, organisation_slug)
    cohort = _import_cohort_or_404(request, scoped.organisation)
    if not check_import_gate(cast(User, request.user), scoped.organisation, cohort):
        return _import_denied(request, scoped)
    return _csv_attachment(
        write_error_csv(HEADERS, TEMPLATE_EXAMPLE_ROWS), "learner-import-template.csv"
    )


@login_required
def learner_import_errors(
    request: HttpRequest, organisation_slug: str, import_id: str
) -> HttpResponse | StreamingHttpResponse:
    """The rows of an import that were not added because of an error, with
    the reason for each, in the shape the import accepts plus a reason."""
    scoped = scope_request(request, organisation_slug)
    learner_import = _requested_import_or_404(request, scoped, import_id)
    if not check_import_gate(
        cast(User, request.user), learner_import.organisation, learner_import.cohort
    ):
        return _import_denied(request, scoped)
    # Built before the response is returned: the body is read after the
    # request's site scope has been cleared.
    rows = error_rows(learner_import).iterator(chunk_size=500)
    filename = f"learner-import-errors-{timezone.localdate().isoformat()}.csv"
    return _csv_attachment(
        write_error_csv(
            ERROR_CSV_HEADER,
            (
                (
                    row.email,
                    row.first_name,
                    row.last_name,
                    row.cohort_name,
                    error_reason(row),
                )
                for row in rows
            ),
        ),
        filename,
    )


def _capped_error_rows(learner_import: LearnerImport) -> list[dict[str, object]]:
    """The first IMPORT_RESULT_ERROR_ROWS error rows with their reasons."""
    return [
        {"row": row, "reason": error_reason(row)}
        for row in error_rows(learner_import)[:IMPORT_RESULT_ERROR_ROWS]
    ]


def _import_status_context(
    scoped: OrganisationScopedRequest, learner_import: LearnerImport
) -> dict[str, object]:
    """What `partials/run_status.html` renders for an import: the progress while
    it is queued or running, the outcome once it has finished or failed."""
    import_id = str(learner_import.pk)
    total = learner_import.row_count
    context: dict[str, object] = {
        "run": learner_import,
        "learner_import": learner_import,
        "noun": "rows",
        "total": total,
        "percentage": learner_import.processed_count * 100 // total if total else 100,
        "status_url": _import_url(
            "learner_import_status", scoped.organisation, import_id
        ),
        "result_template": "educator_interface/partials/learner_import_result_body.html",
        "result_on_failure": True,
        "in_progress": learner_import.status not in (RunStatus.DONE, RunStatus.FAILED),
    }
    if context["in_progress"]:
        return context
    counts = _label_counts(
        LearnerImportRow.objects.filter(learner_import=learner_import), "final_label"
    )
    added = total - _count_of(counts, *NOT_ADDED_LABELS)
    context.update(
        label_counts=counts,
        added_count=added,
        not_added_count=total - added,
        error_rows=_capped_error_rows(learner_import),
        error_count=_count_of(counts, ImportLabel.ERROR),
        errors_url=_import_url("learner_import_errors", scoped.organisation, import_id),
        new_account_count=_count_of(counts, ImportLabel.NEW_ACCOUNT),
        learners_url=(
            _cohort_learners_url(learner_import.cohort)
            if learner_import.cohort
            else _learners_url(scoped.organisation)
        ),
        upload_url=_import_upload_url(learner_import),
    )
    return context


@login_required
def learner_import_result(
    request: HttpRequest, organisation_slug: str, import_id: str
) -> HttpResponse:
    """What an import did, or how far it got."""
    scoped = scope_request(request, organisation_slug)
    learner_import = _requested_import_or_404(request, scoped, import_id)
    user = cast(User, request.user)
    if not check_import_gate(user, learner_import.organisation, learner_import.cohort):
        return _import_denied(request, scoped)
    if learner_import.status == ImportStatus.PREVIEWED:
        return _see_other(
            _import_url("learner_import_preview", scoped.organisation, import_id)
        )
    return _import_page(
        request,
        scoped,
        "educator_interface/learner_import_result.html",
        _import_status_context(scoped, learner_import),
    )


@login_required_htmx_to("educator_interface:root")
def partial_learner_import_status(
    request: HttpRequest, organisation_slug: str, import_id: str
) -> HttpResponse:
    """The polled fragment of `learner_import_result`."""
    scoped = scope_request(request, organisation_slug)
    learner_import = _requested_import_or_404(request, scoped, import_id)
    user = cast(User, request.user)
    if not check_import_gate(user, learner_import.organisation, learner_import.cohort):
        return _import_denied(request, scoped)
    if learner_import.status == ImportStatus.PREVIEWED:
        raise Http404("The import has not been confirmed.")
    context = _import_status_context(scoped, learner_import)
    response = render(request, "educator_interface/partials/run_status.html", context)
    if not context["in_progress"]:
        # The finished outcome has a heading and focus handling the polled
        # fragment cannot carry, so the whole page is rendered again.
        response["HX-Refresh"] = "true"
    return response


@login_required
def interface(
    request: HttpRequest, organisation_slug: str, path_string: str = ""
) -> HttpResponse | StreamingHttpResponse:
    """Serve the panel framework for the organisation named in the URL."""
    scoped_request = scope_request(request, organisation_slug)
    organisation = scoped_request.organisation
    scoped_request.path_string = path_string
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
        section_config = sections_by_url_name(interface_config)[section]
        section_model: type[Model] | None = getattr(section_config, "model", None)
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
