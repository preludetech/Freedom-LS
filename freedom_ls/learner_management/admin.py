from typing import cast
from urllib.parse import urlencode
from uuid import UUID

from unfold.admin import TabularInline

from django import forms
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.admin.widgets import AutocompleteSelect
from django.db import models
from django.http import HttpRequest
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import ngettext

from freedom_ls.organisations.admin import (
    ORGANISATION_SUMMARIES,
    OrganisationAdmin,
)
from freedom_ls.organisations.models import Organisation
from freedom_ls.site_aware_models.admin import (
    GuardedSiteAwareModelAdmin,
    SiteAwareModelAdmin,
)

from .forms import (
    CohortAdminForm,
    CohortCourseRegistrationAdminForm,
    LearnerAdminForm,
    LearnerCourseRegistrationAdminForm,
)
from .models import (
    Cohort,
    CohortCourseRegistration,
    CohortDeadline,
    CohortMembership,
    Learner,
    LearnerCohortDeadlineOverride,
    LearnerCourseRegistration,
    LearnerDeadline,
)

SCOPE_TO_ORGANISATION_OF_COHORT = "organisation_of_cohort"
SCOPE_TO_MEMBERS_OF_COHORT = "members_of_cohort"

_SCOPE_LOOKUPS = {
    SCOPE_TO_ORGANISATION_OF_COHORT: "organisation__cohort__id",
    SCOPE_TO_MEMBERS_OF_COHORT: "cohortmembership__cohort_id",
}


def narrow_learners(
    learners: models.QuerySet[Learner], scope: str, cohort_id: str | UUID
) -> models.QuerySet[Learner]:
    """The learners a cohort admits under ``scope``, removed ones included.

    One definition for both halves of the rule -- the options a dropdown offers
    and the queryset that validates what comes back. If they drifted, someone
    would be offered a learner the form then refuses.
    """
    return learners.filter(**{_SCOPE_LOOKUPS[scope]: cohort_id})


def _cohort_of_registration(registration_id: str | None) -> UUID | None:
    """The cohort a CohortCourseRegistration belongs to, by its admin
    ``object_id``. None when the id is absent or does not name a registration
    on this site -- the change view 404s on it moments later anyway."""
    if not registration_id:
        return None
    try:
        pk = UUID(registration_id)
    except ValueError:
        return None
    return (
        CohortCourseRegistration.objects.filter(pk=pk)
        .values_list("cohort_id", flat=True)
        .first()
    )


class ScopedLearnerAutocompleteSelect(AutocompleteSelect):
    """Names a cohort scope on the autocomplete URL's querystring.

    Every learner dropdown in the admin is served by one shared endpoint, which
    builds its results from LearnerAdmin.get_search_results and never sees an
    inline's narrowed formfield queryset. The scope has to travel in the URL
    for that endpoint to be able to honour it.
    """

    def __init__(
        self,
        field: models.ForeignKey,
        admin_site: AdminSite,
        scope: str,
        cohort_id: str | UUID,
    ) -> None:
        super().__init__(field, admin_site)
        self.scope = scope
        self.cohort_id = cohort_id

    def get_url(self) -> str:
        # select2 fetches this through jQuery.ajax, which appends its own
        # term/page/app_label/model_name/field_name to a URL that already
        # carries a querystring rather than replacing it.
        return f"{super().get_url()}?{urlencode({self.scope: str(self.cohort_id)})}"


@admin.register(Learner)
class LearnerAdmin(SiteAwareModelAdmin):
    form = LearnerAdminForm
    list_display = ["user", "organisation", "is_active", "created_at"]
    list_filter = ["organisation", "is_active"]
    readonly_fields = ["created_at"]
    search_fields = ["user__first_name", "user__last_name", "user__email"]
    autocomplete_fields = ["user", "organisation"]
    # Matches the "<email> - <organisation>" label a learner dropdown renders.
    # The autocomplete endpoint paginates, so without a stable order its second
    # page can repeat or skip a learner.
    ordering = ["user__email", "organisation__name"]

    def has_delete_permission(
        self, request: HttpRequest, obj: Learner | None = None
    ) -> bool:
        return False

    def get_search_results(
        self,
        request: HttpRequest,
        queryset: models.QuerySet[Learner],
        search_term: str,
    ) -> tuple[models.QuerySet[Learner], bool]:
        """Honour the cohort scope a learner dropdown put on its URL.

        The scope arrives as a query param because one endpoint serves every
        learner dropdown in the admin. Only ScopedLearnerAutocompleteSelect
        emits these param names -- the changelist rejects GET params it does
        not recognise before it gets here -- so their presence is enough to
        tell the two apart.

        The filter can only intersect what get_queryset already returned, which
        the site-aware manager has narrowed to the current site. A tampered
        param can therefore empty the results or swap them for another
        organisation's learners, both of which this staff user can already read
        off the Learners changelist; it can never widen them.
        """
        queryset, may_have_duplicates = super().get_search_results(
            request, queryset, search_term
        )
        for scope in _SCOPE_LOOKUPS:
            raw_cohort_id = request.GET.get(scope)
            if raw_cohort_id is None:
                continue
            try:
                cohort_id = UUID(raw_cohort_id)
            except ValueError:
                # A scope that is present but unusable means a hand-edited URL.
                # Offer nothing: falling through unscoped would reopen the very
                # gap this closes, and the ORM would reject it anyway on a UUID
                # primary key.
                return queryset.none(), may_have_duplicates
            queryset = narrow_learners(queryset, scope, cohort_id)
        return queryset, may_have_duplicates


