from django.contrib import admin
from unfold.admin import TabularInline

from system_base.admin import SiteAwareModelAdmin
from .models import Student, Cohort, CohortMembership
from guardian.admin import GuardedModelAdmin


class StudentCohortMembershipInline(TabularInline):
    model = CohortMembership
    extra = 0
    autocomplete_fields = ["cohort"]
    exclude = ["site_id"]
    verbose_name = "Cohort Membership"
    verbose_name_plural = "Cohort Memberships"


@admin.register(Student)
class StudentAdmin(SiteAwareModelAdmin):
    list_display = ["id_number", "cellphone", "get_cohorts"]
    search_fields = ["id_number"]
    list_filter = ["date_of_birth"]
    inlines = [StudentCohortMembershipInline]

    def get_cohorts(self, obj):
        cohorts = Cohort.objects.filter(cohortmembership__student=obj)
        return ", ".join([cohort.name for cohort in cohorts])

    get_cohorts.short_description = "Cohorts"


class CohortMembershipInline(TabularInline):
    model = CohortMembership
    extra = 1
    autocomplete_fields = ["student"]
    exclude = ["site_id"]


@admin.register(Cohort)
class CohortAdmin(GuardedModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    inlines = [CohortMembershipInline]
