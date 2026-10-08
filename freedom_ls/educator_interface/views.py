from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast
from uuid import UUID

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Page
from django.db.models import Count, F, Model, Prefetch, Q, QuerySet
from django.http import Http404, HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.actions import (
    DeleteEmptyCohortAction,
    EditCohortAction,
    cohort_not_empty_sentence,
    cohort_state_actions,
)
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    EDUCATOR_CHANGED,
    LEARNER_CHANGED,
    REGISTRATION_CHANGED,
)
from freedom_ls.educator_interface.exceptions import OrganisationScopeDenied
from freedom_ls.educator_interface.filters import (
    ShowInactiveFilter,
    VisibleCourseFilter,
)
from freedom_ls.educator_interface.forms import CohortForm
from freedom_ls.educator_interface.quick_views import CohortQuickView, LearnerQuickView
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    active_organisation_admins,
    cohort_course_count,
    cohort_educators,
    cohort_is_empty,
    cohort_learner_count,
    cohorts_visible_to,
    courses_visible_to,
    learners_visible_to,
    organisations_accessible_to,
)
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.actions import (
    CreateInstanceAction,
    PanelAction,
)
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
) -> Column:
    """A link column into the educator interface, the shape every table's
    name/title column shares. The link always navigates to the row's page;
    quick_view adds a trigger beside it that opens the row in the quick-view
    drawer instead."""
    return Column(
        header=header,
        template="cotton/data-table-cells/link.html",
        text_attr=text_attr,
        url_name="educator_interface:interface",
        url_path_template=path_template,
        htmx_nav=True,
        quick_view=quick_view,
        sortable=sortable,
        card=card,
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
                template="cotton/data-table-cells/text.html",
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
        if cls.get_filters() and "inactive" not in query.filters:
            queryset = queryset.filter(is_active=True)
        queryset = super().filter_queryset(request, queryset, query)
        if query.sort:
            # Keep the default tie-breaker under a sort, or pages repeat and
            # skip rows when several cohorts share a value.
            queryset = queryset.order_by(query.sort, "name", "pk")
        return queryset


class LearnerCohortDataTable(CohortDataTable):
    """The learner page's cohorts: every cohort the learner belongs to, active
    or not, with search, sort and pagination but no filters."""

    @classmethod
    def get_filters(cls) -> list[TableFilter]:
        return []


class LearnerDataTable(DataTable):
    search_fields = ["user__first_name", "user__last_name", "user__email"]

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        request = cast(OrganisationScopedRequest, request)
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
    def get_columns() -> list[Column]:
        return [
            _interface_link(
                "First Name",
                "user.first_name",
                "learners/{pk}",
                sortable=True,
                card="primary",
                quick_view=True,
            ),
            _interface_link(
                "Last Name",
                "user.last_name",
                "learners/{pk}",
                sortable=True,
            ),
            Column(
                header="Email",
                template="cotton/data-table-cells/text.html",
                attr="user.email",
                # sortable=True,
                card="md_only",
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
                header="Registered Courses",
                template="educator_interface/data-table-cells/learner_courses.html",
            ),
        ]


class LearnerDetailsPanel(InstanceDetailsPanel):
    model = Learner
    fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
    ]
    refresh_events = (LEARNER_CHANGED,)


class LearnerCohortsPanel(DataTablePanel):
    title = "Cohorts"
    data_table = LearnerCohortDataTable
    table_key = "cohorts"
    refresh_events = (LEARNER_CHANGED,)

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return (
            super()
            .get_queryset(request)
            .filter(cohortmembership__learner=self.instance)
        )


class LearnerPanelStack(PanelStack):
    children = {
        "details": LearnerDetailsPanel,
        "cohorts": LearnerCohortsPanel,
    }


class LearnerInstanceView(InstanceView):
    panel = LearnerPanelStack


def _interface_path(organisation: Organisation, path_string: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": path_string},
    )


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
        context["cohort_learner_count"] = cohort_learner_count(cohort)
        context["cohort_course_count"] = cohort_course_count(cohort)
        return context


class CohortCourseRegistrationDataTable(DataTable):
    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        organisation = cast(OrganisationScopedRequest, request).organisation
        return (
            CohortCourseRegistration.objects.select_related("course")
            .filter(cohort__organisation=organisation)
            .order_by("course__title")
        )

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            _interface_link(
                "Course", "course.title", "courses/{course.pk}", card="primary"
            ),
            *_registration_columns(),
        ]


class CohortLearnersPanel(DataTablePanel):
    title = "Learners"
    data_table = LearnerDataTable
    table_key = "learners"
    refresh_events = (COHORT_CHANGED,)

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return (
            super().get_queryset(request).filter(cohortmembership__cohort=self.instance)
        )

    def get_tab_count(self) -> int | None:
        return self.get_queryset(self.request).count()


class CourseRegistrationsPanel(DataTablePanel):
    title = "Course Registrations"
    data_table = CohortCourseRegistrationDataTable
    table_key = "course_registrations"
    refresh_events = (COHORT_CHANGED,)

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).filter(cohort=self.instance)


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
    refresh_events = (COHORT_CHANGED, EDUCATOR_CHANGED)

    def get_actions(self) -> list[PanelAction]:
        return []

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
        context["is_empty"] = cohort_is_empty(cohort)
        context["not_empty_sentence"] = (
            "" if context["is_empty"] else cohort_not_empty_sentence(cohort)
        )
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
        "courses": CourseRegistrationsPanel,
        "settings": CohortSettingsPanel,
    }


class CohortInstanceView(InstanceView):
    panel = CohortTabSet

    def get_status_badge(self) -> StatusBadge:
        return active_status_badge(cast(Cohort, self.instance).is_active)

    def get_stats(self) -> list[HeaderStat]:
        cohort = cast(Cohort, self.instance)
        return [
            HeaderStat("Learners", str(cohort_learner_count(cohort))),
            HeaderStat("Courses", str(cohort_course_count(cohort))),
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
    def get_instance_label(cls, instance: Model) -> str:
        return cast(Learner, instance).user.display_name

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        organisation = cast(OrganisationScopedRequest, request).organisation
        if (
            not learners_visible_to(request.user, organisation)
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
            _interface_link(
                "First Name",
                "learner.user.first_name",
                "learners/{learner.pk}",
                card="primary",
                quick_view=True,
            ),
            _interface_link(
                "Last Name",
                "learner.user.last_name",
                "learners/{learner.pk}",
            ),
            Column(
                header="Email",
                template="cotton/data-table-cells/text.html",
                attr="learner.user.email",
                card="md_only",
            ),
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


interface_config = [
    NavGroup("Teaching", [DashboardConfig, CohortConfig, LearnerConfig, CourseConfig]),
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
    organisation = get_object_or_404(Organisation, slug=organisation_slug)
    if (
        not organisations_accessible_to(request.user)
        .filter(pk=organisation.pk)
        .exists()
    ):
        raise Http404
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
