from __future__ import annotations

from typing import cast
from uuid import UUID

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Page
from django.db.models import Count, Model, Prefetch, Q, QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.exceptions import OrganisationScopeDenied
from freedom_ls.educator_interface.forms import CohortForm
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    cohorts_visible_to,
    learners_visible_to,
    organisations_accessible_to,
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
    PanelStack,
    TabSet,
)
from freedom_ls.panel_framework.tables import DataTable
from freedom_ls.panel_framework.views import (
    BaseViewConfig,
    InstanceView,
    ListViewConfig,
    NavGroup,
    panel_framework_view,
    sections_by_url_name,
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
    model = Learner
    fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
    ]


class LearnerCohortsPanel(DataTablePanel):
    title = "Cohorts"
    data_table = CohortDataTable

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


class CohortDetailsPanel(InstanceDetailsPanel):
    model = Cohort
    fields = ["name"]
    editable = True
    form_class = CohortForm

    def get_actions(self) -> list[PanelAction]:
        # The instance already carries its own organisation, so the success
        # URL needs nothing from the request.
        cohort = cast(Cohort, self.instance)
        return [
            *super().get_actions(),
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


class CohortCourseRegistrationDataTable(DataTable):
    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        organisation = cast(_OrganisationScopedRequest, request).organisation
        return (
            CohortCourseRegistration.objects.select_related("course")
            .filter(cohort__organisation=organisation)
            .order_by("course__title")
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

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return (
            super().get_queryset(request).filter(cohortmembership__cohort=self.instance)
        )


class CourseRegistrationsPanel(DataTablePanel):
    title = "Course Registrations"
    data_table = CohortCourseRegistrationDataTable

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).filter(cohort=self.instance)


class CohortDetailsStack(PanelStack):
    title = "Details"
    children = {
        "details": CohortDetailsPanel,
        "courses": CourseRegistrationsPanel,
        "learners": CohortLearnersPanel,
    }


class CohortTabSet(TabSet):
    title = "Cohort sections"
    children = {"details": CohortDetailsStack}


class CohortInstanceView(InstanceView):
    panel = CohortTabSet


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
    icon = "cohort"
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
    icon = "user"
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
        cls, request: HttpRequest, columns: list[dict], queryset: QuerySet
    ) -> Page:
        page_obj = super().get_rows(request, columns, queryset)
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
    model = Course
    fields = ["title", "dashboard_category"]


class CourseCohortRegistrationDataTable(DataTable):
    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        organisation = cast(_OrganisationScopedRequest, request).organisation
        return (
            CohortCourseRegistration.objects.select_related("cohort", "course")
            .filter(cohort__organisation=organisation)
            .order_by("cohort__name")
        )

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

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).filter(course=self.instance)


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


class CourseConfig(ListViewConfig):
    url_name = "courses"
    menu_label = "Courses"
    icon = "course"
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


class DashboardPanel(Panel):
    title = "Reporting"
    template_name = "educator_interface/panels/dashboard.html"


class DashboardConfig(BaseViewConfig):
    url_name = "dashboard"
    menu_label = "Dashboard"
    icon = "home"
    panel = DashboardPanel

    required_request_attrs = ("organisation",)


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
