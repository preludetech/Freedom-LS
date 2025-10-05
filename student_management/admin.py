from django.contrib import admin
from unfold.admin import TabularInline

from system_base.admin import SiteAwareModelAdmin
from .models import Student, Cohort, CohortMembership


@admin.register(Student)
class StudentAdmin(SiteAwareModelAdmin):
    list_display = ["full_name", "email", "id_number", "cellphone"]
    search_fields = ["full_name", "email", "id_number"]
    list_filter = ["date_of_birth"]


class CohortMembershipInline(TabularInline):
    model = CohortMembership
    extra = 1
    autocomplete_fields = ["student"]
    exclude = ["site_id"]


@admin.register(Cohort)
class CohortAdmin(SiteAwareModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    inlines = [CohortMembershipInline]
