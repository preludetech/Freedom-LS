"""The panels on the Personal details page."""

from __future__ import annotations

from typing import cast

from django.http import HttpRequest

from freedom_ls.accounts.models import User
from freedom_ls.accounts.utils import get_own_user
from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.panels import Panel

from .actions import (
    ACCOUNT_CHANGED,
    EditNameAction,
    RemoveProfilePictureAction,
    UploadProfilePictureAction,
)


class OwnAccountPanel(Panel):
    """A panel on the user's own row. It holds nothing but its actions' forms,
    so it shows only to a user who may run one of them."""

    model = User

    def has_permission(self, request: HttpRequest) -> bool:
        return super().has_permission(request) and bool(self.available_actions)


class NamePanel(OwnAccountPanel):
    """The user's first and last name as fields with Save, posted inline to
    the edit action. The save response re-renders the form, which is all the
    panel holds, so it needs no refresh events."""

    title = "Name"
    template_name = "accounts/panels/name.html"

    def get_actions(self) -> list[PanelAction]:
        return [EditNameAction(cast(User, self.instance))]

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context["rename"] = self.available_actions[0].get_context_data(self.ctx)
        return context


class ProfilePicturePanel(OwnAccountPanel):
    """The stored picture, or the initials, above an inline upload form."""

    title = "Profile picture"
    template_name = "accounts/panels/profile_picture.html"
    refresh_events = (ACCOUNT_CHANGED,)

    def get_actions(self) -> list[PanelAction]:
        return [
            UploadProfilePictureAction(cast(User, self.instance)),
            RemoveProfilePictureAction(),
        ]

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context["upload"] = self.available_actions[0].get_context_data(self.ctx)
        # Read fresh rather than from self.instance: a form that has bound a
        # refused file onto the instance must not show it as the current
        # picture.
        context["stored_user"] = get_own_user(self.ctx.request)
        return context
