from __future__ import annotations

from dataclasses import dataclass

from freedom_ls.panel_framework.panels import Panel


@dataclass
class Tab:
    label: str
    panels: dict[str, type[Panel]]
