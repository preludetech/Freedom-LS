"""Export resource for course applications."""

from __future__ import annotations

from collections.abc import Iterator
from functools import partial
from uuid import UUID

from import_export.fields import Field
from import_export.widgets import ForeignKeyWidget

from django.db.models import QuerySet

from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.exports import answer_cell, answer_columns
from freedom_ls.form_engine.models import QuestionAnswer
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

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._applications: list[CourseApplication] = []
        # Answers by sitting, then by question, built once per export.
        self._answers: dict[UUID, dict[UUID, QuestionAnswer]] = {}

    def filter_export(
        self, queryset: QuerySet[CourseApplication], **kwargs: object
    ) -> QuerySet[CourseApplication]:
        return queryset.select_related(
            "user", "anonymous_applicant", "course", "form_progress"
        ).prefetch_related(
            "form_progress__form",
            "form_progress__answers__question",
            "form_progress__answers__selected_options",
            "form_progress__answers__answer_file",
        )

    def before_export(
        self, queryset: QuerySet[CourseApplication] | None, **kwargs: object
    ) -> None:
        # The rows are loaded once, here: the answer columns are built from
        # them and the cells read the same objects, so nothing is fetched twice.
        if queryset is None:
            queryset = self.get_queryset()
        self._applications = list(self.filter_export(queryset))
        sittings = [
            application.form_progress
            for application in self._applications
            if application.form_progress is not None
        ]
        self._answers = {
            sitting.pk: {answer.question_id: answer for answer in sitting.answers.all()}
            for sitting in sittings
        }
        for column in answer_columns(sittings):
            self.fields[f"question_{column.question.id}"] = Field(
                column_name=column.header,
                dehydrate_method=partial(
                    self._answer_cell, question_id=column.question.id
                ),
            )

    def iter_queryset(
        self, queryset: QuerySet[CourseApplication]
    ) -> Iterator[CourseApplication]:
        # The rows are already in memory from before_export, which built the
        # answer columns from them; the package's chunked walk would read the
        # same rows a second time.
        return iter(self._applications)

    def _answer_cell(self, application: CourseApplication, question_id: UUID) -> str:
        if application.form_progress is None:
            return ""
        return answer_cell(self._answers[application.form_progress.pk].get(question_id))
