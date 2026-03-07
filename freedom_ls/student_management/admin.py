from guardian.admin import GuardedModelAdmin
from unfold.admin import TabularInline

from django.contrib import admin

from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin

from .models import (
    Cohort,
    CohortCourseRegistration,
    CohortDeadline,
    CohortMembership,
    RecommendedCourse,
    StudentDeadline,
    UserCohortDeadlineOverride,
    UserCourseRegistration,
)


class CohortMembershipInline(TabularInline):
    model = CohortMembership
    extra = 1
    autocomplete_fields = ["user"]
    fields = ["user"]


class CohortCourseRegistrationInline(TabularInline):
    model = CohortCourseRegistration
    extra = 0
    autocomplete_fields = ["collection"]
    fields = ["collection", "is_active", "registered_at"]
    readonly_fields = ["registered_at"]

    verbose_name = "Course Registration"
    verbose_name_plural = "Course Registrations"


@admin.register(Cohort)
class CohortAdmin(GuardedModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    inlines = [CohortMembershipInline, CohortCourseRegistrationInline]
    # @claude: We need a base class that extends from Guarded model admin and excludes the site (like SiteAwareModelAdmin).
    # implement it and then update docs/admin_interface.md


class StudentDeadlineInline(TabularInline):
    model = StudentDeadline
    extra = 0
    fields = ["content_type", "object_id", "deadline", "is_hard_deadline"]

    verbose_name = "Deadline"
    verbose_name_plural = "Deadlines"


@admin.register(UserCourseRegistration)
class UserCourseRegistrationAdmin(SiteAwareModelAdmin):
    list_display = ["get_user_name", "collection", "is_active", "registered_at"]
    list_select_related = ["user", "collection"]
    list_filter = ["is_active", "registered_at"]
    search_fields = [
        "user__email",
        "user__first_name",
        "user__last_name",
        "collection__title",
    ]
    autocomplete_fields = ["user", "collection"]
    readonly_fields = ["registered_at"]
    inlines = [StudentDeadlineInline]

    fieldsets = (
        (None, {"fields": ("user", "collection", "is_active")}),
        ("Timestamps", {"fields": ("registered_at",), "classes": ("collapse",)}),
    )

    @admin.display(description="User", ordering="user__first_name")
    def get_user_name(self, obj: UserCourseRegistration) -> str:
        """Display user's full name."""
        if obj.user.first_name or obj.user.last_name:
            return f"{obj.user.first_name} {obj.user.last_name}".strip()
        return obj.user.email


class CohortDeadlineInline(TabularInline):
    model = CohortDeadline
    extra = 0
    fields = ["content_type", "object_id", "deadline", "is_hard_deadline"]

    verbose_name = "Deadline"
    verbose_name_plural = "Deadlines"


class UserCohortDeadlineOverrideInline(TabularInline):
    model = UserCohortDeadlineOverride
    extra = 0
    autocomplete_fields = ["user"]
    fields = ["user", "content_type", "object_id", "deadline", "is_hard_deadline"]

    verbose_name = "Student Deadline Override"
    verbose_name_plural = "Student Deadline Overrides"


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


@admin.register(StudentDeadline)
class StudentDeadlineAdmin(SiteAwareModelAdmin):
    list_display = [
        "get_user_name",
        "get_course_name",
        "get_content_item",
        "deadline",
        "is_hard_deadline",
    ]
    list_select_related = [
        "student_course_registration__user",
        "student_course_registration__collection",
    ]
    list_filter = [
        "student_course_registration__collection",
        "is_hard_deadline",
    ]
    search_fields = [
        "student_course_registration__user__first_name",
        "student_course_registration__user__last_name",
        "student_course_registration__collection__title",
    ]
    autocomplete_fields = ["student_course_registration"]

    @admin.display(description="User")
    def get_user_name(self, obj: StudentDeadline) -> str:
        return str(obj.student_course_registration.user)

    @admin.display(description="Course")
    def get_course_name(self, obj: StudentDeadline) -> str:
        return obj.student_course_registration.collection.title

    @admin.display(description="Content Item")
    def get_content_item(self, obj: StudentDeadline) -> str:
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
        "user",
        "cohort_course_registration__cohort",
        "cohort_course_registration__collection",
    ]
    list_filter = [
        "cohort_course_registration__cohort",
        "cohort_course_registration__collection",
        "is_hard_deadline",
    ]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "cohort_course_registration__cohort__name",
        "cohort_course_registration__collection__title",
    ]
    autocomplete_fields = ["cohort_course_registration", "user"]

    @admin.display(description="User")
    def get_user_name(self, obj: UserCohortDeadlineOverride) -> str:
        return str(obj.user)

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
