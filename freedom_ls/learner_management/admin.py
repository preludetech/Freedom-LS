from typing import cast

from unfold.admin import TabularInline

from django import forms
from django.contrib import admin
from django.db import models
from django.http import HttpRequest

from freedom_ls.site_aware_models.admin import (
    GuardedSiteAwareModelAdmin,
    SiteAwareModelAdmin,
)

from .models import (
    Cohort,
    CohortCourseRegistration,
    CohortDeadline,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
    LearnerDeadline,
    RecommendedCourse,
    UserCohortDeadlineOverride,
)


@admin.register(Learner)
class LearnerAdmin(SiteAwareModelAdmin):
    list_display = ["user", "organisation", "is_active", "created_at"]
    list_filter = ["organisation", "is_active"]
    readonly_fields = ["created_at"]
    search_fields = ["user__first_name", "user__last_name", "user__email"]
    autocomplete_fields = ["user", "organisation"]

    def has_delete_permission(
        self, request: HttpRequest, obj: Learner | None = None
    ) -> bool:
        return False


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
        # Narrows the dropdown to the cohort's own organisation on the change
        # page only -- `object_id` isn't in the URL kwargs on the add page, so
        # a brand-new cohort still offers every learner there. Cross-org rows
        # are rejected either way by CohortMembership.clean(); this only saves
        # a round trip on the common case.
        if db_field.name == "learner" and request.resolver_match:
            cohort_id = request.resolver_match.kwargs.get("object_id")
            if cohort_id:
                kwargs["queryset"] = Learner.objects.filter(
                    organisation__cohort__id=cohort_id, is_active=True
                )
        return cast(
            "forms.ModelChoiceField | None",
            super().formfield_for_foreignkey(db_field, request, **kwargs),
        )


class CohortCourseRegistrationInline(TabularInline):
    model = CohortCourseRegistration
    extra = 0
    autocomplete_fields = ["collection"]
    fields = ["collection", "is_active", "registered_at"]
    readonly_fields = ["registered_at"]

    verbose_name = "Course Registration"
    verbose_name_plural = "Course Registrations"


@admin.register(Cohort)
class CohortAdmin(GuardedSiteAwareModelAdmin):
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
    list_display = ["get_user_name", "collection", "is_active", "registered_at"]
    list_select_related = ["learner__user", "collection"]
    list_filter = ["is_active", "registered_at"]
    search_fields = [
        "learner__user__email",
        "learner__user__first_name",
        "learner__user__last_name",
        "collection__title",
    ]
    autocomplete_fields = ["learner", "collection"]
    readonly_fields = ["registered_at"]
    inlines = [LearnerDeadlineInline]

    fieldsets = (
        (None, {"fields": ("learner", "collection", "is_active")}),
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


class UserCohortDeadlineOverrideInline(TabularInline):
    model = UserCohortDeadlineOverride
    extra = 0
    autocomplete_fields = ["learner"]
    fields = ["learner", "content_type", "object_id", "deadline", "is_hard_deadline"]

    verbose_name = "User Deadline Override"
    verbose_name_plural = "User Deadline Overrides"


@admin.register(CohortCourseRegistration)
class CohortCourseRegistrationAdmin(SiteAwareModelAdmin):
    list_display = ["cohort", "collection", "is_active", "registered_at"]
    list_select_related = ["cohort", "collection"]
    list_filter = ["is_active", "registered_at"]
    search_fields = ["cohort__name", "collection__title"]
    autocomplete_fields = ["cohort", "collection"]
    readonly_fields = ["registered_at"]
    inlines = [CohortDeadlineInline, UserCohortDeadlineOverrideInline]

    fieldsets = (
        (None, {"fields": ("cohort", "collection", "is_active")}),
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
        "cohort_course_registration__collection",
    ]
    list_filter = [
        "cohort_course_registration__cohort",
        "cohort_course_registration__collection",
        "is_hard_deadline",
    ]
    search_fields = [
        "cohort_course_registration__cohort__name",
        "cohort_course_registration__collection__title",
    ]
    autocomplete_fields = ["cohort_course_registration"]

    @admin.display(
        description="Cohort", ordering="cohort_course_registration__cohort__name"
    )
    def get_cohort_name(self, obj: CohortDeadline) -> str:
        return obj.cohort_course_registration.cohort.name

    @admin.display(
        description="Course", ordering="cohort_course_registration__collection__title"
    )
    def get_course_name(self, obj: CohortDeadline) -> str:
        return obj.cohort_course_registration.collection.title

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
        "learner_course_registration__collection",
    ]
    list_filter = [
        "learner_course_registration__collection",
        "is_hard_deadline",
    ]
    search_fields = [
        "learner_course_registration__learner__user__first_name",
        "learner_course_registration__learner__user__last_name",
        "learner_course_registration__collection__title",
    ]
    autocomplete_fields = ["learner_course_registration"]

    @admin.display(description="User")
    def get_user_name(self, obj: LearnerDeadline) -> str:
        return str(obj.learner_course_registration.learner.user)

    @admin.display(description="Course")
    def get_course_name(self, obj: LearnerDeadline) -> str:
        return obj.learner_course_registration.collection.title

    @admin.display(description="Content Item")
    def get_content_item(self, obj: LearnerDeadline) -> str:
        return str(obj.content_item) if obj.content_item else "Whole course"


@admin.register(UserCohortDeadlineOverride)
class UserCohortDeadlineOverrideAdmin(SiteAwareModelAdmin):
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
        "cohort_course_registration__collection",
    ]
    list_filter = [
        "cohort_course_registration__cohort",
        "cohort_course_registration__collection",
        "is_hard_deadline",
    ]
    search_fields = [
        "learner__user__first_name",
        "learner__user__last_name",
        "cohort_course_registration__cohort__name",
        "cohort_course_registration__collection__title",
    ]
    autocomplete_fields = ["cohort_course_registration", "learner"]

    @admin.display(description="User")
    def get_user_name(self, obj: UserCohortDeadlineOverride) -> str:
        return str(obj.learner.user)

    @admin.display(description="Cohort")
    def get_cohort_name(self, obj: UserCohortDeadlineOverride) -> str:
        return obj.cohort_course_registration.cohort.name

    @admin.display(description="Course")
    def get_course_name(self, obj: UserCohortDeadlineOverride) -> str:
        return obj.cohort_course_registration.collection.title

    @admin.display(description="Content Item")
    def get_content_item(self, obj: UserCohortDeadlineOverride) -> str:
        return str(obj.content_item) if obj.content_item else "Whole course"


@admin.register(RecommendedCourse)
class RecommendedCourseAdmin(SiteAwareModelAdmin):
    list_display = ["user", "collection", "created_at"]
    search_fields = ["user__email", "collection__title"]
    list_filter = ["created_at"]
    readonly_fields = ["created_at"]
    exclude = ["site"]
