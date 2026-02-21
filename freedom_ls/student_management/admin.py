from django.contrib import admin
from unfold.admin import TabularInline

from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin
from .models import (
    Student,
    Cohort,
    CohortMembership,
    StudentCourseRegistration,
    CohortCourseRegistration,
    CohortDeadline,
    StudentDeadline,
    StudentCohortDeadlineOverride,
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


class StudentDeadlineInline(TabularInline):
    model = StudentDeadline
    extra = 0
    fields = ["content_type", "object_id", "deadline", "is_hard_deadline"]

    verbose_name = "Deadline"
    verbose_name_plural = "Deadlines"


@admin.register(StudentCourseRegistration)
class StudentCourseRegistrationAdmin(SiteAwareModelAdmin):
    list_display = ["get_student_name", "collection", "is_active", "registered_at"]
    list_select_related = ["student__user", "collection"]
    list_filter = ["is_active", "registered_at"]
    search_fields = [
        "student__user__email",
        "student__user__first_name",
        "student__user__last_name",
        "collection__title",
    ]
    autocomplete_fields = ["student", "collection"]
    readonly_fields = ["registered_at"]
    inlines = [StudentDeadlineInline]

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


class CohortDeadlineInline(TabularInline):
    model = CohortDeadline
    extra = 0
    fields = ["content_type", "object_id", "deadline", "is_hard_deadline"]

    verbose_name = "Deadline"
    verbose_name_plural = "Deadlines"


class StudentCohortDeadlineOverrideInline(TabularInline):
    model = StudentCohortDeadlineOverride
    extra = 0
    autocomplete_fields = ["student"]
    fields = ["student", "content_type", "object_id", "deadline", "is_hard_deadline"]

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
    inlines = [CohortDeadlineInline, StudentCohortDeadlineOverrideInline]

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

    def get_cohort_name(self, obj: CohortDeadline) -> str:
        return obj.cohort_course_registration.cohort.name

    get_cohort_name.short_description = "Cohort"
    get_cohort_name.admin_order_field = "cohort_course_registration__cohort__name"

    def get_course_name(self, obj: CohortDeadline) -> str:
        return obj.cohort_course_registration.collection.title

    get_course_name.short_description = "Course"
    get_course_name.admin_order_field = "cohort_course_registration__collection__title"

    def get_content_item(self, obj: CohortDeadline) -> str:
        return str(obj.content_item) if obj.content_item else "Whole course"

    get_content_item.short_description = "Content Item"


@admin.register(StudentDeadline)
class StudentDeadlineAdmin(SiteAwareModelAdmin):
    list_display = [
        "get_student_name",
        "get_course_name",
        "get_content_item",
        "deadline",
        "is_hard_deadline",
    ]
    list_select_related = [
        "student_course_registration__student__user",
        "student_course_registration__collection",
    ]
    list_filter = [
        "student_course_registration__collection",
        "is_hard_deadline",
    ]
    search_fields = [
        "student_course_registration__student__user__first_name",
        "student_course_registration__student__user__last_name",
        "student_course_registration__collection__title",
    ]
    autocomplete_fields = ["student_course_registration"]

    def get_student_name(self, obj: StudentDeadline) -> str:
        return str(obj.student_course_registration.student)

    get_student_name.short_description = "Student"

    def get_course_name(self, obj: StudentDeadline) -> str:
        return obj.student_course_registration.collection.title

    get_course_name.short_description = "Course"

    def get_content_item(self, obj: StudentDeadline) -> str:
        return str(obj.content_item) if obj.content_item else "Whole course"

    get_content_item.short_description = "Content Item"


@admin.register(StudentCohortDeadlineOverride)
class StudentCohortDeadlineOverrideAdmin(SiteAwareModelAdmin):
    list_display = [
        "get_student_name",
        "get_cohort_name",
        "get_course_name",
        "get_content_item",
        "deadline",
        "is_hard_deadline",
    ]
    list_select_related = [
        "student__user",
        "cohort_course_registration__cohort",
        "cohort_course_registration__collection",
    ]
    list_filter = [
        "cohort_course_registration__cohort",
        "cohort_course_registration__collection",
        "is_hard_deadline",
    ]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "cohort_course_registration__cohort__name",
        "cohort_course_registration__collection__title",
    ]
    autocomplete_fields = ["cohort_course_registration", "student"]

    def get_student_name(self, obj: StudentCohortDeadlineOverride) -> str:
        return str(obj.student)

    get_student_name.short_description = "Student"

    def get_cohort_name(self, obj: StudentCohortDeadlineOverride) -> str:
        return obj.cohort_course_registration.cohort.name

    get_cohort_name.short_description = "Cohort"

    def get_course_name(self, obj: StudentCohortDeadlineOverride) -> str:
        return obj.cohort_course_registration.collection.title

    get_course_name.short_description = "Course"

    def get_content_item(self, obj: StudentCohortDeadlineOverride) -> str:
        return str(obj.content_item) if obj.content_item else "Whole course"

    get_content_item.short_description = "Content Item"


@admin.register(RecommendedCourse)
class RecommendedCourseAdmin(SiteAwareModelAdmin):
    list_display = ["user", "collection", "created_at"]
    search_fields = ["user__email", "collection__title"]
    list_filter = ["created_at"]
    readonly_fields = ["created_at"]
    exclude = ["site"]
