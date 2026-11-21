from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, F, Model, Q, QuerySet
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from freedom_ls.accounts.models import User
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
    REGISTRATION_CHANGED,
    STAFF_CHANGED,
)
from freedom_ls.educator_interface.exceptions import OrganisationScopeDenied
from freedom_ls.educator_interface.forms import CohortForm
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
)
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
from freedom_ls.educator_interface.panels.learner.actions import (
    ImportLearnersAction,
    MoveToCohortAction,
    RemoveFromCohortAction,
)
from freedom_ls.educator_interface.panels.learner.config import LearnerConfig
from freedom_ls.educator_interface.panels.learner.data_tables import (
    CohortLearnerDataTable,
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
)
from freedom_ls.educator_interface.reporting import (
    DOWNLOAD_COHORT_REPORT,
    CohortNeedsAttentionPanel,
    CohortReportStack,
)
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    ASSIGN_COHORT_VIEWER,
    CHANGE_COHORT,
    cohort_counts,
    cohort_educators,
    cohorts_visible_to,
    organisations_accessible_to,
)
from freedom_ls.learner_management.utils import record_cohort_entry
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.actions import (
    CreateInstanceAction,
    PanelAction,
)
from freedom_ls.panel_framework.bulk_actions import BulkAction, bulk_actions_for_table
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.panels import (
    DataTablePanel,
    InstanceDetailsPanel,
    Panel,
    PanelStack,
    TabSet,
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
