"""Template tags for the course reference outline in the player sidebar."""

from __future__ import annotations

from django import template
from django.template import Context

from freedom_ls.content_engine.models import Course, CoursePart, Topic
from freedom_ls.learner_interface.utils import reference_outline

register = template.Library()


@register.inclusion_tag(
    "learner_interface/partials/reference_outline.html", takes_context=True
)
def reference_link(context: Context) -> dict[str, object]:
    """The sidebar's Reference heading and outline, when the course has reference topics.

    The tag reads the course from the page, so no player view has to supply
    anything for the outline to appear. On a reference topic page the view's
    current_part and topic mark the current row.
    """
    course: Course = context["course"]
    on_reference_page = context.get("on_reference_page", False)
    current_part = context.get("current_part") if on_reference_page else None
    topic = context.get("topic") if on_reference_page else None
    return {
        "course": course,
        "reference_outline": reference_outline(
            course,
            linked=True,
            current_part=current_part if isinstance(current_part, CoursePart) else None,
            current_topic=topic if isinstance(topic, Topic) else None,
        ),
        "on_reference_listing": on_reference_page and current_part is None,
    }
