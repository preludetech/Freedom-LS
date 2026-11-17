"""Panels whose body costs a gather: the first render is a skeleton that fetches the body."""

from __future__ import annotations

from datetime import datetime

from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from freedom_ls.panel_framework.errors import PanelBodyTooLargeError
from freedom_ls.panel_framework.panels import Panel

__all__ = ["LOADED_PARAM", "LazyBodyPanel", "render_region"]

#: The query parameter that turns a lazy panel's skeleton into its body.
LOADED_PARAM = "loaded"


def render_region(panel: Panel, status: int = 200) -> HttpResponse:
    """A panel's refresh region on its own, the fragment a targeted swap replaces."""
    return render(
        panel.request,
        panel.region_template_name or panel.template_name,
        panel.get_context_data(),
        status=status,
    )


class LazyBodyPanel(Panel):
    """A panel whose body costs a gather: the first render is a skeleton that fetches the body.

    get_loaded_context runs only on the fetch that carries loaded=1. It may
    raise PanelBodyTooLargeError; the region then shows the error's message
    instead of a body.
    """

    template_name = "panel_framework/panels/lazy_panel.html"
    skeleton_shape = "text"
    skeleton_lines = 3
    #: The link text a browser without JavaScript follows to load the body.
    load_label: str = "Load"
    #: Show when the body's data is from, above the loaded body. A panel whose
    #: data is gathered or cached returns the time it was computed under
    #: "as_of" from get_loaded_context; otherwise the stamp is the time of
    #: this render, which is wrong for data that is older than the request.
    show_as_of: bool = False

    @property
    def is_loaded(self) -> bool:
        return self.request.GET.get(LOADED_PARAM) == "1"

    def get_loaded_context(self) -> dict[str, object]:
        return {}

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context.update(
            is_loaded=self.is_loaded,
            loaded_url=f"{self.ctx.base_url}?{LOADED_PARAM}=1",
            skeleton_shape=self.skeleton_shape,
            skeleton_lines=self.skeleton_lines,
            load_label=self.load_label,
            show_as_of=self.show_as_of,
        )
        if self.is_loaded:
            try:
                context.update(self.get_loaded_context())
                if self.show_as_of:
                    as_of = context.setdefault("as_of", timezone.now())
                    if not isinstance(as_of, datetime) or timezone.is_naive(as_of):
                        raise ValueError(
                            f"{type(self).__name__}'s as_of must be an aware datetime."
                        )
            except PanelBodyTooLargeError as error:
                context["too_large_message"] = str(error)
        return context