class CohortMembershipInline(TabularInline):
    model = CohortMembership
    extra = 1
    autocomplete_fields = ["learner"]
    fields = ["learner"]

    def formfield_for_foreignkey(
        self,
        db_field: models.ForeignKey,
        request: HttpRequest,
        **kwargs: object,
    ) -> forms.ModelChoiceField | None:
        # Two halves of one rule, both on the change page only -- `object_id`
        # isn't in the URL kwargs on the add page, and there is no cohort to
        # scope to until the form is saved. The queryset validates the learner
        # that comes back; the widget scopes the options offered, which
        # otherwise come unfiltered from the shared autocomplete endpoint.
        # Removed learners must stay in the queryset -- it also validates the
        # inline rows that already exist, so excluding them would make a cohort
        # holding one impossible to save.
        if db_field.name == "learner" and request.resolver_match:
            cohort_id = request.resolver_match.kwargs.get("object_id")
            if cohort_id:
                kwargs["queryset"] = narrow_learners(
                    Learner.objects.all(), SCOPE_TO_ORGANISATION_OF_COHORT, cohort_id
                )
                kwargs["widget"] = ScopedLearnerAutocompleteSelect(
                    db_field,
                    self.admin_site,
                    SCOPE_TO_ORGANISATION_OF_COHORT,
                    cohort_id,
                )
        return cast(
            "forms.ModelChoiceField | None",
            super().formfield_for_foreignkey(db_field, request, **kwargs),
        )


class CohortCourseRegistrationInline(TabularInline):
    model = CohortCourseRegistration
    extra = 0
    autocomplete_fields = ["course"]
    fields = ["course", "is_active", "registered_at"]
    readonly_fields = ["registered_at"]

    verbose_name = "Course Registration"
    verbose_name_plural = "Course Registrations"


@admin.register(Cohort)
class CohortAdmin(GuardedSiteAwareModelAdmin):
    form = CohortAdminForm
    list_display = ["name"]
    search_fields = ["name"]
    autocomplete_fields = ["organisation"]
    inlines = [CohortMembershipInline, CohortCourseRegistrationInline]
    # @claude: GuardedSiteAwareModelAdmin combines Unfold's ModelAdmin with
    # guardian's GuardedModelAdmin. The admin_guardian resource warns this pairing
    # isn't guaranteed by either package (overlapping templates/hooks) — someone
    # needs to manually load this model's guardian object-permissions page in the
    # browser and confirm it renders correctly under the unfold theme before this
    # comment can be removed.


class LearnerDeadlineInline(TabularInline):
    model = LearnerDeadline
    extra = 0
    fields = ["content_type", "object_id", "deadline", "is_hard_deadline"]

    verbose_name = "Deadline"
    verbose_name_plural = "Deadlines"


@admin.register(LearnerCourseRegistration)
class LearnerCourseRegistrationAdmin(SiteAwareModelAdmin):
    form = LearnerCourseRegistrationAdminForm
    list_display = ["get_user_name", "course", "is_active", "registered_at"]
    list_select_related = ["learner__user", "course"]
    list_filter = ["is_active", "registered_at"]
    search_fields = [
        "learner__user__email",
        "learner__user__first_name",
        "learner__user__last_name",
        "course__title",
    ]
    autocomplete_fields = ["learner", "course"]
    readonly_fields = ["registered_at"]
    inlines = [LearnerDeadlineInline]

    fieldsets = (
        (None, {"fields": ("learner", "course", "is_active")}),
        ("Timestamps", {"fields": ("registered_at",), "classes": ("collapse",)}),
    )

    @admin.display(description="User", ordering="learner__user__first_name")
    def get_user_name(self, obj: LearnerCourseRegistration) -> str:
        """Display user's full name."""
        user = obj.learner.user
        if user.first_name or user.last_name:
            return f"{user.first_name} {user.last_name}".strip()
        return user.email


