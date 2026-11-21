from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import NamedTuple, cast
from uuid import UUID, uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
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
)
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
from freedom_ls.audit_log.writer import record_entry
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
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.actions import (
    AddExistingLearnersAction,
    AddLearnerToCohortAction,
    DeactivateCohortRegistrationAction,
    DeleteEmptyCohortAction,
    EditCohortAction,
    RegisterCohortForCourseAction,
    cohort_not_empty_sentence,
    cohort_state_actions,
)
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
    REGISTRATION_CHANGED,
    STAFF_CHANGED,
)
from freedom_ls.educator_interface.exceptions import OrganisationScopeDenied
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
from freedom_ls.educator_interface.panels.audit_log.config import AuditLogConfig
from freedom_ls.educator_interface.panels.audit_log.data_table_panels import (
    HistoryPanel,
)
from freedom_ls.educator_interface.panels.audit_log.data_tables import (
    TargetedAuditLogEntryTable,
)
from freedom_ls.educator_interface.panels.cohort.data_tables import (
    CohortDataTable,
    LearnerCohortDataTable,
)
from freedom_ls.educator_interface.panels.common.badges import (
    active_status_badge,
    inactive_badge,
    learner_status_badge,
)
from freedom_ls.educator_interface.panels.common.ids import uuid_or_404
from freedom_ls.educator_interface.panels.common.request import (
    LAST_ORGANISATION_SESSION_KEY,
    OrganisationScopedRequest,
    OrganisationSectionConfig,
)
from freedom_ls.educator_interface.panels.common.tables import (
    _cohort_links_column,
    _course_title_column,
    _learner_column,
    _registration_columns,
)
from freedom_ls.educator_interface.panels.course.config import CourseConfig
from freedom_ls.educator_interface.panels.dashboard.config import DashboardConfig
from freedom_ls.educator_interface.panels.learner.actions import (
    AddLearnerAction,
    AddToCohortAction,
    DeactivateRegistrationAction,
    EditLearnerNameAction,
    ImportLearnersAction,
    MoveToCohortAction,
    ReactivateRegistrationAction,
    RegisterLearnerForCourseAction,
    RemoveFromCohortAction,
    ResendSetupEmailAction,
    learner_state_actions,
)
from freedom_ls.educator_interface.panels.learner.filters import (
    LearnerCohortFilter,
    LearnerCourseFilter,
    LearnerStatusFilter,
)
from freedom_ls.educator_interface.panels.staff.actions import (
    AddStaffMemberToCohortAction,
    ChangeRoleAction,
    RemoveStaffFromCohortAction,
    roles_grantable_on,
)
from freedom_ls.educator_interface.panels.staff.config import StaffConfig
from freedom_ls.educator_interface.paths import interface_path
from freedom_ls.educator_interface.quick_views import (
    CohortQuickView,
    LearnerQuickView,
)
from freedom_ls.educator_interface.reporting import (
    DOWNLOAD_COHORT_REPORT,
    CohortNeedsAttentionPanel,
    CohortReportStack,
    LearnerCoursesPanel,
)
from freedom_ls.educator_interface.tasks import _run_learner_import_task
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
)
from freedom_ls.learner_management.queries import (
    ASSIGN_COHORT_VIEWER,
    CHANGE_COHORT,
    DELETE_COHORTMEMBERSHIP,
    VIEW_CONVERSATION,
    LearnerStatus,
    available_to_organisation_expression,
    cohort_counts,
    cohort_educators,
    cohorts_visible_to,
    learner_status,
    learners_visible_to,
    organisations_accessible_to,
    site_level_admins,
)
from freedom_ls.learner_management.utils import record_cohort_entry
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.actions import (
    CreateInstanceAction,
    PanelAction,
)
from freedom_ls.panel_framework.bulk_actions import BulkAction, bulk_actions_for_table
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
    entry_count_text,
)
from freedom_ls.panel_framework.tables import (
    BadgeColumn,
    Column,
    DataTable,
    ExportColumn,
)
from freedom_ls.panel_framework.views import (
    InstanceView,
    ListViewConfig,
    NavGroup,
    StatusBadge,
    build_menu_items,
    first_visible_section,
    panel_framework_view,
    sections_by_url_name,
)
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.services import report_file_response
from freedom_ls.site_aware_models.models import get_cached_site

