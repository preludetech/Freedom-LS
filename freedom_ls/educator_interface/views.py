from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast
from uuid import UUID, uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import Site
from django.core.paginator import Page
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
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from freedom_ls.accounts.models import User
from freedom_ls.comms.config import config as comms_config
from freedom_ls.comms.messaging import (
    inbox_for,
    other_participant,
    refusal_alert_copy,
    reply_decisions,
    search_recipients,
    send_message,
)
from freedom_ls.comms.messaging_loader import get_messaging_policy
from freedom_ls.comms.messaging_views import (
    composer_context,
    thread_context,
)
from freedom_ls.comms.models import Conversation
from freedom_ls.comms.templatetags.comms_tags import badge_count
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.actions import (
    AddExistingLearnersAction,
    AddLearnersAction,
    AddLearnersToCohortAction,
    AddMemberAction,
    AddMemberToCohortAction,
    AddToCohortAction,
    ChangeCohortsAction,
    DeleteEmptyCohortAction,
    EditCohortAction,
    EditLearnerNameAction,
    MoveToCohortAction,
    ReactivateMemberAction,
    RegisterCohortForCourseAction,
    RegisterLearnerForCourseAction,
    RemoveFromCohortAction,
    RemoveRoleAction,
    ReregisterLearnerForCourseAction,
    ResendSetupEmailAction,
    SuspendMemberAction,
    UnregisterCohortFromCourseAction,
    UnregisterLearnerFromCourseAction,
    cohort_not_empty_sentence,
    cohort_state_actions,
    grantable_roles_for,
    learner_state_actions,
)
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
    MEMBER_CHANGED,
    REGISTRATION_CHANGED,
)
from freedom_ls.educator_interface.exceptions import OrganisationScopeDenied
from freedom_ls.educator_interface.filters import (
    LearnerCohortFilter,
    LearnerCourseFilter,
    LearnerStatusFilter,
    MemberRoleFilter,
    ShowInactiveFilter,
    VisibleCourseFilter,
)
from freedom_ls.educator_interface.forms import CohortForm
from freedom_ls.educator_interface.members import member_role_entries
from freedom_ls.educator_interface.messaging import (
    ConversationRow,
    conversations_in_organisation,
)
from freedom_ls.educator_interface.quick_views import (
    CohortQuickView,
    LearnerQuickView,
    visible_registrations_with_progress,
)
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
    OrganisationMember,
)
from freedom_ls.learner_management.queries import (
    DELETE_COHORTMEMBERSHIP,
    MEMBER_ROLES,
    LearnerStatus,
    active_organisation_admins,
    cohort_counts,
    cohort_educators,
    cohorts_visible_to,
    courses_visible_to,
    learner_status,
    learners_visible_to,
    member_assignments,
    members_of,
    organisations_accessible_to,
    site_level_admins,
)
from freedom_ls.learner_management.role_assignment import GrantableRole
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.actions import (
    CreateInstanceAction,
    PanelAction,
    navigation_response,
)
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.filters import TableFilter
from freedom_ls.panel_framework.panels import (
    DataTablePanel,
    InstanceDetailsPanel,
    Panel,
    PanelStack,
    TabSet,
)
from freedom_ls.panel_framework.tables import Column, DataTable, TableQuery
from freedom_ls.panel_framework.views import (
    BaseViewConfig,
    HeaderStat,
    InstanceView,
    ListViewConfig,
    NavGroup,
    SectionConfigBase,
    StatusBadge,
    panel_framework_view,
    sections_by_url_name,
)
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
            "freedom_ls_learner_management.view_organisationmember",
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
# Checkboxes and bulk actions (eg. Delete, add to cohort, remove from cohort)
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
            template="cotton/data-table-cells/text.html",
            attr="registered_at",
            card="md_only",
        ),
    ]