class CohortDeadlineInline(TabularInline):
    model = CohortDeadline
    extra = 0
    fields = ["content_type", "object_id", "deadline", "is_hard_deadline"]

    verbose_name = "Deadline"
    verbose_name_plural = "Deadlines"


class LearnerCohortDeadlineOverrideInline(TabularInline):
    model = LearnerCohortDeadlineOverride
    extra = 0
    autocomplete_fields = ["learner"]
    fields = ["learner", "content_type", "object_id", "deadline", "is_hard_deadline"]

    verbose_name = "User Deadline Override"
    verbose_name_plural = "User Deadline Overrides"

    def formfield_for_foreignkey(
        self,
        db_field: models.ForeignKey,
        request: HttpRequest,
        **kwargs: object,
    ) -> forms.ModelChoiceField | None:
        # An override only makes sense for a member of the registration's own
        # cohort, which is what the model already insists on. Scope both the
        # options offered and the queryset that validates them to those
        # members. The parent's `object_id` names the registration, not the
        # cohort, so the cohort is looked up; on the add page there is no
        # `object_id` and therefore nothing to scope to.
        if db_field.name == "learner" and request.resolver_match:
            registration_id = request.resolver_match.kwargs.get("object_id")
            cohort_id = _cohort_of_registration(registration_id)
            if cohort_id:
                kwargs["queryset"] = narrow_learners(
                    Learner.objects.all(), SCOPE_TO_MEMBERS_OF_COHORT, cohort_id
                )
                kwargs["widget"] = ScopedLearnerAutocompleteSelect(
                    db_field, self.admin_site, SCOPE_TO_MEMBERS_OF_COHORT, cohort_id
                )
        return cast(
            "forms.ModelChoiceField | None",
            super().formfield_for_foreignkey(db_field, request, **kwargs),
        )


@admin.register(CohortCourseRegistration)
class CohortCourseRegistrationAdmin(SiteAwareModelAdmin):
    form = CohortCourseRegistrationAdminForm
    list_display = ["cohort", "course", "is_active", "registered_at"]
    list_select_related = ["cohort", "course"]
    list_filter = ["is_active", "registered_at"]
    search_fields = ["cohort__name", "course__title"]
    autocomplete_fields = ["cohort", "course"]
    readonly_fields = ["registered_at"]
    inlines = [CohortDeadlineInline, LearnerCohortDeadlineOverrideInline]

    fieldsets = (
        (None, {"fields": ("cohort", "course", "is_active")}),
        ("Timestamps", {"fields": ("registered_at",), "classes": ("collapse",)}),
    )


@admin.register(CohortDeadline)
class CohortDeadlineAdmin(SiteAwareModelAdmin):
    list_display = [
        "get_cohort_name",
        "get_course_name",
        "get_content_item",
        "deadline",
        "is_hard_deadline",
    ]
    list_select_related = [
        "cohort_course_registration__cohort",
        "cohort_course_registration__course",
    ]
    list_filter = [
        "cohort_course_registration__cohort",
        "cohort_course_registration__course",
        "is_hard_deadline",
    ]
    search_fields = [
        "cohort_course_registration__cohort__name",
        "cohort_course_registration__course__title",
    ]
    autocomplete_fields = ["cohort_course_registration"]

    @admin.display(
        description="Cohort", ordering="cohort_course_registration__cohort__name"
    )
    def get_cohort_name(self, obj: CohortDeadline) -> str:
        return obj.cohort_course_registration.cohort.name

    @admin.display(
        description="Course", ordering="cohort_course_registration__course__title"
    )
    def get_course_name(self, obj: CohortDeadline) -> str:
        return obj.cohort_course_registration.course.title

    @admin.display(description="Content Item")
    def get_content_item(self, obj: CohortDeadline) -> str:
        return str(obj.content_item) if obj.content_item else "Whole course"


@admin.register(LearnerDeadline)
class LearnerDeadlineAdmin(SiteAwareModelAdmin):
    list_display = [
        "get_user_name",
        "get_course_name",
        "get_content_item",
        "deadline",
        "is_hard_deadline",
    ]
    list_select_related = [
        "learner_course_registration__learner__user",
        "learner_course_registration__course",
    ]
    list_filter = [
        "learner_course_registration__course",
        "is_hard_deadline",
    ]
    search_fields = [
        "learner_course_registration__learner__user__first_name",
        "learner_course_registration__learner__user__last_name",
        "learner_course_registration__course__title",
    ]
    autocomplete_fields = ["learner_course_registration"]

    @admin.display(description="User")
    def get_user_name(self, obj: LearnerDeadline) -> str:
        return str(obj.learner_course_registration.learner.user)

    @admin.display(description="Course")
    def get_course_name(self, obj: LearnerDeadline) -> str:
        return obj.learner_course_registration.course.title

    @admin.display(description="Content Item")
    def get_content_item(self, obj: LearnerDeadline) -> str:
        return str(obj.content_item) if obj.content_item else "Whole course"


