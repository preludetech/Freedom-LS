"""The History panel shared by the learner and cohort pages."""

from __future__ import annotations

from typing import cast

from django.db.models import Model, QuerySet
from django.http import HttpRequest

from freedom_ls.audit_log.writer import subject_key
from freedom_ls.educator_interface.panels.audit_log.data_tables import (
    AuditLogEntryTable,
    _record_export,
)
from freedom_ls.panel_framework.panels import DataTablePanel

__all__ = [
    "HistoryPanel",
]


class HistoryPanel(DataTablePanel):
    """The History tab of one learner or cohort: every entry whose subjects name it."""

    title = "History"
    data_table = AuditLogEntryTable
    table_key = "history"
    capability = "freedom_ls_audit_log.view_auditlogentry"
    empty_message: str
    #: What the export's entry says it covered: "learner" or "cohort".
    export_scope: str

    @property
    def scope_label(self) -> str:
        """The learner's or cohort's name, for the entry and the filename."""
        raise NotImplementedError

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context["empty_message"] = self.empty_message
        return context

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return (
            super()
            .get_queryset(request)
            .filter(subjects__contains=[subject_key(cast(Model, self.instance))])
        )

    def get_export_queryset(self, request: HttpRequest) -> QuerySet:
        return self.get_queryset(request).select_related("actor")

    def get_export_scope_slug(self, request: HttpRequest) -> str:
        return self.scope_label

    def before_export(self, request: HttpRequest, rows: QuerySet) -> QuerySet:
        return _record_export(
            request,
            rows,
            table=self.data_table,
            table_key=self.table_key,
            scope=self.export_scope,
            scope_label=self.scope_label,
        )
