"""The audit log table's filter parameters."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import time_machine

from django.http import QueryDict

from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.educator_interface.panels.audit_log.data_tables import (
    AuditLogEntryTable,
)

pytestmark = pytest.mark.usefixtures("_site_context")


@pytest.mark.django_db
def test_the_audit_log_filters_on_the_when_parameter(audit_request):
    request, organisation = audit_request
    recent = AuditLogEntryFactory(target=organisation)
    with time_machine.travel(datetime.now(UTC) - timedelta(days=30), tick=False):
        AuditLogEntryFactory(target=organisation)
    request.GET = QueryDict("audit-when=7d")

    query = AuditLogEntryTable.parse_query(request, "audit")
    rows = AuditLogEntryTable.filter_queryset(
        request,
        AuditLogEntry.objects.filter(organisation=organisation),
        query,
    )

    assert list(rows) == [recent]