class CohortDataTable(DataTable):
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
                template="cotton/data-table-cells/text.html",
                attr="created_at",
                sortable=True,
                card="md_only",
            ),
        ]

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

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            *CohortDataTable.get_columns(),
            Column(
                header="Joined",
                template="cotton/data-table-cells/text.html",
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
    search_fields = ["user__first_name", "user__last_name", "user__email"]
    default_sort = "user__first_name"

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        request = cast(OrganisationScopedRequest, request)
        organisation = request.organisation
        return (
            learners_visible_to(request.user, organisation, include_removed=True)
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


class CohortLearnerDataTable(LearnerDataTable):
    """The cohort page's learners: the learners table plus a Remove cell."""

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
        return [RemoveFromCohortAction(), MoveToCohortAction()]

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
            UnregisterLearnerFromCourseAction(),
            ReregisterLearnerForCourseAction(),
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


class LearnerCoursesPanel(Panel):
    model = Learner
    title = "Courses"
    template_name = "educator_interface/panels/learner_courses.html"
    refresh_events = (LEARNER_CHANGED, REGISTRATION_CHANGED)

    def get_context_data(self) -> dict[str, object]:
        learner = cast(Learner, self.instance)
        request = cast(OrganisationScopedRequest, self.request)
        context = super().get_context_data()
        context["entries"] = sorted(
            visible_registrations_with_progress(learner, request),
            key=lambda entry: entry.course.title,
        )
        return context


class LearnerCoursesStack(PanelStack):
    title = "Courses"
    refresh_events = (LEARNER_CHANGED,)
    children = {"courses": LearnerCoursesPanel}


class LearnerHistoryPanel(Panel):
    model = Learner
    title = "History"
    template_name = "educator_interface/panels/learner_history.html"
    refresh_events = (LEARNER_CHANGED,)


class LearnerTabSet(TabSet):
    title = "Learner sections"
    children = {
        "overview": LearnerOverviewStack,
        "courses": LearnerCoursesStack,
        "history": LearnerHistoryPanel,
    }


class LearnerInstanceView(InstanceView):
    panel = LearnerTabSet

    def get_status_badge(self) -> StatusBadge:
        return learner_status_badge(cast(Learner, self.instance))

    def get_subtitle(self) -> str:
        return cast(Learner, self.instance).user.email

    def get_actions(self) -> list[PanelAction]:
        return [
            EditLearnerNameAction(cast(Learner, self.instance)),
            AddToCohortAction(),
            RegisterLearnerForCourseAction(),
            ResendSetupEmailAction(),
            *learner_state_actions(),
        ]


def _interface_path(organisation: Organisation, path_string: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": path_string},
    )


_LEARNER_STATUS_TONES: dict[LearnerStatus, str] = {
    LearnerStatus.ACTIVE: "success",
    LearnerStatus.PENDING: "info",
    LearnerStatus.REMOVED: "muted",
}


def learner_status_badge(learner: Learner) -> StatusBadge:
    """The badge for a learner's status: Active, Pending or Removed."""
    status = learner_status(learner)
    return StatusBadge(_LEARNER_STATUS_TONES[status], status.label)


def active_status_badge(is_active: bool) -> StatusBadge:
    """The badge for an `is_active` flag, matching `<c-active-status-badge>`."""
    if is_active:
        return StatusBadge("success", "Active")
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
                template="educator_interface/data-table-cells/unregister.html",
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
            AddLearnersToCohortAction(),
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

    def get_tab_count(self) -> int | None:
        # The table lists removed members too; the tab counts current ones.
        return self.get_queryset(self.request).filter(is_active=True).count()


class CohortCoursesPanel(DataTablePanel):
    title = "Courses"
    data_table = CohortCourseRegistrationDataTable
    table_key = "cohort_courses"
    refresh_events = (COHORT_CHANGED, REGISTRATION_CHANGED)

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).filter(cohort=self.instance)

    def get_actions(self) -> list[PanelAction]:
        # Unregister renders per row, not in the footer: the unregister cell
        # reads its URL from row_action_urls.
        return [RegisterCohortForCourseAction(), UnregisterCohortFromCourseAction()]

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
        # removed or have left the cohort are kept for ever, so the counts are
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


class CohortNeedsAttentionPanel(Panel):
    title = "Needs attention"
    template_name = "educator_interface/panels/cohort_needs_attention.html"
    refresh_events = (COHORT_CHANGED,)


class CohortEducatorsPanel(Panel):
    title = "Educators"
    capability = "freedom_ls_learner_management.view_organisationmember"
    template_name = "educator_interface/panels/cohort_educators.html"
    refresh_events = (COHORT_CHANGED, MEMBER_CHANGED)

    def get_actions(self) -> list[PanelAction]:
        return [AddMemberToCohortAction()]

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context["educators"] = cohort_educators(cast(Cohort, self.instance))
        return context


class CohortSettingsPanel(Panel):
    title = "Settings"
    capability = "freedom_ls_learner_management.change_cohort"
    template_name = "educator_interface/panels/cohort_settings.html"
    refresh_events = (COHORT_CHANGED,)

    def get_actions(self) -> list[PanelAction]:
        cohort = cast(Cohort, self.instance)
        return [
            *cohort_state_actions(),
            DeleteEmptyCohortAction(
                success_url=_interface_path(cohort.organisation, "cohorts"),
            ),
        ]

    def get_context_data(self) -> dict[str, object]:
        cohort = cast(Cohort, self.instance)
        context = super().get_context_data()
        context["cohort"] = cohort
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
        "educators": CohortEducatorsPanel,
    }


