"""The panels on the Personal details page."""

from __future__ import annotations

from typing import cast

from allauth.account.internal import flows

from django.http import HttpRequest

from freedom_ls.accounts.models import User
from freedom_ls.accounts.utils import get_own_user
from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.panels import Panel

from .actions import (
    ACCOUNT_CHANGED,
    EMAIL_ADDRESSES_CHANGED,
    PASSWORD_CHANGED,
    AddEmailAction,
    ChangePasswordAction,
    EditNameAction,
    MakePrimaryEmailAction,
    RemoveEmailAction,
    RemoveProfilePictureAction,
    ResendVerificationAction,
    UploadProfilePictureAction,
    own_email_addresses,
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


class EmailAddressesPanel(OwnAccountPanel):
    """The user's email addresses, one row each with its badges and its own
    actions, and Add email in the footer."""

    title = "Email addresses"
    template_name = "accounts/panels/email_addresses.html"
    refresh_events = (EMAIL_ADDRESSES_CHANGED,)

    def get_actions(self) -> list[PanelAction]:
        return [
            AddEmailAction(),
            MakePrimaryEmailAction(),
            ResendVerificationAction(),
            RemoveEmailAction(),
        ]

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context["rows"] = [
            {
                "address": address,
                "can_make_primary": not address.primary
                and flows.manage_email.can_mark_as_primary(address),
                "can_resend": not address.verified,
                "can_remove": flows.manage_email.can_delete_email(address),
            }
            for address in own_email_addresses(self.ctx)
        ]
        return context


class PasswordPanel(OwnAccountPanel):
    """The user's password as an inline form, titled Set password for a user
    who has none."""

    title = "Password"
    template_name = "accounts/panels/password.html"
    refresh_events = (PASSWORD_CHANGED,)

    def get_actions(self) -> list[PanelAction]:
        return [ChangePasswordAction(cast(User, self.instance))]

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        action = cast(ChangePasswordAction, self.available_actions[0])
        context["change"] = action.get_context_data(self.ctx)
        context["submit_label"] = action.label
        if not action.has_password:
            context["title"] = "Set password"
        return context
