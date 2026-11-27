"""The organisation-scoped request type and the section config every organisation section extends."""

from __future__ import annotations

from typing import cast

from panel_framework.views import SectionConfigBase

from django.db.models import Model
from django.http import HttpRequest

from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_management.queries import (
    VIEW_COHORT,
    VIEW_ORGANISATION_STAFF,
    active_organisation_admins,
    can_on_any,
)
from freedom_ls.learner_management.role_assignment import GrantableRole
from freedom_ls.organisations.models import Organisation

__all__ = [
    "LAST_ORGANISATION_SESSION_KEY",
    "OrganisationScopedRequest",
    "OrganisationSectionConfig",
]

#: Session key remembering the educator's last-visited organisation, used
#: only to pick a default for the bare /educator/ redirect. Re-authorised on
#: every use — the session value is never trusted on its own.
LAST_ORGANISATION_SESSION_KEY = "educator_interface_last_organisation_slug"


class OrganisationScopedRequest(HttpRequest):
    """Typing-only view of a request after interface() has resolved and
    authorised an organisation onto it.

    panel_framework names none of these: the scope it enforces is whatever a
    config lists in required_request_attrs, and the title segment reads
    panel_scope_name. So this class exists purely so the educator modules can
    type-check the attribute access without a type: ignore. Never
    instantiated; only used with cast().
    """

    organisation: Organisation
    panel_scope_name: str
    panel_url_kwargs: dict[str, str]
    accessible_organisations: list[Organisation]
    path_string: str
    panel_announcement: str
    panel_extra_oob: list[str]
    grantable_roles: list[GrantableRole]
    role_reach: dict[str, set[Cohort]]

    may_see_staff_roles: bool
    works_with_cohorts: bool


class OrganisationSectionConfig(SectionConfigBase):
    """Shared by every section scoped to the organisation interface() resolves."""

    required_request_attrs = ("organisation",)

    @classmethod
    def get_scope(cls, request: HttpRequest) -> Model | None:
        return cast(OrganisationScopedRequest, request).organisation

    @classmethod
    def has_capability(
        cls, request: HttpRequest, capability: str, scope: Model
    ) -> bool:
        return can(request.user, capability, scope)

    @classmethod
    def is_visible(cls, request: HttpRequest) -> bool:
        # A section that names no capability is for people who work with the
        # organisation's cohorts; a role that only sees the staff list stops at Staff.
        if cls.view_capability is None:
            return cls._works_with_cohorts(request)
        return super().is_visible(request)

    @staticmethod
    def _works_with_cohorts(request: HttpRequest) -> bool:
        """Whether the viewer holds view_cohort here, answered once per
        request because every section without a capability asks."""
        scoped = cast(OrganisationScopedRequest, request)
        cached = getattr(scoped, "works_with_cohorts", None)
        if cached is None:
            cached = can_on_any(scoped.user, scoped.organisation, VIEW_COHORT)
            scoped.works_with_cohorts = cached
        return cached

    @classmethod
    def get_denied_context(
        cls, request: HttpRequest, capability: str | None, scope: Model | None
    ) -> dict[str, str]:
        organisation = cast(OrganisationScopedRequest, request).organisation
        who = f"Ask an organisation admin of {organisation.name}."
        if can(request.user, VIEW_ORGANISATION_STAFF, organisation):
            names = [
                admin.display_name for admin in active_organisation_admins(organisation)
            ]
            if names:
                who = (
                    f"Ask an organisation admin of {organisation.name}: "
                    f"{', '.join(names)}."
                )
        return {"who_to_ask": who}