@admin.register(LearnerCohortDeadlineOverride)
class LearnerCohortDeadlineOverrideAdmin(SiteAwareModelAdmin):
    list_display = [
        "get_user_name",
        "get_cohort_name",
        "get_course_name",
        "get_content_item",
        "deadline",
        "is_hard_deadline",
    ]
    list_select_related = [
        "learner__user",
        "cohort_course_registration__cohort",
        "cohort_course_registration__course",
    ]
    list_filter = [
        "cohort_course_registration__cohort",
        "cohort_course_registration__course",
        "is_hard_deadline",
    ]
    search_fields = [
        "learner__user__first_name",
        "learner__user__last_name",
        "cohort_course_registration__cohort__name",
        "cohort_course_registration__course__title",
    ]
    autocomplete_fields = ["cohort_course_registration", "learner"]

    @admin.display(description="User")
    def get_user_name(self, obj: LearnerCohortDeadlineOverride) -> str:
        return str(obj.learner.user)

    @admin.display(description="Cohort")
    def get_cohort_name(self, obj: LearnerCohortDeadlineOverride) -> str:
        return obj.cohort_course_registration.cohort.name

    @admin.display(description="Course")
    def get_course_name(self, obj: LearnerCohortDeadlineOverride) -> str:
        return obj.cohort_course_registration.course.title

    @admin.display(description="Content Item")
    def get_content_item(self, obj: LearnerCohortDeadlineOverride) -> str:
        return str(obj.content_item) if obj.content_item else "Whole course"


class OrganisationCohortInline(TabularInline):
    """An organisation's cohorts, editable from its own admin page.

    Contributed to OrganisationAdmin at the bottom of this module. A cohort's
    members and course registrations stay on the cohort's own page, which
    `show_change_link` reaches from each row.
    """

    model = Cohort
    fields = ["name"]
    # per_page hands the queryset to a Paginator, which reorders nothing of its
    # own: without an order here its pages would repeat and skip rows.
    ordering = ["name"]
    extra = 0
    per_page = 20
    show_count = True
    show_change_link = True
    tab = True


class OrganisationLearnerInline(TabularInline):
    """An organisation's learners, read-only and paginated.

    One organisation can hold thousands, so the rows page rather than render in
    a single block, and `organisation_learner_search_link` covers finding a
    particular one -- an inline has no search of its own. Read-only because a
    learner is edited on their own page, which each row links to; this list is
    for looking.
    """

    model = Learner
    fields = ["user", "is_active", "created_at"]
    readonly_fields = fields
    ordering = ["user__email"]
    extra = 0
    max_num = 0
    can_delete = False
    per_page = 25
    show_count = True
    show_change_link = True
    tab = True

    def has_add_permission(
        self, request: HttpRequest, obj: Organisation | None = None
    ) -> bool:
        return False

    def get_queryset(self, request: HttpRequest) -> models.QuerySet[Learner]:
        # Every row renders its learner's user, and the row title renders it
        # again -- one query per row without this.
        learners: models.QuerySet[Learner] = super().get_queryset(request)
        return learners.select_related("user")


def organisation_learner_search_link(organisation: Organisation) -> str:
    """A link to the Learners changelist, narrowed to this organisation.

    The inline above pages through learners but cannot search them.
    `LearnerAdmin.list_filter` already carries `organisation`, so the changelist
    -- which does search, filtering and bulk actions -- is one link away.
    """
    count = Learner.objects.filter(organisation=organisation).count()
    if not count:
        return "No learners yet"
    label = ngettext(
        "Search this organisation's 1 learner",
        "Search this organisation's %(count)d learners",
        count,
    ) % {"count": count}
    query = urlencode({"organisation__id__exact": str(organisation.pk)})
    return format_html(
        '<a href="{}?{}" class="text-primary-600 dark:text-primary-500">{}</a>',
        reverse("admin:freedom_ls_learner_management_learner_changelist"),
        query,
        label,
    )


# Cohorts and learners on the Organisation change page, through the two seams
# OrganisationAdmin declares for it. The wiring runs from here rather than from
# `organisations`, which sits below this app in docs/app_structure.md and cannot
# import Cohort or Learner without making the dependency a cycle.
OrganisationAdmin.inlines = [OrganisationCohortInline, OrganisationLearnerInline]
ORGANISATION_SUMMARIES.append(organisation_learner_search_link)
