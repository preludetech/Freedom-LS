"""The learners section's configuration."""

from __future__ import annotations

from typing import cast

from django.db.models import Model
from django.http import HttpRequest

from freedom_ls.educator_interface.events import LEARNER_CHANGED
from freedom_ls.educator_interface.exceptions import OrganisationScopeDenied
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
    OrganisationSectionConfig,
)

# Importing the module registers the learners table's bulk actions.
from freedom_ls.educator_interface.panels.learner import bulk_actions  # noqa: F401
from freedom_ls.educator_interface.panels.learner.actions import (
    AddLearnerAction,
    ImportLearnersAction,
)
from freedom_ls.educator_interface.panels.learner.data_tables import LearnerDataTable
from freedom_ls.educator_interface.panels.learner.instance_view import (
    LearnerInstanceView,
)
from freedom_ls.educator_interface.panels.learner.quick_view import LearnerQuickView
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_management.queries import learners_visible_to
from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.bulk_actions import BulkAction, bulk_actions_for_table
from freedom_ls.panel_framework.views import ListViewConfig

__all__ = [
    "LearnerConfig",
]


class LearnerConfig(OrganisationSectionConfig, ListViewConfig):
    url_name = "learners"
    menu_label = "Learners"
    icon = "user"
    model = Learner
    list_view = LearnerDataTable
    table_key = "learners"
    instance_view = LearnerInstanceView
    refresh_events = (LEARNER_CHANGED,)
    quick_view = LearnerQuickView

    @classmethod
    def get_actions(cls, request: HttpRequest) -> list[PanelAction]:
        return [AddLearnerAction(), ImportLearnersAction()]

    @classmethod
    def get_bulk_actions(cls, request: HttpRequest) -> list[BulkAction]:
        return list(bulk_actions_for_table(cls.table_key))

    @classmethod
    def get_instance_label(cls, instance: Model) -> str:
        return cast(Learner, instance).user.display_name

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        organisation = cast(OrganisationScopedRequest, request).organisation
        if (
            not learners_visible_to(request.user, organisation, include_inactive=True)
            .filter(pk=instance.pk)
            .exists()
        ):
            raise OrganisationScopeDenied
