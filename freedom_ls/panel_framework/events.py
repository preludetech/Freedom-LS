"""The HX-Trigger contract every panel action answers through.

A domain event names an entity that changed and carries the primary keys of
the rows it touched, so a listener elsewhere on the page can decide whether
it cares. `closeModal` and `instanceTitleChanged` are not domain events —
they are framework signals the modal component itself consumes — so they get
their own constants rather than living in a consumer's event list.
"""

from __future__ import annotations

import json

CLOSE_MODAL_EVENT = "closeModal"
INSTANCE_TITLE_EVENT = "instanceTitleChanged"


def build_hx_trigger(
    events: dict[str, list[str]],
    *,
    close_modal: bool = False,
    title: str | None = None,
) -> str:
    """The JSON body of an HX-Trigger header for a panel action response.

    Every action builds its header through this function, so the client
    only ever has to parse one shape: each domain event maps to
    ``{"ids": [...]}``, and the two framework signals are opted into by
    keyword rather than appearing in `events`.
    """
    payload: dict[str, object] = {name: {"ids": ids} for name, ids in events.items()}
    if close_modal:
        payload[CLOSE_MODAL_EVENT] = {}
    if title is not None:
        payload[INSTANCE_TITLE_EVENT] = {"title": title}
    return json.dumps(payload)
