"""The Staff table of the educator interface."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from panel_framework.filters import TableFilter
from panel_framework.tables import (
    Column,
    DataTable,
    TableQuery,
)

from django.core.paginator import Page
from django.db.models import (
    Prefetch,
    QuerySet,
)
from django.http import (
    HttpRequest,
)

from freedom_ls.accounts.models import User
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.staff.actions import (
    actionable_roles,
)
from freedom_ls.educator_interface.panels.staff.filters import (
    StaffRoleFilter,
)
from freedom_ls.educator_interface.staff import staff_role_entries
from freedom_ls.learner_management.models import (
    Learner,
    StaffMember,
)
from freedom_ls.learner_management.queries import (
    site_level_admins,
    staff_assignments,
    staff_of,
)

__all__ = [
    "StaffDataTable",
]


class StaffDataTable(DataTable):
    noun = "staff members"
    noun_singular = "staff member"
    search_fields = ["first_name", "last_name", "email"]
    default_sort = "first_name"
    empty_message = "No staff yet. Add the first staff member to give someone access to this organisation."
    empty_no_results = "No staff members match these filters."
    # Four columns, two of them buttons, need more room than a tablet or the
    # space beside the quick view gives.
    cards_when_narrow = True
    card_template_name = "educator_interface/partials/staff_card.html"

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        organisation = cast(OrganisationScopedRequest, request).organisation
        return staff_of(organisation).prefetch_related(
            Prefetch(
                "object_role_assignments",
                queryset=staff_assignments(organisation)
                .select_related("assigned_by")
                .prefetch_related("target"),
                to_attr="held_assignments",
            ),
            Prefetch(
                "staffmember_set",
                queryset=StaffMember.objects.filter(organisation=organisation),
                to_attr="member_rows",
            ),
            Prefetch(
                "learner_set",
                queryset=Learner.objects.filter(
                    organisation=organisation, is_active=True
                ),
                to_attr="learner_rows",
            ),
        )

    @staticmethod
    def get_filters() -> list[TableFilter]:
        return [StaffRoleFilter()]

    @classmethod
    def get_rows(
        cls,
        request: HttpRequest,
        queryset: QuerySet | Sequence[object],
        query: TableQuery,
    ) -> Page:
        page_obj = super().get_rows(request, queryset, query)
        site = cast(OrganisationScopedRequest, request).organisation.site
        site_level_ids = set(
            site_level_admins(site)
            .filter(pk__in=[row.pk for row in page_obj.object_list])
            .values_list("pk", flat=True)
        )
        for row in page_obj.object_list:
            row.is_site_level = row.pk in site_level_ids
            row.role_entries = staff_role_entries(row, site)
            row.actionable_roles = actionable_roles(request, row.role_entries)
            row.is_inactive = not any(m.is_active for m in row.member_rows)
        return page_obj

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            Column(
                header="Staff member",
                template_name="educator_interface/data-table-cells/staff_member.html",
                sortable=True,
                sort_field="first_name",
                card="primary",
            ),
            Column(
                header="Roles",
                template_name="educator_interface/data-table-cells/staff_roles.html",
                card="secondary",
            ),
            Column(
                header="Role actions",
                template_name="educator_interface/data-table-cells/staff_role_actions.html",
                card="secondary",
            ),
            Column(
                header="Staff member actions",
                template_name="educator_interface/data-table-cells/staff_member_actions.html",
                card="secondary",
            ),
        ]

    @staticmethod
    def get_row_label(row: object) -> str:
        return cast(User, row).display_name