class CohortTabSet(TabSet):
    title = "Cohort sections"
    children = {
        "overview": CohortOverviewStack,
        "learners": CohortLearnersPanel,
        "courses": CohortCoursesPanel,
        "settings": CohortSettingsPanel,
    }


class CohortInstanceView(InstanceView):
    panel = CohortTabSet
    header_refresh_events = (COHORT_CHANGED,)

    def get_status_badge(self) -> StatusBadge:
        return active_status_badge(cast(Cohort, self.instance).is_active)

    def get_stats(self) -> list[HeaderStat]:
        counts = cohort_counts(cast(Cohort, self.instance))
        return [
            HeaderStat("Learners", str(counts.learners)),
            HeaderStat("Courses", str(counts.courses)),
        ]

    def get_actions(self) -> list[PanelAction]:
        # The instance already carries its own organisation, so the success
        # URL needs nothing from the request.
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


class CreateCohortAction(CreateInstanceAction):
    label = "Create Cohort"
    form_class = CohortForm
    form_title = "Create Cohort"
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
        return _interface_path(self._organisation, f"cohorts/{instance.pk}")


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
        return [AddLearnersAction()]

    @classmethod
    def get_instance_label(cls, instance: Model) -> str:
        return cast(Learner, instance).user.display_name

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        organisation = cast(OrganisationScopedRequest, request).organisation
        if (
            not learners_visible_to(request.user, organisation, include_removed=True)
            .filter(pk=instance.pk)
            .exists()
        ):
            raise OrganisationScopeDenied


class ConversationDataTable(DataTable):
    """The educator's conversations with learners of the organisation.

    Rows are ConversationRow objects: the Status column needs each row's reply
    decision, which is decided for the whole page in one policy call so the
    query count does not follow the number of rows.
    """

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        scoped = cast(OrganisationScopedRequest, request)
        return conversations_in_organisation(
            cast(User, request.user), scoped.organisation
        )

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            Column(
                header="With",
                template="educator_interface/data-table-cells/conversation_with.html",
                text_attr="other.display_name",
                url_name="educator_interface:interface",
                url_path_template="messages/{conversation.pk}",
                htmx_nav=True,
                card="primary",
            ),
            Column(
                header="Last message",
                template="educator_interface/data-table-cells/conversation_last_message.html",
            ),
            Column(
                header="Status",
                template="educator_interface/data-table-cells/conversation_state.html",
            ),
        ]

    @classmethod
    def get_rows(
        cls, request: HttpRequest, queryset: QuerySet, query: TableQuery
    ) -> Page:
        page = super().get_rows(request, queryset, query)
        viewer = cast(User, request.user)
        conversations = list(page.object_list)
        decisions = reply_decisions(viewer=viewer, conversations=conversations)
        page.object_list = [
            ConversationRow(
                conversation=conversation,
                other=other_participant(conversation, viewer),
                can_reply=decisions[conversation.pk].allowed,
            )
            for conversation in conversations
        ]
        return page


