from __future__ import annotations

from django.db.models import Model
from django.http import HttpRequest


class QuickView:
    """Feeds the drawer opened for one row of a `ListViewConfig`'s table.

    Bound fresh on every request, the way an `InstanceView` is. A consumer
    overrides `get_context_data` (and `get_title`, when the instance's
    `str()` is not what the drawer should show) to supply the fields its
    template renders.
    """

    template_name: str
    #: Domain events that make an open drawer refetch itself when they name
    #: the shown instance.
    refresh_events: tuple[str, ...] = ()

    def __init__(self, request: HttpRequest, instance: Model) -> None:
        self.request = request
        self.instance = instance

    def get_title(self) -> str:
        return str(self.instance)

    def get_context_data(self) -> dict[str, object]:
        return {}
