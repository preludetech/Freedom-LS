"""Template tags for the course reference link in the player sidebar."""

from __future__ import annotations

from django import template
from django.template import Context

from freedom_ls.content_engine.models import Course

register = template.Library()


@register.inclusion_tag(
    "learner_interface/partials/reference_link.html", takes_context=True
)
def reference_link(context: Context) -> dict[str, object]:
    """The sidebar link to the course's reference listing, when it has one.

    The tag reads the course from the page, so no player view has to supply
    anything for the link to appear.
    """
    course: Course = context["course"]
    return {
        "course": course,
        "has_reference": course.reference_parts.exists(),
        "is_current": context.get("on_reference_page", False),
    }