class ConversationThreadPanel(Panel):
    """The conversation's thread, with its composer, inside the interface card."""

    model = Conversation
    template_name = "educator_interface/panels/conversation_thread.html"
    card_flush = True

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context.update(thread_context(self.request, cast(Conversation, self.instance)))
        organisation = cast(OrganisationScopedRequest, self.request).organisation
        context["back_url"] = _interface_path(organisation, "messages")
        return context


class NewMessageAction(PanelAction):
    """Starts a conversation with a learner of the organisation, in the app modal.

    The picker offers only learners the sender can see in this organisation
    and the policy lets them message, so a learner elsewhere looks the same as
    a name that does not exist.
    """

    label = "New message"
    action_name = "new_message"
    trigger_template_name = "panel_framework/partials/modal_trigger.html"
    template_name = "educator_interface/modal/new_message.html"

    def _candidates(self, ctx: PanelContext) -> QuerySet[User]:
        user = cast(User, ctx.request.user)
        organisation = cast(OrganisationScopedRequest, ctx.request).organisation
        site = cast(Site, get_cached_site(ctx.request))
        return (
            get_messaging_policy()
            .recipients_for(sender=user, site=site)
            .filter(pk__in=learners_visible_to(user, organisation).values("user_id"))
        )

    def _modal_context(
        self,
        ctx: PanelContext,
        recipient: User | None,
        *,
        client_key: UUID | None = None,
        draft: str = "",
        alert: str = "",
    ) -> dict[str, object]:
        action_url = self.get_action_url(ctx)
        context: dict[str, object] = {
            "recipient": recipient,
            "other": recipient,
            "search_url": action_url,
            "choose_url": action_url,
            "include_email": True,
            "in_modal": True,
        }
        if recipient is None:
            term = ctx.request.GET.get("q", "")
            context["term"] = term.strip()
            context["search"] = search_recipients(
                sender=cast(User, ctx.request.user),
                site=cast(Site, get_cached_site(ctx.request)),
                term=term,
                candidates=self._candidates(ctx),
                include_email=True,
                scope=cast(OrganisationScopedRequest, ctx.request).organisation,
            )
        else:
            context["composer"] = composer_context(
                client_key=client_key or uuid4(),
                draft=draft,
                alert=alert,
                recipient=recipient,
                action_url=action_url,
                in_modal=True,
            )
        return context

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        raw = ctx.request.GET.get("recipient")
        if raw is None:
            return self._modal_context(ctx, None)
        recipient = get_object_or_404(self._candidates(ctx), pk=_recipient_pk(raw))
        return self._modal_context(ctx, recipient)

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        request = ctx.request
        recipient = get_object_or_404(
            self._candidates(ctx), pk=_recipient_pk(request.POST.get("recipient"))
        )
        try:
            client_key = UUID(request.POST.get("client_key", ""))
        except ValueError:
            return HttpResponseBadRequest("client_key must be a UUID")
        draft = request.POST.get("body", "")
        result = send_message(
            sender=cast(User, request.user),
            body=draft,
            client_key=client_key,
            site=cast(Site, get_cached_site(request)),
            recipient=recipient,
        )
        if result.message is not None:
            organisation = cast(OrganisationScopedRequest, request).organisation
            conversation = cast(Conversation, result.conversation)
            return navigation_response(
                _interface_path(organisation, f"messages/{conversation.pk}")
            )
        alert = result.body_error or refusal_alert_copy(result.refusal, recipient)
        return render(
            request,
            self.template_name,
            self._modal_context(
                ctx, recipient, client_key=client_key, draft=draft, alert=alert
            ),
            status=422,
        )


