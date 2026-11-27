"""The Personal details page: one stack of panels for the user's own row."""

from __future__ import annotations

from panel_framework.panels import PanelStack
from panel_framework.views import InstanceView

from .panels import (
    EmailAddressesPanel,
    NamePanel,
    PasswordPanel,
    ProfilePicturePanel,
)


class PersonalDetailsStack(PanelStack):
    title = "Personal details"
    children = {
        "name": NamePanel,
        "profile-picture": ProfilePicturePanel,
        "email-addresses": EmailAddressesPanel,
        "password": PasswordPanel,
    }


class PersonalDetailsInstanceView(InstanceView):
    panel = PersonalDetailsStack
