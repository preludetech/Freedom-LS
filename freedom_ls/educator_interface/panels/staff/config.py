"""The Staff section of the educator interface."""

from __future__ import annotations

from typing import cast

from django.db.models import Model
from django.http import HttpRequest

from freedom_ls.accounts.models import User
from freedom_ls.educator_interface.events import STAFF_CHANGED
from freedom_ls.educator_interface.exceptions import OrganisationScopeDenied
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
    OrganisationSectionConfig,
)
from freedom_ls.educator_interface.panels.staff.actions import (
    AddRoleAction,
    AddStaffMemberAction,
    ChangeCohortsAction,
    DeactivateRoleAction,
    DeactivateStaffMemberAction,
    ReactivateStaffMemberAction,
    grantable_roles_for,
)
from freedom_ls.educator_interface.panels.staff.data_tables import StaffDataTable
from freedom_ls.educator_interface.panels.staff.filters import may_see_staff_roles
from freedom_ls.educator_interface.panels.staff.quick_view import StaffQuickView
from freedom_ls.educator_interface.paths import interface_path
from freedom_ls.learner_management.queries import VIEW_ORGANISATION_STAFF, staff_of
from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.views import ListViewConfig

__all__ = ["StaffConfig"]


class StaffConfig(OrganisationSectionConfig, ListViewConfig):
    url_name = "staff"
    menu_label = "Staff"
    icon = "user"
    model = User
    list_view = StaffDataTable
    table_key = "staff"
    view_capability = VIEW_ORGANISATION_STAFF
    quick_view = StaffQuickView

    intro_template_name = "educator_interface/partials/staff_only_admin_callout.html"
    refresh_events = (STAFF_CHANGED,)

    @classmethod
    def get_actions(cls, request: HttpRequest) -> list[PanelAction]:
        return [
            AddStaffMemberAction(),
            AddRoleAction(),
            DeactivateRoleAction(),
            ChangeCohortsAction(),
            DeactivateStaffMemberAction(),
            ReactivateStaffMemberAction(),
        ]

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        """A staff member opens in the quick view, which lists their roles, so
        it serves only people on this organisation's staff, to a viewer who
        may see roles."""
        organisation = cast(OrganisationScopedRequest, request).organisation
        if (
            not may_see_staff_roles(request)
            or not staff_of(organisation).filter(pk=instance.pk).exists()
        ):
            raise OrganisationScopeDenied

    @classmethod
    def get_cell_context(cls, request: HttpRequest) -> dict[str, object]:
        organisation = cast(OrganisationScopedRequest, request).organisation
        return {
            "viewer": request.user,
            "staff_url": interface_path(organisation, "staff"),
            "grantable_role_keys": {g.role for g in grantable_roles_for(request)},
            "shows_roles": may_see_staff_roles(request),
        }

    @classmethod
    def get_intro_context(cls, request: HttpRequest) -> dict[str, object]:
        scoped = cast(OrganisationScopedRequest, request)
        staff = staff_of(scoped.organisation)
        return {
            # One query: the first two staff pks are the viewer's alone only
            # when the viewer is the sole staff member.
            "only_staff_member_is_viewer": set(staff.values_list("pk", flat=True)[:2])
            == {scoped.user.pk},
        }