def _recipient_pk(raw: str | None) -> int:
    try:
        return int(raw or "")
    except ValueError:
        raise Http404("recipient must be a user id") from None


class ConversationInstanceView(InstanceView):
    panel = ConversationThreadPanel

    def get_actions(self) -> list[PanelAction]:
        return [NewMessageAction()]


class MessagesConfig(OrganisationSectionConfig, ListViewConfig):
    url_name = "messages"
    menu_label = "Messages"
    icon = "message"
    model = Conversation
    list_view = ConversationDataTable
    table_key = "conversations"
    instance_view = ConversationInstanceView

    @classmethod
    def get_actions(cls, request: HttpRequest) -> list[PanelAction]:
        return [NewMessageAction()]

    @classmethod
    def is_available(cls, request: HttpRequest) -> bool:
        return comms_config.MESSAGING_ENABLED

    @classmethod
    def get_menu_count_url(cls, request: HttpRequest) -> str | None:
        organisation = cast(OrganisationScopedRequest, request).organisation
        return reverse(
            "educator_interface:messages_unread_count",
            kwargs={"organisation_slug": organisation.slug},
        )

    @classmethod
    def get_menu_count_poll_seconds(cls) -> int:
        return comms_config.MESSAGE_INBOX_POLL_SECONDS

    @classmethod
    def get_instance_view(cls, request: HttpRequest, pk: str) -> InstanceView:
        """The instance view over the educator's own copy of the conversation.

        Loaded through the inbox query after authorisation, so the other
        participant is already on the instance for the heading and the thread.
        """
        authorised = super().get_instance_view(request, pk)
        conversation = inbox_for(cast(User, request.user)).get(
            pk=authorised.instance.pk
        )
        return cls.instance_view(conversation)

    @classmethod
    def get_instance_label(cls, instance: Model) -> str:
        participants = getattr(instance, "other_participants", None)
        return participants[0].user.display_name if participants else "Deleted user"

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        organisation = cast(OrganisationScopedRequest, request).organisation
        if (
            not conversations_in_organisation(cast(User, request.user), organisation)
            .filter(pk=instance.pk)
            .exists()
        ):
            raise OrganisationScopeDenied


class CourseDataTable(DataTable):
    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        # Courses are shared across the site, so the list, the counts and the
        # cells are all read through the organisation in view: the cohorts and
        # learners counted and linked on each row are narrowed to what this
        # educator may see, and another organisation's cohorts never show
        # through a shared course.
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
    fields = ["title", "dashboard_category"]


class CourseCohortRegistrationDataTable(DataTable):
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
    title = "Cohort Registrations"
    data_table = CourseCohortRegistrationDataTable
    table_key = "cohort_registrations"

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).filter(course=self.instance)


class CourseLearnerRegistrationDataTable(DataTable):
    default_sort = "learner__user__first_name"

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        # Courses are shared across the site, so the registrations are scoped through the organisation's learners rather than through the course.
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
    title = "Direct Registrations"
    data_table = CourseLearnerRegistrationDataTable
    table_key = "learner_registrations"

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).filter(course=self.instance)


