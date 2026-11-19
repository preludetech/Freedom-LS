"""The panels on the Personal details page."""

from __future__ import annotations

from typing import cast

from django.http import HttpRequest

from freedom_ls.accounts.models import User
from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.panels import Panel

from .actions import EditNameAction


class NamePanel(Panel):
    """The user's first and last name as fields with Save, posted inline to
    the edit action. The save response re-renders the form, which is all the
    panel holds, so it needs no refresh events."""

    model = User
    title = "Name"
    template_name = "accounts/panels/name.html"

    def has_permission(self, request: HttpRequest) -> bool:
        return super().has_permission(request) and bool(self.available_actions)

    def get_actions(self) -> list[PanelAction]:
        return [EditNameAction(cast(User, self.instance))]

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context["rename"] = self.available_actions[0].get_context_data(self.ctx)
        return context
