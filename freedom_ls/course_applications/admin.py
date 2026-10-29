"""Admin for course applications."""

from __future__ import annotations

from unfold.contrib.filters.admin import AutocompleteSelectFilter

from django.contrib import admin
from django.db.models import Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.utils import formats, timezone
from django.utils.safestring import SafeString

from freedom_ls.accounts.admin import USER_ERASURE_CASCADE_MODELS
from freedom_ls.form_engine.admin import answers_context
from freedom_ls.site_aware_models.admin import (
    SiteAwareExportModelAdmin,
    SiteAwareModelAdmin,
    admin_change_link,
)
from freedom_ls.site_aware_models.admin_filters import InclusiveRangeDateTimeFilter

from .erasure import erase_anonymous_applicant
from .models import AnonymousApplicant, CourseApplication
from .resources import CourseApplicationResource

# The admin below denies delete so nobody can thin out applications one by one.
# Erasing the applicant is the one path that must take them along, and the User
# admin only vouches for the models named here.
USER_ERASURE_CASCADE_MODELS.add(CourseApplication)
USER_ERASURE_CASCADE_MODELS.add(AnonymousApplicant)


class CourseApplicationSubmittedFilter(admin.SimpleListFilter):
    """Submitted or draft, by the same rule as CourseApplication.is_submitted.

    An application with no sitting was submitted the moment it was created, so
    "submitted" is an OR over two shapes and the shared completion filter, which
    tests one timestamp, cannot express it.
    """

    title = "submitted"
    parameter_name = "submitted"

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin
    ) -> list[tuple[str, str]]:
        return [("submitted", "Submitted"), ("draft", "Draft")]

    def queryset(
        self, request: HttpRequest, queryset: QuerySet[CourseApplication]
    ) -> QuerySet[CourseApplication]:
        if self.value() == "submitted":
            return queryset.filter(
                Q(form_progress__isnull=True)
                | Q(form_progress__completed_time__isnull=False)
            )
        if self.value() == "draft":
            return queryset.filter(
                form_progress__isnull=False, form_progress__completed_time__isnull=True
            )
        return queryset


class EmailVerifiedFilter(admin.SimpleListFilter):
    """Applications whose address somebody has proven they own, or not yet."""

    title = "email verified"
    parameter_name = "email_verified"

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin
    ) -> list[tuple[str, str]]:
        return [("verified", "Verified"), ("unverified", "Unverified")]

    def queryset(
        self, request: HttpRequest, queryset: QuerySet[CourseApplication]
    ) -> QuerySet[CourseApplication]:
        if self.value() == "verified":
            return queryset.filter(user__isnull=False)
        if self.value() == "unverified":
            return queryset.filter(user__isnull=True)
        return queryset


@admin.register(CourseApplication)
class CourseApplicationAdmin(SiteAwareExportModelAdmin):
    """Find an application and read it. Nothing here writes.

    Applications are created only by the apply flow, which also creates the
    sitting; re-pointing the user, course or sitting from here would break the
    rule that the sitting is the applicant's own sitting of that course's form,
    and deleting one would leave its sitting and files with no owner.
    """

    resource_classes = [CourseApplicationResource]

    list_display = [
        "applicant_email",
        "applicant_name",
        "is_email_verified",
        "course",
        "is_submitted",
        "submitted_time",
        "created_at",
    ]
    # Every column reads one of these relations; without them the changelist
    # queries once per row.
    list_select_related = ["user", "anonymous_applicant", "course", "form_progress"]
    ordering = ["-created_at"]
    list_filter = [
        CourseApplicationSubmittedFilter,
        EmailVerifiedFilter,
        ("course", AutocompleteSelectFilter),
        ("created_at", InclusiveRangeDateTimeFilter),
    ]
    # Filters apply on Submit, so a created-date range goes through as a pair of
    # dates rather than refreshing the list after each box.
    list_filter_submit = True
    search_fields = [
        "user__email",
        "user__first_name",
        "user__last_name",
        "anonymous_applicant__email",
        "anonymous_applicant__first_name",
        "anonymous_applicant__last_name",
        "course__title",
    ]
    fields = ["is_submitted", "submitted_time_display", "created_at"]
    readonly_fields = fields
    change_form_template = "admin/form_engine/answers_change_form.html"

    def get_queryset(self, request: HttpRequest) -> QuerySet[CourseApplication]:
        queryset: QuerySet[CourseApplication] = (
            super()
            .get_queryset(request)
            .select_related("user", "anonymous_applicant", "course", "form_progress")
        )
        return queryset

    def render_change_form(
        self,
        request: HttpRequest,
        context: dict[str, object],
        add: bool = False,
        change: bool = False,
        form_url: str = "",
        obj: CourseApplication | None = None,
    ) -> HttpResponse:
        if obj is not None:
            form_progress = obj.form_progress
            unverified_rows = (
                []
                if obj.is_email_verified
                else [("Unverified email", obj.applicant_email)]
            )
            context["summary_rows"] = [
                *unverified_rows,
                ("Applicant", self._applicant_link(request, obj)),
                ("Course", admin_change_link(request, obj.course)),
                (
                    "Form progress record",
                    admin_change_link(request, form_progress)
                    if form_progress is not None
                    else "The course asked for no application form.",
                ),
            ]
            if form_progress is not None:
                context.update(answers_context(request, form_progress))
        response: HttpResponse = super().render_change_form(
            request, context, add, change, form_url, obj
        )
        return response

    def _applicant_link(
        self, request: HttpRequest, obj: CourseApplication
    ) -> str | SafeString:
        if obj.user is not None:
            return admin_change_link(request, obj.user)
        if obj.anonymous_applicant is not None:
            return admin_change_link(request, obj.anonymous_applicant)
        return ""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: CourseApplication | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: CourseApplication | None = None
    ) -> bool:
        return False

    @admin.display(description="Applicant", ordering="user__email")
    def applicant_email(self, obj: CourseApplication) -> str:
        return obj.applicant_email

    @admin.display(description="Applicant name", ordering="user__last_name")
    def applicant_name(self, obj: CourseApplication) -> str:
        return obj.applicant_name

    @admin.display(boolean=True, description="Email verified")
    def is_email_verified(self, obj: CourseApplication) -> bool:
        return obj.is_email_verified

    @admin.display(boolean=True, description="Submitted")
    def is_submitted(self, obj: CourseApplication) -> bool:
        return obj.is_submitted

    @admin.display(description="Submitted time")
    def submitted_time_display(self, obj: CourseApplication) -> str:
        """The submitted time as the change page shows it.

        Unfold prints a callable's datetime with ``str()``, skipping the
        formatting that the changelist and model fields get.
        """
        submitted_time = obj.submitted_time
        if submitted_time is None:
            return str(self.get_empty_value_display())
        return formats.localize(timezone.localtime(submitted_time))