# TODO
# Data Tables
# top level filters (searchable dropdown)
#   use HTMX to only reload that one panel
# Bulk delete
# Export as csv
#
# instance edit
# instance, other actions (eg: send_email)


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
    cards_when_narrow = True
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
            .select_related("user", "organisation")
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
                    queryset=CohortCourseRegistration.objects.filter(is_active=True)
                    .select_related("course")
                    .prefetch_related("course__organisations"),
                ),
                Prefetch(
                    "learnercourseregistration_set",
                    queryset=LearnerCourseRegistration.objects.filter(is_active=True)
                    .select_related("course")
                    .prefetch_related("course__organisations"),
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
            BadgeColumn(
                header="Status",
                template_name="cotton/data-table-cells/badge.html",
                badge=lambda row: learner_status_badge(cast(Learner, row)),
            ),
            _cohort_links_column("cohortmembership_set.all"),
            Column(
                header="Courses",
                template_name="educator_interface/data-table-cells/learner_courses.html",
            ),
            Column(
                header="Last active",
                template_name="cotton/data-table-cells/date.html",
                attr="last_active",
                sortable=True,
                empty_text="Never",
            ),
        ]

    @staticmethod
    def get_row_label(row: object) -> str:
        return cast(Learner, row).user.display_name

    @staticmethod
    def get_filters() -> list[TableFilter]:
        return [
            LearnerStatusFilter(),
            LearnerCohortFilter("cohort", "Cohort"),
            LearnerCourseFilter("course", "Course"),
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
                    summary.course.label_for(cast(Learner, row).organisation)
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
                template_name="educator_interface/data-table-cells/membership_actions.html",
                card="secondary",
            ),
        ]


