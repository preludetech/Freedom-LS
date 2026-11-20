"""The panels listing a course's cohort and direct registrations."""

from __future__ import annotations

from django.db.models import QuerySet
from django.http import HttpRequest

from freedom_ls.educator_interface.panels.course.data_tables import (
    CourseCohortRegistrationDataTable,
    CourseLearnerRegistrationDataTable,
)
from freedom_ls.panel_framework.panels import DataTablePanel

__all__ = ["CourseCohortRegistrationsPanel", "CourseLearnerRegistrationsPanel"]


class CourseCohortRegistrationsPanel(DataTablePanel):
    title = "Cohort registrations"
    data_table = CourseCohortRegistrationDataTable
    table_key = "cohort_registrations"

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).filter(course=self.instance)


class CourseLearnerRegistrationsPanel(DataTablePanel):
    title = "Direct registrations"
    data_table = CourseLearnerRegistrationDataTable
    table_key = "learner_registrations"

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).filter(course=self.instance)