class CoursePanelStack(PanelStack):
    children = {
        "details": CourseDetailsPanel,
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


class DashboardPanel(Panel):
    title = "Reporting"
    template_name = "educator_interface/panels/dashboard.html"


class DashboardConfig(OrganisationSectionConfig, BaseViewConfig):
    url_name = "dashboard"
    menu_label = "Dashboard"
    icon = "home"
    panel = DashboardPanel


class MemberDataTable(DataTable):
    search_fields = ["first_name", "last_name", "email"]
    default_sort = "first_name"
    empty_state_template = "educator_interface/partials/members_empty.html"

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        organisation = cast(OrganisationScopedRequest, request).organisation
        return members_of(organisation).prefetch_related(
            Prefetch(
                "object_role_assignments",
                queryset=member_assignments(organisation)
                .select_related("assigned_by")
                .prefetch_related("target"),
                to_attr="held_assignments",
            ),
            Prefetch(
                "organisationmember_set",
                queryset=OrganisationMember.objects.filter(organisation=organisation),
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
        return [MemberRoleFilter()]

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
            row.role_entries = member_role_entries(row, site)
            row.is_suspended = not any(m.is_active for m in row.member_rows)
        return page_obj

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            Column(
                header="Member",
                template="educator_interface/data-table-cells/member.html",
                sortable=True,
                sort_field="first_name",
                card="primary",
            ),
            Column(
                header="Roles",
                template="educator_interface/data-table-cells/member_roles.html",
                card="secondary",
            ),
            Column(
                header="",
                template="educator_interface/data-table-cells/member_actions.html",
                card="secondary",
            ),
        ]

    @staticmethod
    def get_row_label(row: Model) -> str:
        return cast(User, row).display_name


class MemberConfig(OrganisationSectionConfig, ListViewConfig):
    url_name = "members"
    menu_label = "Members"
    icon = "user"
    model = User
    list_view = MemberDataTable
    table_key = "members"
    view_capability = "freedom_ls_learner_management.view_organisationmember"
    # Rows have no page of their own, so there is nothing to authorise.
    check_access_exempt_reason = "members have no instance pages"

    intro_template_name = "educator_interface/partials/members_intro.html"
    refresh_events = (MEMBER_CHANGED,)

    @classmethod
    def get_actions(cls, request: HttpRequest) -> list[PanelAction]:
        return [
            AddMemberAction(),
            RemoveRoleAction(),
            ChangeCohortsAction(),
            SuspendMemberAction(),
            ReactivateMemberAction(),
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
        members = members_of(scoped.organisation)
        return {
            "roles": [config[role] for role in MEMBER_ROLES],
            # One query: the first two member pks are the viewer's alone only
            # when the viewer is the sole member.
            "only_member_is_viewer": set(members.values_list("pk", flat=True)[:2])
            == {scoped.user.pk},
        }


interface_config = [
    NavGroup(
        "Teaching",
        [DashboardConfig, CohortConfig, LearnerConfig, CourseConfig, MessagesConfig],
    ),
    NavGroup("Administration", [MemberConfig]),
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


@login_required
def messages_unread_count(request: HttpRequest, organisation_slug: str) -> HttpResponse:
    """The Messages nav item's count: the unread conversations of the organisation.

    The body is empty for zero so the sidebar shows no badge.
    """
    if not comms_config.MESSAGING_ENABLED:
        raise Http404
    user = cast(User, request.user)
    organisation = _resolve_organisation(user, organisation_slug)
    unread = (
        conversations_in_organisation(user, organisation)
        .filter(Q(is_unread=True))
        .count()
    )
    return HttpResponse(badge_count(unread) if unread else "")


@login_required
def interface(
    request: HttpRequest, organisation_slug: str, path_string: str = ""
) -> HttpResponse | StreamingHttpResponse:
    """Resolve and authorise the organisation named in the URL, once.

    Selecting an organisation is an authorisation decision, not a filter:
    unlike Site, which is derived from the request host and cannot be
    forged, an organisation comes from user-supplied URL input. "No such
    slug" and "slug exists but you have no access" both 404 identically — a
    403 would confirm the slug is real and let an attacker enumerate a
    Site's organisation names.
    """
    organisation = _resolve_organisation(cast(User, request.user), organisation_slug)
    scoped_request = cast(OrganisationScopedRequest, request)
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
