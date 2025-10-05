from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Student, Cohort, CohortMembership


@admin.register(Student)
class StudentAdmin(ModelAdmin):
    list_display = ["full_name", "email", "id_number", "cellphone"]
    search_fields = ["full_name", "email", "id_number"]
    list_filter = ["date_of_birth"]


class CohortMembershipInline(TabularInline):
    model = CohortMembership
    extra = 1
    autocomplete_fields = ["student"]


@admin.register(Cohort)
class CohortAdmin(ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    inlines = [CohortMembershipInline]
