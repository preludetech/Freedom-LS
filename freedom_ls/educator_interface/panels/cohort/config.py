"""The cohorts section's configuration."""

from __future__ import annotations

from typing import cast

from django import forms
from django.db import transaction
from django.db.models import Model
from django.http import HttpRequest, HttpResponse

from freedom_ls.accounts.models import User
from freedom_ls.educator_interface.events import COHORT_CHANGED
from freedom_ls.educator_interface.exceptions import OrganisationScopeDenied
from freedom_ls.educator_interface.forms import CohortForm

# Importing the module registers the cohorts table's bulk actions.
from freedom_ls.educator_interface.panels.cohort import bulk_actions  # noqa: F401
from freedom_ls.educator_interface.panels.cohort.data_tables import CohortDataTable
from freedom_ls.educator_interface.panels.cohort.instance_view import (
    CohortInstanceView,
)
from freedom_ls.educator_interface.panels.cohort.quick_view import CohortQuickView
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
    OrganisationSectionConfig,
)
from freedom_ls.educator_interface.paths import interface_path
from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_management.queries import cohorts_visible_to
from freedom_ls.learner_management.utils import record_cohort_entry
from freedom_ls.panel_framework.actions import CreateInstanceAction, PanelAction
from freedom_ls.panel_framework.bulk_actions import BulkAction, bulk_actions_for_table
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.views import ListViewConfig

__all__ = [
    "CohortConfig",
    "CreateCohortAction",
]


class CreateCohortAction(CreateInstanceAction):
    label = "Create cohort"
    form_class = CohortForm
    form_title = "Create cohort"
    action_name = "create_cohort"
    success_events = (COHORT_CHANGED,)

    def get_form(self, ctx: PanelContext) -> forms.BaseForm:
        # The organisation is not a user choice — CohortForm never exposes
        # the field — so it comes from the URL the request already resolved
        # and authorised, not from anything the form submitted. It is attached
        # here rather than in form_valid because the per-organisation
        # uniqueness constraint can only be checked while cleaning if the
        # instance already carries its organisation.
        form = super().get_form(ctx)
        organisation = cast(OrganisationScopedRequest, ctx.request).organisation
        cast(Cohort, cast(forms.ModelForm, form).instance).organisation = organisation
        return form

    def get_success_url(self, ctx: PanelContext, instance: Model) -> str:
        organisation = cast(OrganisationScopedRequest, ctx.request).organisation
        return interface_path(organisation, f"cohorts/{instance.pk}")

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        with transaction.atomic():
            response = super().form_valid(ctx, form)
            record_cohort_entry(
                cast(Cohort, cast(forms.ModelForm, form).instance),
                "cohort.created",
                cast(User, ctx.request.user),
            )
        return response


class CohortConfig(OrganisationSectionConfig, ListViewConfig):
    url_name = "cohorts"
    menu_label = "Cohorts"
    icon = "cohort"
    model = Cohort
    list_view = CohortDataTable
    table_key = "cohorts"
    instance_view = CohortInstanceView
    refresh_events = (COHORT_CHANGED,)
    quick_view = CohortQuickView

    @classmethod
    def get_actions(cls, request: HttpRequest) -> list[PanelAction]:
        return [CreateCohortAction()]

    @classmethod
    def get_bulk_actions(cls, request: HttpRequest) -> list[BulkAction]:
        return list(bulk_actions_for_table(cls.table_key))

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        organisation = cast(OrganisationScopedRequest, request).organisation
        if (
            not cohorts_visible_to(request.user, organisation)
            .filter(pk=instance.pk)
            .exists()
        ):
            raise OrganisationScopeDenied