@admin.register(AnonymousApplicant)
class AnonymousApplicantAdmin(SiteAwareModelAdmin):
    """Find an unverified applicant and erase them. Nothing here writes.

    Deleting an applicant takes their application, sitting, answers and stored
    files with it, which is how a right-to-erasure request for an address that
    never became an account is carried out. A claimed applicant is protected:
    its application belongs to a user now, and deleting the user is the one
    path that takes a user's application away.
    """

    list_display = [
        "email",
        "first_name",
        "last_name",
        "course",
        "is_claimed",
        "created_at",
    ]
    list_select_related = ["course", "user"]
    ordering = ["-created_at"]
    search_fields = ["email", "first_name", "last_name"]
    list_filter = [
        ("course", AutocompleteSelectFilter),
        ("created_at", InclusiveRangeDateTimeFilter),
    ]
    list_filter_submit = True
    readonly_fields = [
        "course",
        "email",
        "first_name",
        "last_name",
        "terms_version",
        "terms_git_hash",
        "privacy_version",
        "privacy_git_hash",
        "consent_ip_address",
        "consented_at",
        "user",
        "claimed_at",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: AnonymousApplicant | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: AnonymousApplicant | None = None
    ) -> bool:
        if obj is not None and obj.claimed_at is not None:
            return False
        allowed: bool = super().has_delete_permission(request, obj)
        return allowed

    def get_deleted_objects(
        self,
        objs: QuerySet[AnonymousApplicant] | list[AnonymousApplicant],
        request: HttpRequest,
    ) -> tuple[list[object], dict[str, int], set[str], list[object]]:
        # A list from the single-object delete view, a queryset from the bulk
        # action. Claimed applicants are reported as protected, which makes the
        # confirmation page refuse the whole selection and name them.
        applicants = list(objs)
        unclaimed = [a for a in applicants if a.claimed_at is None]
        to_delete, model_count, perms_needed, protected = super().get_deleted_objects(
            unclaimed, request
        )
        # The application admin denies delete to everyone, yet the confirmation
        # page lists the application the erasure takes along.
        perms_needed.discard(str(CourseApplication._meta.verbose_name))
        claimed = [
            f"{applicant} (claimed): delete the user instead"
            for applicant in applicants
            if applicant.claimed_at is not None
        ]
        return to_delete, model_count, perms_needed, [*protected, *claimed]

    def delete_model(self, request: HttpRequest, obj: AnonymousApplicant) -> None:
        erase_anonymous_applicant(obj)

    def delete_queryset(
        self, request: HttpRequest, queryset: QuerySet[AnonymousApplicant]
    ) -> None:
        for applicant in queryset.filter(claimed_at__isnull=True):
            erase_anonymous_applicant(applicant)

    @admin.display(boolean=True, description="Claimed", ordering="claimed_at")
    def is_claimed(self, obj: AnonymousApplicant) -> bool:
        return obj.claimed_at is not None
