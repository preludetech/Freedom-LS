"""Template tags for the course reference outline in the player sidebar."""

from __future__ import annotations

from django import template
from django.template import Context

from freedom_ls.content_engine.models import Course
from freedom_ls.learner_interface.utils import reference_outline

register = template.Library()


@register.inclusion_tag(
    "learner_interface/partials/reference_outline.html", takes_context=True
)
def reference_link(context: Context) -> dict[str, object]:
    """The sidebar's Reference heading and outline, when the course has reference topics.

    The tag reads the course from the page, so no player view has to supply
    anything for the outline to appear. A reference page supplies its own
    reference_outline, with the topic being read marked current, and the tag
    draws that rather than reading the parts again. Elsewhere topic rows link
    only where the page sets reference_linked, so a learner the reference pages
    would turn away sees the titles alone.
    """
    course: Course = context["course"]
    on_reference_page = context.get("on_reference_page", False)
    outline = context.get("reference_outline")
    if outline is None:
        outline = reference_outline(
            course, linked=bool(context.get("reference_linked", False))
        )
    return {
        "course": course,
        "reference_outline": outline,
        "on_reference_listing": on_reference_page
        and context.get("current_part") is None,
    }
