"""The per-request state a bound panel or action needs to render or submit."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from django.db.models import Model
from django.http import HttpRequest

__all__ = [
    "PanelContext",
]

if TYPE_CHECKING:
    # Under TYPE_CHECKING only: views.py imports context.py, so a runtime
    # import the other way round would cycle.
    from freedom_ls.panel_framework.views import SectionConfigBase


@dataclass(frozen=True, kw_only=True)
class PanelContext:
    """Everything a bound panel or action needs at render time.

    `base_url` is the URL of this panel's own path segment. `name` is this
    panel's key in its parent's `children` dict, and is the empty string for
    a root panel. `page_url` is the URL the browser's address bar should show
    while this panel is current: it advances at a tab boundary, since a tab
    has its own page, and stays put through a panel stack, since a stack's
    panels all share the one page their tab already named. A container
    builds each child's context with `dataclasses.replace(ctx, base_url=...,
    name=...)` rather than mutating the parent's context, and a new field can
    be added here with a default without breaking any existing subclass --
    `config` has none, because every construction site passes it.
    """

    request: HttpRequest
    instance: Model | None
    base_url: str
    name: str
    config: type[SectionConfigBase]
    scope: Model | None = None
    page_url: str = ""
    # The reason a confirm dialog posted, set by the action that validated
    # it; empty for an action that takes none.
    reason: str = ""
    # What `once` has loaded during this request. A context built with
    # `dataclasses.replace` shares it, so a key names everything its value
    # depends on.
    loaded: dict[Hashable, object] = field(
        default_factory=dict, compare=False, repr=False
    )

    def once[T](self, key: Hashable, load: Callable[[], T]) -> T:
        """The value `load` returns, read once per request under `key`: a
        dialog's hooks each ask for the same row, and only the first ask
        reaches the database. A `load` that raises stores nothing."""
        if key not in self.loaded:
            self.loaded[key] = load()
        return cast(T, self.loaded[key])

    def scope_object(self) -> Model | None:
        """The object a permission check runs against: the bound instance,
        or, on a list or base view with none, the list-level scope."""
        return self.instance if self.instance is not None else self.scope