class LearnerDetailsPanel(InstanceDetailsPanel):
    model = Learner
    refresh_events = (LEARNER_CHANGED,)

    def get_rows(self) -> list[dict[str, object]]:
        learner = cast(Learner, self.instance)
        return [
            self.detail_row("Name", learner.user.display_name),
            self.detail_row("Email", learner.user.email),
            self.detail_row("Status", learner_status_badge(learner), "badge"),
            self.detail_row("Date added", learner.created_at, "date"),
        ]


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
        # those rows alone, and an inactive cohort offers nothing.
        context["membership_param"] = "cohort"
        context["membership_row_ids"] = set(
            cohorts_visible_to(
                request.user,
                request.organisation,
                capability=DELETE_COHORTMEMBERSHIP,
            )
            .filter(is_active=True)
            .values_list("pk", flat=True)
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
    shared_by: str | None = None
    can_reactivate: bool = False

    @property
    def detail(self) -> str:
        """The muted line under the course title: how the learner is
        registered, then who shares the course when another organisation
        owns it."""
        return (
            f"{self.via} · Shared by {self.shared_by}" if self.shared_by else self.via
        )

    @property
    def badge(self) -> StatusBadge:
        return active_status_badge(self.is_active)

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
        individual = list(
            LearnerCourseRegistration.objects.filter(learner=learner)
            .select_related("course")
            .prefetch_related("course__organisations")
        )
        # A registration through an inactive cohort is not shown at all; the
        # learner reaches that course only while the cohort is active.
        through_cohorts = (
            CohortCourseRegistration.objects.filter(
                cohort__in=visible_cohorts,
                cohort__is_active=True,
                cohort__cohortmembership__learner=learner,
            )
            .select_related("course", "cohort")
            .prefetch_related("course__organisations")
        )
        # Reactivating registers the learner again, which an educator may do
        # only for a course available to the learner's organisation.
        available_course_ids = set(
            Course.objects.filter(
                pk__in=[r.course_id for r in individual if not r.is_active]
            )
            .filter(available_to_organisation_expression(learner.organisation))
            .values_list("pk", flat=True)
        )

        def row(
            registration: LearnerCourseRegistration | CohortCourseRegistration,
            via: str,
        ) -> RegistrationRow:
            return RegistrationRow(
                registration.course,
                via,
                registration.is_active,
                registration,
                registration.course.shared_by(request.organisation),
                registration.course_id in available_course_ids,
            )

        rows = [row(r, "Individual") for r in individual] + [
            row(r, f"via {r.cohort.name}") for r in through_cohorts
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


class LearnerHistoryPanel(HistoryPanel):
    model = Learner
    export_scope = "learner"
    refresh_events = (LEARNER_CHANGED,)
    empty_message = (
        "No history for this learner yet. Actions such as moving or "
        "deactivating them are recorded here."
    )

    def has_permission(self, request: HttpRequest) -> bool:
        """A learner's history spans every cohort they belong to, so it
        opens only for someone who may read the whole organisation's audit
        log, not for a cohort admin of one of those cohorts."""
        organisation = cast(Learner, self.instance).organisation
        return self.ctx.config.has_capability(request, self.capability, organisation)

    @property
    def scope_label(self) -> str:
        return cast(Learner, self.instance).user.display_name


class LearnerMessagesPanel(Panel):
    """The educator's own conversation with the learner. The thread pane runs
    edge to edge, so the card is flush.

    It declares no refresh events: a re-fetch would mark the thread read again
    for nothing, and the thread polls for new messages itself.
    """

    model = Learner
    title = "Messages"
    template_name = "educator_interface/panels/learner_messages.html"
    card_flush = True

    def has_permission(self, request: HttpRequest) -> bool:
        return comms_config.MESSAGING_ENABLED and super().has_permission(request)

    @cached_property
    def _own(self) -> OwnConversation:
        return own_conversation_with(self.request, cast(Learner, self.instance))

    def get_actions(self) -> list[PanelAction]:
        return [SendToLearnerAction()]

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
            own = self._own
        may_write = own.allowed or bool(alert)
        context["learner"] = learner
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
        return context


class LearnerOtherConversationsPanel(Panel):
    """The learner's conversations with their other educators, for someone
    with oversight of the learner: one row each, opening the conversation
    read-only in the app modal."""

    model = Learner
    title = "Other educator conversations"
    template_name = "educator_interface/panels/learner_other_conversations.html"

    def has_permission(self, request: HttpRequest) -> bool:
        return (
            comms_config.MESSAGING_ENABLED
            and super().has_permission(request)
            and bool(self.available_actions)
        )

    def get_actions(self) -> list[PanelAction]:
        return [ViewConversationAction()]

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        learner = cast(Learner, self.instance)
        rows = other_educator_conversations(cast(User, self.request.user), learner)
        context["oversight_rows"] = [
            (c, other_participant(c, learner.user)) for c in rows
        ]
        return context


class LearnerMessagesStack(PanelStack):
    """The learner's Messages tab: the educator's own conversation, then the
    learner's other educator conversations, each its own panel."""

    model = Learner
    title = "Messages"
    children = {
        "conversation": LearnerMessagesPanel,
        "others": LearnerOtherConversationsPanel,
    }


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


def _oversight_role_label(viewer: User, learner: Learner) -> str:
    """How the read-only banner names the viewer's access: a site admin reads
    through the site grant, anyone else holding the permission is an
    organisation admin of the learner's organisation."""
    if site_level_admins(learner.site).filter(pk=viewer.pk).exists():
        return "a site admin"
    return "an organisation admin"


class LearnerNamePanel(Panel):
    """The learner's first and last name as fields with Save, posted inline
    to the edit action, as the cohort's Name panel is. Shown only to someone
    who may change the name."""

    model = Learner
    title = "Name"
    template_name = "educator_interface/panels/learner_name.html"
    refresh_events = (LEARNER_CHANGED,)

    def has_permission(self, request: HttpRequest) -> bool:
        return super().has_permission(request) and bool(self.available_actions)

    def get_actions(self) -> list[PanelAction]:
        return [EditLearnerNameAction(cast(Learner, self.instance))]

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context["rename"] = self.available_actions[0].get_context_data(self.ctx)
        return context


class LearnerAccountPanel(Panel):
    """The learner's account: whether it is set up and active, with Resend
    setup email and Deactivate or Reactivate in the footer. Shown to anyone
    who may take one of those actions."""

    model = Learner
    title = "Account"
    template_name = "educator_interface/panels/learner_account.html"
    refresh_events = (LEARNER_CHANGED,)

    def has_permission(self, request: HttpRequest) -> bool:
        return super().has_permission(request) and bool(self.available_actions)

    def get_actions(self) -> list[PanelAction]:
        return [ResendSetupEmailAction(), *learner_state_actions()]

    def get_context_data(self) -> dict[str, object]:
        learner = cast(Learner, self.instance)
        context = super().get_context_data()
        context["learner"] = learner
        context["status"] = learner_status(learner)
        return context


class LearnerSettingsStack(PanelStack):
    """The learner's Settings tab: the actions with no home of their own,
    one panel per job. Add to cohort lives on the Cohorts panel and Register
    for a course on the Courses tab, beside what they change."""

    model = Learner
    title = "Settings"
    children = {"name": LearnerNamePanel, "account": LearnerAccountPanel}


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
        "messages": LearnerMessagesStack,
        "settings": LearnerSettingsStack,
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


class CohortDetailsPanel(InstanceDetailsPanel):
    model = Cohort
    refresh_events = (COHORT_CHANGED,)

    def get_rows(self) -> list[dict[str, object]]:
        cohort = cast(Cohort, self.instance)
        counts = cohort_counts(cohort)
        return [
            self.detail_row("Name", cohort.name),
            self.detail_row("Status", active_status_badge(cohort.is_active), "badge"),
            self.detail_row("Created", cohort.created_at, "date"),
            self.detail_row("Learners", counts.learners),
            self.detail_row("Courses", counts.courses),
        ]


class CohortCourseRegistrationDataTable(DataTable):
    empty_message = "This cohort is not registered for any courses yet. Its course registrations will appear here."
    empty_no_results = "No course registrations match these filters."

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        request = cast(OrganisationScopedRequest, request)
        visible_cohorts = cohorts_visible_to(request.user, request.organisation)
        return (
            CohortCourseRegistration.objects.select_related("course", "cohort")
            .prefetch_related("course__organisations")
            .filter(cohort__in=visible_cohorts)
            .order_by("course__title")
        )

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            _course_title_column(
                "Course", "course.title", "courses/{course.pk}", attr="course"
            ),
            *_registration_columns(),
            Column(
                header="",
                template_name="educator_interface/data-table-cells/deactivate_registration.html",
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
        # None offers the actions on every learner row; an inactive cohort
        # offers none.
        context["membership_param"] = "learner"
        context["membership_row_ids"] = (
            None if cast(Cohort, self.instance).is_active else set()
        )
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
    shared_by: str | None = None

    @property
    def detail(self) -> str:
        """The muted line under the course title: who shares the course when
        another organisation owns it, then how many members have completed."""
        progress = f"{self.completed_count} of {self.record_count} completed"
        return (
            f"Shared by {self.shared_by} · {progress}" if self.shared_by else progress
        )


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
            .prefetch_related("course__organisations")
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
                shared_by=registration.course.shared_by(
                    cast(OrganisationScopedRequest, self.request).organisation
                ),
            )
            for registration in registrations
        ]
        return context


class CohortNamePanel(Panel):
    """The cohort's name as a field with Save, posted inline to the edit
    action. Hidden when the edit action is not available, as on an inactive
    cohort."""

    title = "Name"
    capability = CHANGE_COHORT
    template_name = "educator_interface/panels/cohort_name.html"
    refresh_events = (COHORT_CHANGED,)

    def get_actions(self) -> list[PanelAction]:
        cohort = cast(Cohort, self.instance)
        return [
            EditCohortAction(
                form_class=CohortForm,
                form_title=f"Edit {cohort}",
                instance=cohort,
                success_events=(COHORT_CHANGED,),
            )
        ]

    def is_shown(self) -> bool:
        return super().is_shown() and bool(self.available_actions)

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context["rename"] = self.available_actions[0].get_context_data(self.ctx)
        return context


class CohortStaffPanel(Panel):
    """The cohort's staff: Add staff member in the header, then one row per
    person with their role and Change role and Remove from cohort for each
    cohort role the viewer may give. A cohort admin who cannot change the
    cohort still gets this panel, since they may give cohort roles on it."""

    title = "Staff"
    template_name = "educator_interface/panels/cohort_staff.html"
    refresh_events = (COHORT_CHANGED, STAFF_CHANGED)

    def has_permission(self, request: HttpRequest) -> bool:
        cohort = cast(Cohort, self.instance)
        return can(request.user, CHANGE_COHORT, cohort) or can(
            request.user, ASSIGN_COHORT_VIEWER, cohort
        )

    def get_actions(self) -> list[PanelAction]:
        return [
            AddStaffMemberToCohortAction(),
            ChangeRoleAction(),
            RemoveStaffFromCohortAction(),
        ]

    def get_context_data(self) -> dict[str, object]:
        cohort = cast(Cohort, self.instance)
        context = super().get_context_data()
        by_name = {action.action_name: action for action in self.available_actions}
        remove = by_name.get("remove_staff_from_cohort")
        change = by_name.get("change_role")
        context["add_staff"] = by_name.get("add_staff_member")
        context["remove_from_cohort_url"] = (
            remove.get_action_url(self.ctx) if remove else ""
        )
        context["change_role_url"] = change.get_action_url(self.ctx) if change else ""
        context["educators"] = cohort_educators(cohort)
        context["grantable"] = roles_grantable_on(self.request, cohort)
        return context


class CohortStatusPanel(Panel):
    """Whether the cohort is active, with Deactivate or Reactivate and
    Delete in the footer."""

    title = "Status"
    capability = CHANGE_COHORT
    template_name = "educator_interface/panels/cohort_status.html"
    refresh_events = (COHORT_CHANGED,)

    def get_actions(self) -> list[PanelAction]:
        cohort = cast(Cohort, self.instance)
        return [
            *cohort_state_actions(),
            DeleteEmptyCohortAction(
                success_url=interface_path(cohort.organisation, "cohorts"),
            ),
        ]

    def get_context_data(self) -> dict[str, object]:
        cohort = cast(Cohort, self.instance)
        context = super().get_context_data()
        context["cohort"] = cohort
        context["not_empty_sentence"] = cohort_not_empty_sentence(cohort)
        return context


class CohortSettingsStack(PanelStack):
    """The cohort's Settings tab: one panel per job, so the name, the staff
    and the cohort's status each have their own card."""

    title = "Settings"
    refresh_events = (COHORT_CHANGED,)
    children = {
        "name": CohortNamePanel,
        "staff": CohortStaffPanel,
        "status": CohortStatusPanel,
    }


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
        "settings": CohortSettingsStack,
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

    def get_form(self, ctx: PanelContext) -> forms.BaseForm:
        # The organisation is not a user choice — CohortForm never exposes
        # the field — so it comes from the URL the request already resolved
        # and authorised, not from anything the form submitted. It is attached
        # here rather than in form_valid because the per-organisation
        # uniqueness constraint can only be checked while cleaning if the
        # instance already carries its organisation.
        form = super().get_form(ctx)
        organisation = cast(OrganisationScopedRequest, ctx.request).organisation
        cast(Cohort, cast(forms.ModelForm, form).instance).organisation = organisation
        return form

    def get_success_url(self, ctx: PanelContext, instance: Model) -> str:
        organisation = cast(OrganisationScopedRequest, ctx.request).organisation
        return interface_path(organisation, f"cohorts/{instance.pk}")

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        with transaction.atomic():
            response = super().form_valid(ctx, form)
            record_cohort_entry(
                cast(Cohort, cast(forms.ModelForm, form).instance),
                "cohort.created",
                cast(User, ctx.request.user),
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
    # Which sections show depends on the viewer's roles in this organisation:
    # someone who sees the staff list and nothing else has no Dashboard.
    _attach_organisation(request, organisation.slug)
    section = first_visible_section(interface_config, request)
    if section is None:
        raise Http404
    return redirect(
        "educator_interface:interface",
        organisation_slug=organisation.slug,
        path_string=section.url_name,
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
    template = "educator_interface/learner_import_preview.html"
    if request.headers.get("HX-Target") == "import-rows":
        # A page link swaps in only the rows card. Any other htmx request (a
        # redirect followed here, a navigation link) needs the whole page.
        template = f"{template}#rows"
    return _import_page(
        request,
        scoped,
        template,
        {
            "learner_import": learner_import,
            "page_obj": page_obj,
            "entry_count": entry_count_text(page_obj, "row", "rows"),
            "label": label,
            "pagination_params": urlencode({"label": label}) if label else "",
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

    if not path_string.strip("/"):
        # The organisation's own URL names no section: land on the first one
        # the visitor's roles show, as the educator root does.
        landing = first_visible_section(interface_config, scoped_request)
        if landing is None:
            raise Http404
        return redirect(
            "educator_interface:interface",
            organisation_slug=organisation.slug,
            path_string=landing.url_name,
        )

    is_switch = request.headers.get("X-Organisation-Switch") == "true"
    landed_elsewhere = False
    if is_switch:
        scoped_request.panel_announcement = f"Now viewing {organisation.name}"
        # The switcher links to the section the visitor is on, which their
        # roles in this organisation may not show. They land on one it does.
        asked = sections_by_url_name(interface_config).get(path_string.split("/", 1)[0])
        if asked is not None and not (
            asked.is_visible(scoped_request) and asked.is_available(scoped_request)
        ):
            landing = first_visible_section(interface_config, scoped_request)
            if landing is None:
                raise Http404
            path_string = landing.url_name
            scoped_request.path_string = path_string
            landed_elsewhere = True

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

    if landed_elsewhere:
        response["HX-Push-Url"] = reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": path_string},
        )
    return response
