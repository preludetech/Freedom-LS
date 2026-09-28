"""The component reference page: every panel_framework component, every state.

Static example data only, so the page carries no model access and no query
cost of its own. `component_reference` is the one view; `config/urls.py`
includes it only under `if settings.DEBUG:`, and the isolated test URLconf
(`tests/urls.py`) exposes the same view unconditionally so it can be tested
without a real dev server.
"""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

# Two rows for `#attention-list-default`, so the divider between rows is
# visible. Their `href`/`action_href` are fragments on the page itself
# (`#attention-row-target` / `#attention-row-action`), which lets the
# Playwright test assert on the URL after a tap without leaving the page.
EXAMPLE_CONTEXT: dict[str, object] = {
    "attention_rows": [
        {
            "subject": "Thandi Mokoena",
            "user_id": 42,
            "reason": "4 days idle",
            "badge_label": "Stalled",
            "badge_tone": "warning",
            "href": "#attention-row-target",
            "action_label": "Message",
            "action_href": "#attention-row-action",
        },
        {
            "subject": "Sipho Nkosi",
            "user_id": 7,
            "reason": "Last active 6 days ago",
            "badge_label": "",
            "badge_tone": "muted",
            "href": "#attention-row-target",
            "action_label": "Message",
            "action_href": "#attention-row-action",
        },
    ],
}


@staff_member_required
def component_reference(
    request: HttpRequest,
    template_name: str = "panel_framework/reference/component_reference.html",
) -> HttpResponse:
    return render(request, template_name, EXAMPLE_CONTEXT)
