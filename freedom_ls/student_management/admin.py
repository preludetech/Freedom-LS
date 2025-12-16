from django.contrib import admin
from unfold.admin import TabularInline

from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin
from .models import (
    Student,
    Cohort,
    CohortMembership,
    StudentCourseRegistration,
    CohortCourseRegistration,
    RecommendedCourse,
)
from guardian.admin import GuardedModelAdmin


class StudentCohortMembershipInline(TabularInline):
    model = CohortMembership
    extra = 0
    autocomplete_fields = ["cohort"]
    fields = ["cohort"]

    verbose_name = "Cohort Membership"
    verbose_name_plural = "Cohort Memberships"


class StudentCourseRegistrationInline(TabularInline):
    model = StudentCourseRegistration
    extra = 0
    autocomplete_fields = ["collection"]
    fields = ["collection", "is_active", "registered_at"]
    readonly_fields = ["registered_at"]

    verbose_name = "Course Registration"
    verbose_name_plural = "Course Registrations"


@admin.register(Student)
class StudentAdmin(SiteAwareModelAdmin):
    list_display = [
        "get_full_name",
        "get_email",
        "id_number",
        "cellphone",
        "get_cohorts",
    ]
    search_fields = ["user__email", "user__first_name", "user__last_name", "id_number"]
    list_filter = ["date_of_birth", "user__is_active"]
    inlines = [StudentCohortMembershipInline, StudentCourseRegistrationInline]
    autocomplete_fields = ["user"]
    exclude = ["site"]

    def get_full_name(self, obj):
        """Display the student's full name from user."""
        if obj.user.first_name or obj.user.last_name:
            return f"{obj.user.first_name} {obj.user.last_name}".strip()
        return "-"

    get_full_name.short_description = "Full Name"
    get_full_name.admin_order_field = "user__first_name"

    def get_email(self, obj):
        """Display the student's email from user."""
        return obj.user.email

    get_email.short_description = "Email"
    get_email.admin_order_field = "user__email"

    def get_cohorts(self, obj):
        cohorts = Cohort.objects.filter(cohortmembership__student=obj)
        return ", ".join([cohort.name for cohort in cohorts])

    get_cohorts.short_description = "Cohorts"


class CohortMembershipInline(TabularInline):
    model = CohortMembership
    extra = 1
    autocomplete_fields = ["student"]
    fields = ["student"]


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


@admin.register(StudentCourseRegistration)
class StudentCourseRegistrationAdmin(SiteAwareModelAdmin):
    list_display = ["get_student_name", "collection", "is_active", "registered_at"]
    list_filter = ["is_active", "registered_at"]
    search_fields = [
        "student__user__email",
        "student__user__first_name",
        "student__user__last_name",
        "collection__title",
    ]
    autocomplete_fields = ["student", "collection"]
    readonly_fields = ["registered_at"]

    fieldsets = (
        (None, {"fields": ("student", "collection", "is_active")}),
        ("Timestamps", {"fields": ("registered_at",), "classes": ("collapse",)}),
    )

    def get_student_name(self, obj):
        """Display student's full name."""
        if obj.student.user.first_name or obj.student.user.last_name:
            return f"{obj.student.user.first_name} {obj.student.user.last_name}".strip()
        return obj.student.user.email

    get_student_name.short_description = "Student"
    get_student_name.admin_order_field = "student__user__first_name"


@admin.register(CohortCourseRegistration)
class CohortCourseRegistrationAdmin(SiteAwareModelAdmin):
    list_display = ["cohort", "collection", "is_active", "registered_at"]
    list_filter = ["is_active", "registered_at"]
    search_fields = ["cohort__name", "collection__title"]
    autocomplete_fields = ["cohort", "collection"]
    readonly_fields = ["registered_at"]

    fieldsets = (
        (None, {"fields": ("cohort", "collection", "is_active")}),
        ("Timestamps", {"fields": ("registered_at",), "classes": ("collapse",)}),
    )


@admin.register(RecommendedCourse)
class RecommendedCourseAdmin(SiteAwareModelAdmin):
    list_display = ["user", "collection", "created_at"]
    search_fields = ["user__email", "collection__title"]
    list_filter = ["created_at"]
    readonly_fields = ["created_at"]
    exclude = ["site"]
