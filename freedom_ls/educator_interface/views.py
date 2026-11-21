from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import NamedTuple, cast

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Model, Q, QuerySet
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
from freedom_ls.base.csv_import import (
    MAX_UPLOAD_BYTES,
    CsvImportError,
    write_error_csv,
)
from freedom_ls.comms.config import config as comms_config
from freedom_ls.comms.messaging import (
    decode_cursor,
)
from freedom_ls.comms.messaging_views import (
    READ_ONLY_THREAD_ID,
    older_page_response,
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
    other_educator_conversations,
)
from freedom_ls.educator_interface.panels.audit_log.config import AuditLogConfig
from freedom_ls.educator_interface.panels.audit_log.data_table_panels import (
    HistoryPanel,
)
from freedom_ls.educator_interface.panels.audit_log.data_tables import (
    TargetedAuditLogEntryTable,
)
from freedom_ls.educator_interface.panels.cohort.data_tables import CohortDataTable
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
    _course_title_column,
    _registration_columns,
)
from freedom_ls.educator_interface.panels.course.config import CourseConfig
from freedom_ls.educator_interface.panels.dashboard.config import DashboardConfig

# Importing the module registers the learners table's bulk actions.
from freedom_ls.educator_interface.panels.learner import bulk_actions  # noqa: F401
from freedom_ls.educator_interface.panels.learner.actions import (
    AddLearnerAction,
    AddToCohortAction,
    EditLearnerNameAction,
    ImportLearnersAction,
    MoveToCohortAction,
    RegisterLearnerForCourseAction,
    RemoveFromCohortAction,
    ResendSetupEmailAction,
    learner_state_actions,
)
from freedom_ls.educator_interface.panels.learner.data_table_panels import (
    LearnerCohortsPanel,
    LearnerHistoryPanel,
    LearnerRegistrationsPanel,
)
from freedom_ls.educator_interface.panels.learner.data_tables import (
    CohortLearnerDataTable,
    LearnerDataTable,
)
from freedom_ls.educator_interface.panels.learner.messages import (
    LearnerMessagesStack,
)
from freedom_ls.educator_interface.panels.learner.panels import (
    LearnerAccountPanel,
    LearnerCoursesPanel,
    LearnerDetailsPanel,
    LearnerNamePanel,
)
from freedom_ls.educator_interface.panels.learner.quick_view import LearnerQuickView
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
)
from freedom_ls.educator_interface.reporting import (
    DOWNLOAD_COHORT_REPORT,
    CohortNeedsAttentionPanel,
    CohortReportStack,
)
from freedom_ls.educator_interface.tasks import _run_learner_import_task
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.config import config as learner_management_config
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    ImportLabel,
    ImportStatus,
    Learner,
    LearnerImport,
    LearnerImportRow,
)
from freedom_ls.learner_management.queries import (
    ASSIGN_COHORT_VIEWER,
    CHANGE_COHORT,
    VIEW_CONVERSATION,
    LearnerStatus,
    cohort_counts,
    cohort_educators,
    cohorts_visible_to,
    learner_status,
    learners_visible_to,
    organisations_accessible_to,
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
from freedom_ls.panel_framework.models import RunStatus
from freedom_ls.panel_framework.panels import (
    DataTablePanel,
    InstanceDetailsPanel,
    Panel,
    PanelStack,
    TabSet,
    entry_count_text,
)
from freedom_ls.panel_framework.tables import Column, DataTable
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

# TODO
# Data Tables
# top level filters (searchable dropdown)
#   use HTMX to only reload that one panel
# Bulk delete
# Export as csv
#
# instance edit
# instance, other actions (eg: send_email)


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
