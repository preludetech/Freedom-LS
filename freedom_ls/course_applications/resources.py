"""Export resource for course applications."""

from __future__ import annotations

from import_export.fields import Field
from import_export.widgets import ForeignKeyWidget

from django.db.models import QuerySet

from freedom_ls.content_engine.models import Course
from freedom_ls.site_aware_models.admin_exports import (
    IsoDateTimeWidget,
    SiteAwareModelResource,
    SpreadsheetBooleanWidget,
)

from .models import CourseApplication

APPLICATION_EXPORT_FIELDS = (
    "id",
    "applicant_email",
    "applicant_name",
    "is_email_verified",
    "course",
    "is_submitted",
    "submitted_time",
    "created_at",
)


class CourseApplicationResource(SiteAwareModelResource):
    """One row per application, whoever holds it and whether or not it is submitted."""

    applicant_email = Field(attribute="applicant_email")
    applicant_name = Field(attribute="applicant_name")
    is_email_verified = Field(
        attribute="is_email_verified", widget=SpreadsheetBooleanWidget()
    )
    # The course title, not the pk, so the sheet reads without a join.
    course = Field(attribute="course", widget=ForeignKeyWidget(Course, "title"))
    is_submitted = Field(attribute="is_submitted", widget=SpreadsheetBooleanWidget())
    submitted_time = Field(attribute="submitted_time", widget=IsoDateTimeWidget())

    class Meta:
        model = CourseApplication
        fields = APPLICATION_EXPORT_FIELDS
        export_order = APPLICATION_EXPORT_FIELDS

    def filter_export(
        self, queryset: QuerySet[CourseApplication], **kwargs: object
    ) -> QuerySet[CourseApplication]:
        # The fixed columns read these four relations; the admin's own queryset
        # already joins them, and a queryset handed in from elsewhere gets the same.
        return queryset.select_related(
            "user", "anonymous_applicant", "course", "form_progress"
        )
