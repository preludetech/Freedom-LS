"""The audit log's tables, the row and export helpers they share and the export record."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast
from uuid import UUID

from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Page
from django.db.models import Count, F, Model, Q, QuerySet, Window
from django.db.models.functions import RowNumber
from django.http import HttpRequest
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.audit_log.actions import SUMMARY_ACTIONS
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.audit_log.writer import RUN_ROWS_KEPT, record_entry
from freedom_ls.educator_interface.avatars import user_picture_urls
from freedom_ls.educator_interface.panels.audit_log.filters import (
    AuditActionFilter,
    AuditActorFilter,
)
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.learner_management.models import Learner, StaffMember
from freedom_ls.panel_framework.filters import PeriodFilter, TableFilter
from freedom_ls.panel_framework.tables import (
    Column,
    DataTable,
    ExportColumn,
    TableQuery,
)

__all__ = [
    "_PERSON_TARGETS",
    "AuditLogEntryTable",
    "OrganisationAuditLogTable",
    "TargetedAuditLogEntryTable",
    "_attach_people",
    "_export_run_id",
    "_export_when",
    "_export_who",
    "_record_export",
]


#: Target models that are a person: the user pk is the target itself, or the row's user.
_PERSON_TARGETS: tuple[type[User] | type[Learner] | type[StaffMember], ...] = (
    User,
    Learner,
    StaffMember,
)


def _attach_people(entries: Sequence[AuditLogEntry]) -> None:
    """Set `target_is_person`, `target_user_pk` and the who and target pictures on every entry.

    A person target gets the live user's pk (None once the row is gone, so
    the template shows the neutral circle beside the stored label); any
    other target is not a person and renders as plain text. Keyed on the
    stored content type id against the registry's ids, so no entry's
    `target_content_type` relation is read, and one lookup per model type
    regardless of the page size. The picture URLs follow the live user, so a
    removed picture stops showing; both are None when there is no picture. No
    `is_active` filter: an inactive user keeps their avatar.
    """
    person_models_by_type_id = {
        ContentType.objects.get_for_model(model).pk: model for model in _PERSON_TARGETS
    }
    by_model: dict[
        type[User] | type[Learner] | type[StaffMember], list[AuditLogEntry]
    ] = {}
    for entry in entries:
        model = person_models_by_type_id.get(entry.target_content_type_id)
        entry.target_is_person = model is not None
        entry.target_user_pk = None
        if model is not None:
            by_model.setdefault(model, []).append(entry)
    for model, typed in by_model.items():
        user_field = "pk" if model is User else "user_id"
        rows = model.objects.filter(pk__in={entry.target_object_id for entry in typed})
        found: dict[str, int] = {
            str(pk): user_pk for pk, user_pk in rows.values_list("pk", user_field)
        }
        for entry in typed:
            entry.target_user_pk = found.get(entry.target_object_id)
    urls = user_picture_urls(
        pk
        for entry in entries
        for pk in (entry.actor_id, entry.target_user_pk)
        if pk is not None
    )
    for entry in entries:
        entry.actor_picture_url = (
            None if entry.actor_id is None else urls.get(entry.actor_id)
        )
        entry.target_picture_url = (
            None if entry.target_user_pk is None else urls.get(entry.target_user_pk)
        )


def _export_when(row: Model) -> str:
    return timezone.localtime(cast(AuditLogEntry, row).created_at).isoformat()


def _export_who(row: Model) -> str:
    return cast(AuditLogEntry, row).actor_label or "System"


def _export_run_id(row: Model) -> str:
    run_id = cast(AuditLogEntry, row).run_id
    return "" if run_id is None else str(run_id)


class AuditLogEntryTable(DataTable):
    """A log: sortable on when, who and what, and filterable on the same
    three, wherever it appears (the organisation's Audit log and every
    History tab alike). The model's own ordering is newest first, which
    default_sort names so the When header reads as sorted that way."""

    page_size = 25
    card_template_name = "educator_interface/partials/audit_log_card.html"
    default_sort = "-created_at"
    noun = "entries"
    noun_singular = "entry"
    empty_message = "Nothing has been recorded yet."
    empty_no_results = "No entries match these filters."

    row_detail_template_name = "educator_interface/partials/audit_row_detail.html"

    @staticmethod
    def get_row_label(row: object) -> str:
        entry = cast(AuditLogEntry, row)
        return f"{entry.label}: {entry.target_label}"

    @staticmethod
    def has_row_detail(row: object) -> bool:
        entry = cast(AuditLogEntry, row)
        return bool(
            entry.description or entry.reason or getattr(entry, "run_entries", [])
        )

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        organisation = cast(OrganisationScopedRequest, request).organisation
        return AuditLogEntry.objects.filter(organisation=organisation)

    @classmethod
    def get_rows(
        cls,
        request: HttpRequest,
        queryset: QuerySet | Sequence[object],
        query: TableQuery,
    ) -> Page:
        page_obj = super().get_rows(request, queryset, query)
        _attach_people(list(page_obj.object_list))
        return page_obj

    @staticmethod
    def get_filters() -> list[TableFilter]:
        return [
            AuditActorFilter(),
            AuditActionFilter(),
            PeriodFilter(
                "when",
                "When",
                "created_at",
                {
                    "today": ("Today", 1),
                    "7d": ("Last 7 days", 7),
                    "30d": ("Last 30 days", 30),
                    "90d": ("Last 90 days", 90),
                    "12m": ("Last 12 months", 365),
                },
            ),
        ]

    @staticmethod
    def get_export_columns() -> list[ExportColumn]:
        # The screen names a column once; a column only the CSV carries is
        # named for the field it holds. `actor.email` reads the actor the
        # export queryset select_relates, and is empty once the actor is gone.
        return [
            ExportColumn("When", _export_when),
            ExportColumn("Who", _export_who),
            ExportColumn("Actor email", "actor.email"),
            ExportColumn("What", "label"),
            ExportColumn("Action", "action"),
            ExportColumn("Target", "target_label"),
            ExportColumn("Description", "description"),
            ExportColumn("Reason", "reason"),
            ExportColumn("Run ID", _export_run_id),
        ]

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            Column(
                header="When",
                template_name="cotton/data-table-cells/datetime.html",
                attr="created_at",
                sortable=True,
                cell_class="whitespace-nowrap py-2",
            ),
            Column(
                header="Who",
                template_name="educator_interface/data-table-cells/audit_who.html",
                sortable=True,
                sort_field="actor_label",
                # A person's name keeps a readable width when a long What
                # cell would otherwise squeeze the column.
                cell_class="min-w-48 py-2",
            ),
            Column(
                header="What",
                template_name="educator_interface/data-table-cells/audit_what.html",
                card="primary",
                sortable=True,
                sort_field="action",
                # The description is clipped inside this width rather than
                # widening the table past its wrapper.
                cell_class="max-w-md py-2",
            ),
        ]


class TargetedAuditLogEntryTable(AuditLogEntryTable):
    """Audit log entries that may be about different objects, so each row names its target."""

    card_template_name = "educator_interface/partials/audit_log_card_targeted.html"

    @staticmethod
    def get_columns() -> list[Column]:
        when, who, what = AuditLogEntryTable.get_columns()
        target = Column(
            header="Target",
            template_name="educator_interface/data-table-cells/audit_target.html",
            sortable=True,
            sort_field="target_label",
            cell_class="min-w-48 py-2",
        )
        return [when, who, what, target]


def _record_export(
    request: HttpRequest,
    rows: QuerySet,
    *,
    table: type[AuditLogEntryTable],
    table_key: str,
    scope: str,
    scope_label: str,
) -> QuerySet:
    """Write the entry for an audit log export and return the rows without it.

    The count is taken now, at request time, so the entry describes what the
    person asked for even if rows are written while the CSV streams. The
    entry targets the organisation, so it appears on the organisation's
    Audit log and on neither History tab. Excluding its pk keeps a CSV from
    containing a record of its own download.
    """
    scoped = cast(OrganisationScopedRequest, request)
    query = table.parse_query(request, table_key)
    entry = record_entry(
        action="audit_log.exported",
        actor=cast(User, request.user),
        target=scoped.organisation,
        target_label=scoped.organisation.name,
        organisation=scoped.organisation,
        details={
            "scope": scope,
            "scope_label": scope_label,
            "count": rows.count(),
            "filters": ", ".join(table.applied_filter_text(request, query)),
        },
    )
    return rows.exclude(pk=entry.pk)


class OrganisationAuditLogTable(TargetedAuditLogEntryTable):
    empty_message = "Nothing has been recorded for this organisation yet."

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        # A bulk run's per-object entries show on the learner and cohort History
        # tabs; here only its summary row stands for the run.
        return AuditLogEntryTable.get_queryset(request).exclude(
            Q(run_id__isnull=False) & ~Q(action__in=SUMMARY_ACTIONS)
        )

    @classmethod
    def get_rows(
        cls,
        request: HttpRequest,
        queryset: QuerySet | Sequence[object],
        query: TableQuery,
    ) -> Page:
        # Skips AuditLogEntryTable.get_rows: the page's entries and the run
        # entries attached below take one target lookup together.
        page_obj = super(AuditLogEntryTable, cls).get_rows(request, queryset, query)
        summaries = [row for row in page_obj.object_list if row.run_id is not None]
        if not summaries:
            _attach_people(list(page_obj.object_list))
            return page_obj
        organisation = cast(OrganisationScopedRequest, request).organisation
        run_ids = {row.run_id for row in summaries}
        per_object = AuditLogEntry.objects.filter(
            organisation=organisation, run_id__in=run_ids
        ).exclude(action__in=SUMMARY_ACTIONS)
        entries_by_run: dict[UUID, list[AuditLogEntry]] = {}
        for entry in per_object.annotate(
            position=Window(
                RowNumber(),
                partition_by=F("run_id"),
                order_by=[F("created_at").desc(), F("id").desc()],
            )
        ).filter(position__lte=RUN_ROWS_KEPT):
            entries_by_run.setdefault(cast(UUID, entry.run_id), []).append(entry)
        totals = dict(per_object.values_list("run_id").annotate(total=Count("pk")))
        for row in summaries:
            row.run_entries = entries_by_run.get(row.run_id, [])
            row.run_entry_total = totals.get(row.run_id, 0)
            row.run_entries_more = row.run_entry_total - len(row.run_entries)
        _attach_people(
            [*page_obj.object_list, *(e for row in summaries for e in row.run_entries)]
        )
        return page_obj
