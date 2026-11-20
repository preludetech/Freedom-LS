"""The organisation-wide audit log section."""

from __future__ import annotations

from typing import cast

from django.db.models import QuerySet
from django.http import HttpRequest

from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.educator_interface.panels.audit_log.data_tables import (
    AuditLogEntryTable,
    OrganisationAuditLogTable,
    _record_export,
)
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
    OrganisationSectionConfig,
)
from freedom_ls.panel_framework.views import ListViewConfig

__all__ = [
    "AuditLogConfig",
]


class AuditLogConfig(OrganisationSectionConfig, ListViewConfig):
    url_name = "audit-log"
    menu_label = "Audit log"
    icon = "notes"
    model = AuditLogEntry
    list_view = OrganisationAuditLogTable
    table_key = "audit_log"
    view_capability = "freedom_ls_audit_log.view_auditlogentry"
    # Entries are rows in a log, never pages of their own, so there is nothing to authorise per row.
    check_access_exempt_reason = "audit log entries have no instance pages"

    @classmethod
    def get_export_queryset(cls, request: HttpRequest) -> QuerySet:
        # Auditors get a bulk run's per-object entries, which the screen
        # folds under the run's summary row, so this starts from the
        # unexcluded table queryset.
        return AuditLogEntryTable.get_queryset(request).select_related("actor")

    @classmethod
    def get_export_scope_slug(cls, request: HttpRequest) -> str:
        return cast(OrganisationScopedRequest, request).organisation.slug

    @classmethod
    def before_export(cls, request: HttpRequest, rows: QuerySet) -> QuerySet:
        return _record_export(
            request,
            rows,
            table=cls.list_view,
            table_key=cls.table_key,
            scope="organisation",
            scope_label="",
        )
