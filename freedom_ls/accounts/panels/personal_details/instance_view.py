"""The Personal details page: one stack of panels for the user's own row."""

from __future__ import annotations

from freedom_ls.panel_framework.panels import PanelStack
from freedom_ls.panel_framework.views import InstanceView

from .panels import NamePanel, ProfilePicturePanel


class PersonalDetailsStack(PanelStack):
    title = "Personal details"
    children = {"name": NamePanel, "profile-picture": ProfilePicturePanel}


class PersonalDetailsInstanceView(InstanceView):
    panel = PersonalDetailsStack
