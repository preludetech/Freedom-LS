"""Tests for the shared deadline copy partials."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.utils import timezone


def test_closes_line_has_no_space_before_full_stop() -> None:
    """The closes line used to render a space between the date and its full stop."""
    child = SimpleNamespace(
        due_at=timezone.now() + timedelta(days=30),
        closes_at=timezone.now() + timedelta(days=33),
        is_closed=False,
        is_overdue=False,
        status="INCOMPLETE",
        deadline_tier="UPCOMING",
    )

    html = render_to_string(
        "learner_interface/partials/deadline_labels.html#deadline-text",
        {
            "child": child,
            "title": "Knowledge Check",
            "show_time_zone_to_learners": False,
        },
    )

    assert "</time>." in html
